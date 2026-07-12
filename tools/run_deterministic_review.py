from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from axiom_review.contract import canonical_json  # noqa: E402
from axiom_review.freshness import SourceResult  # noqa: E402
from axiom_review.freshness_contract import (  # noqa: E402
    build_freshness_envelope,
    render_freshness_markdown,
    validate_freshness_envelope,
)
from axiom_review.gate import (  # noqa: E402
    EXIT_INTERNAL,
    EXIT_USAGE,
    GateInputError,
    GateInternalError,
    load_event,
    run_deterministic_review,
)


def _default_repository(root: Path) -> str | None:
    try:
        contract = json.loads((root / "contracts" / "project.json").read_text(encoding="utf-8"))
        repository = contract["project"]["repository"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None
    return repository if isinstance(repository, str) else None


def _git_head(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def write_freshness_artifacts(
    *,
    output_dir: Path,
    report_path: Path,
    repository: str,
    pull_request_number: int,
    base_sha: str,
    head_sha: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
    proof_artifact_name: str,
    proof_artifact_digest: str,
) -> tuple[Path, Path]:
    """Write validated exact-head JSON and Markdown from trusted workflow inputs."""

    sources = [
        SourceResult(
            source_id="axiom-proof",
            conclusion="passed",
            reviewed_head_sha=head_sha,
            run_id=workflow_run_id,
            run_attempt=workflow_run_attempt,
            artifact_name=proof_artifact_name,
            artifact_digest=proof_artifact_digest,
        ),
        SourceResult(
            source_id="deterministic-review",
            conclusion="passed",
            reviewed_head_sha=head_sha,
            run_id=workflow_run_id,
            run_attempt=workflow_run_attempt,
            artifact_name=report_path.name,
            artifact_digest=_sha256_file(report_path),
        ),
    ]
    envelope = build_freshness_envelope(
        repository=repository,
        pull_request_number=pull_request_number,
        base_sha=base_sha,
        current_head_sha=head_sha,
        publisher_run_id=workflow_run_id,
        publisher_run_attempt=workflow_run_attempt,
        sources=sources,
    )
    findings = validate_freshness_envelope(envelope)
    if findings:
        codes = ", ".join(item.code for item in findings)
        raise GateInternalError(f"generated freshness envelope failed validation: {codes}")

    envelope_path = output_dir / "freshness-envelope.json"
    markdown_path = output_dir / "freshness-summary.md"
    envelope_path.write_text(canonical_json(envelope), encoding="utf-8")
    markdown_path.write_text(render_freshness_markdown(envelope), encoding="utf-8")
    return envelope_path, markdown_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the AXIOM deterministic pull-request review gate"
    )
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--event", type=Path, help="GitHub pull_request event JSON path")
    parser.add_argument("--repository", help="owner/name; defaults to the project contract")
    parser.add_argument("--pull-request", type=int, dest="pull_request")
    parser.add_argument("--base-sha", dest="base_sha")
    parser.add_argument("--head-sha", dest="head_sha", help="defaults to git rev-parse HEAD")
    parser.add_argument("--evidence-dir", type=Path, dest="evidence_dir")
    parser.add_argument("--output", type=Path, dest="output_dir")
    parser.add_argument("--workflow-run-id", type=int)
    parser.add_argument("--workflow-run-attempt", type=int)
    parser.add_argument("--proof-artifact-name")
    parser.add_argument("--proof-artifact-digest")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    explicit = [args.repository, args.pull_request, args.base_sha, args.head_sha]
    if args.event is not None and any(value is not None for value in explicit):
        print(
            "--event is mutually exclusive with --repository/--pull-request/--base-sha/--head-sha",
            file=sys.stderr,
        )
        return EXIT_USAGE

    workflow_values = [
        args.workflow_run_id,
        args.workflow_run_attempt,
        args.proof_artifact_name,
        args.proof_artifact_digest,
    ]
    if any(value is not None for value in workflow_values) and not all(
        value is not None for value in workflow_values
    ):
        print(
            "workflow freshness inputs must be supplied together",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if args.workflow_run_id is not None and args.workflow_run_id < 1:
        print("--workflow-run-id must be positive", file=sys.stderr)
        return EXIT_USAGE
    if args.workflow_run_attempt is not None and args.workflow_run_attempt < 1:
        print("--workflow-run-attempt must be positive", file=sys.stderr)
        return EXIT_USAGE

    try:
        if args.event is not None:
            identity = load_event(args.event)
        else:
            repository = args.repository or _default_repository(root)
            head_sha = args.head_sha or _git_head(root)
            missing = [
                name
                for name, value in (
                    ("--repository", repository),
                    ("--pull-request", args.pull_request),
                    ("--base-sha", args.base_sha),
                    ("--head-sha", head_sha),
                )
                if value is None
            ]
            if missing:
                raise GateInputError(f"missing required identity input: {', '.join(missing)}")
            identity = {
                "repository": repository,
                "pull_request_number": args.pull_request,
                "base_sha": args.base_sha,
                "head_sha": head_sha,
            }
    except GateInputError as error:
        print(f"deterministic review input error: {error}", file=sys.stderr)
        return EXIT_USAGE

    try:
        result = run_deterministic_review(
            root,
            repository=identity["repository"],
            pull_request_number=identity["pull_request_number"],
            base_sha=identity["base_sha"],
            head_sha=identity["head_sha"],
            evidence_dir=args.evidence_dir,
            output_dir=args.output_dir,
        )
        freshness_paths: tuple[Path, Path] | None = None
        if (
            result.exit_code == 0
            and result.report_path is not None
            and args.workflow_run_id is not None
        ):
            output_dir = result.report_path.parent
            freshness_paths = write_freshness_artifacts(
                output_dir=output_dir,
                report_path=result.report_path,
                repository=identity["repository"],
                pull_request_number=identity["pull_request_number"],
                base_sha=identity["base_sha"],
                head_sha=identity["head_sha"],
                workflow_run_id=args.workflow_run_id,
                workflow_run_attempt=args.workflow_run_attempt,
                proof_artifact_name=args.proof_artifact_name,
                proof_artifact_digest=args.proof_artifact_digest,
            )
    except GateInternalError as error:
        print(f"deterministic review failed closed: {error}", file=sys.stderr)
        return EXIT_INTERNAL
    except Exception:  # noqa: BLE001 - the gate must fail closed, never crash open
        traceback.print_exc()
        return EXIT_INTERNAL

    for problem in result.errors:
        print(f"deterministic review input error: {problem}", file=sys.stderr)
    print(
        json.dumps(
            {
                "document_kind": "axiom.automated-review.gate-run",
                "schema_version": "0.1.0",
                "status": result.report.get("status", "unavailable"),
                "exit_code": result.exit_code,
                "report": str(result.report_path) if result.report_path else None,
                "summary": str(result.summary_path) if result.summary_path else None,
                "freshness_envelope": str(freshness_paths[0]) if freshness_paths else None,
                "freshness_summary": str(freshness_paths[1]) if freshness_paths else None,
                "findings": len(result.report.get("findings", [])),
            },
            sort_keys=True,
        )
    )
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
