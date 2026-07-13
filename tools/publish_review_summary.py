from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from axiom_review.contract import (  # noqa: E402
    SCHEMA_PATH,
    canonical_json,
    render_markdown,
    validate_report,
)
from axiom_review.publisher import (  # noqa: E402
    ArtifactLimits,
    GitHubRestApi,
    PublicationDecision,
    PublicationRejected,
    find_existing_publication_comment,
    inspect_publication_archive,
    parse_workflow_run_event,
    publication_decision,
    render_publication_comment,
    resolve_publication_identity,
)

ENVELOPE_SCHEMA_PATH = Path("review/contracts/0.1.0/publication-envelope.schema.json")
EXPECTED_WORKFLOW_NAME = "AXIOM deterministic review"
LIMITS = ArtifactLimits(
    max_archive_bytes=20_000_000,
    max_entries=64,
    max_file_bytes=1_048_576,
    max_total_uncompressed_bytes=16_000_000,
    max_compression_ratio=250,
    max_report_bytes=1_048_576,
    max_summary_bytes=262_144,
    max_comment_bytes=60_000,
)


def _load_json_object(path: Path, label: str, max_bytes: int = 2_000_000) -> dict[str, Any]:
    try:
        size = path.stat().st_size
        if size > max_bytes:
            raise PublicationRejected(f"{label} exceeds byte limit")
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PublicationRejected(f"{label} is missing: {path}") from error
    except OSError as error:
        raise PublicationRejected(f"{label} could not be read: {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise PublicationRejected(f"{label} is not valid JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise PublicationRejected(f"{label} root must be an object")
    return value


def _validate_schema(instance: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise PublicationRejected(f"{label} schema is invalid: {error.message}") from error
    errors = sorted(
        Draft202012Validator(schema).iter_errors(instance),
        key=lambda item: (item.json_path, item.message),
    )
    if errors:
        first = errors[0]
        raise PublicationRejected(f"{label} schema violation at {first.json_path}: {first.message}")


def _select_artifact(artifacts: list[dict[str, Any]], expected_name: str) -> dict[str, Any]:
    matches = [
        item
        for item in artifacts
        if item.get("name") == expected_name and item.get("expired") is not True
    ]
    if len(matches) != 1:
        raise PublicationRejected(
            f"expected exactly one non-expired artifact named {expected_name!r}; found {len(matches)}"
        )
    artifact = matches[0]
    artifact_id = artifact.get("id")
    size = artifact.get("size_in_bytes")
    if not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id < 1:
        raise PublicationRejected("artifact id is invalid")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise PublicationRejected("artifact size is invalid")
    if size > LIMITS.max_archive_bytes:
        raise PublicationRejected("artifact exceeds archive byte limit")
    return artifact


def _current_head(pull_request: dict[str, Any], expected_number: int) -> str:
    if pull_request.get("number") != expected_number:
        raise PublicationRejected("pull request number mismatch")
    head = pull_request.get("head")
    if not isinstance(head, dict):
        raise PublicationRejected("pull request head is missing")
    sha = head.get("sha")
    if not isinstance(sha, str) or len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise PublicationRejected("current pull request head SHA is invalid")
    return sha


def publish(event_path: Path, root: Path, token: str, api_url: str) -> dict[str, Any]:
    event = _load_json_object(event_path, "workflow_run event")
    run_identity = parse_workflow_run_event(event, expected_workflow_name=EXPECTED_WORKFLOW_NAME)
    api = GitHubRestApi(token, api_url=api_url)
    identity = resolve_publication_identity(
        run_identity,
        api.list_pull_requests_for_commit(
            run_identity.repository, run_identity.reviewed_head_sha
        ),
    )

    artifact = _select_artifact(
        api.list_run_artifacts(identity.repository, identity.workflow_run_id),
        identity.artifact_name,
    )
    archive_bytes = api.download_artifact(
        identity.repository,
        artifact["id"],
        max_bytes=LIMITS.max_archive_bytes,
    )
    bundle = inspect_publication_archive(archive_bytes, identity, LIMITS)

    envelope_schema = _load_json_object(root / ENVELOPE_SCHEMA_PATH, "publication envelope schema")
    _validate_schema(bundle.envelope, envelope_schema, "publication envelope")
    report_schema = _load_json_object(root / SCHEMA_PATH, "review report schema")
    findings = validate_report(bundle.report, report_schema)
    if findings:
        codes = ", ".join(item.code for item in findings[:10])
        raise PublicationRejected(f"review report failed trusted validation: {codes}")
    if canonical_json(bundle.report).encode("utf-8") != bundle.report_bytes:
        raise PublicationRejected("review report is not canonical JSON")
    trusted_summary = render_markdown(bundle.report)
    if trusted_summary != bundle.summary:
        raise PublicationRejected("review summary does not match trusted rendering")

    pull_request = api.get_pull_request(identity.repository, identity.pull_request_number)
    current_head_sha = _current_head(pull_request, identity.pull_request_number)
    comments = api.list_issue_comments(identity.repository, identity.pull_request_number)
    selected = find_existing_publication_comment(comments)
    existing = selected[1] if selected is not None else None
    decision = publication_decision(
        identity,
        current_head_sha=current_head_sha,
        existing=existing,
    )
    if decision is PublicationDecision.SKIP_OLDER:
        return {
            "document_kind": "axiom.automated-review.publication-result",
            "schema_version": "0.1.0",
            "status": "skipped-older",
            "pull_request_number": identity.pull_request_number,
            "reviewed_head_sha": identity.reviewed_head_sha,
            "current_head_sha": current_head_sha,
            "workflow_run_id": identity.workflow_run_id,
        }

    body = render_publication_comment(
        identity,
        current_head_sha=current_head_sha,
        deterministic_summary=trusted_summary,
        max_comment_bytes=LIMITS.max_comment_bytes,
    )
    if selected is None:
        comment = api.create_issue_comment(
            identity.repository,
            identity.pull_request_number,
            body,
        )
        action = "created"
    else:
        comment = api.update_issue_comment(identity.repository, selected[0], body)
        action = "updated"
    comment_id = comment.get("id")
    if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id < 1:
        raise PublicationRejected("GitHub comment response lacks a valid id")
    return {
        "document_kind": "axiom.automated-review.publication-result",
        "schema_version": "0.1.0",
        "status": action,
        "pull_request_number": identity.pull_request_number,
        "reviewed_head_sha": identity.reviewed_head_sha,
        "current_head_sha": current_head_sha,
        "workflow_run_id": identity.workflow_run_id,
        "comment_id": comment_id,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish one trusted idempotent AXIOM pull-request review summary"
    )
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    try:
        result = publish(args.event, args.root.resolve(), token, api_url)
    except PublicationRejected as error:
        print(f"review publication failed closed: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # noqa: BLE001 - privileged publisher must fail closed
        print(f"review publication internal failure: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(canonical_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
