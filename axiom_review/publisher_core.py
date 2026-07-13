from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

_PUBLICATION_MARKER_PREFIX = "<!-- axiom-review-publication:"
_PUBLICATION_MARKER_SUFFIX = " -->"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY = re.compile(r"^[^/\s]+/[^/\s]+$")

class PublicationRejected(ValueError):
    """Raised when a review artifact cannot cross the trusted publication boundary."""


class PublicationDecision(Enum):
    CREATE = "create"
    UPDATE_CURRENT = "update_current"
    SKIP_OLDER = "skip_older"


@dataclass(frozen=True)
class ArtifactLimits:
    max_archive_bytes: int
    max_entries: int
    max_file_bytes: int
    max_total_uncompressed_bytes: int
    max_compression_ratio: float
    max_report_bytes: int
    max_summary_bytes: int
    max_comment_bytes: int


@dataclass(frozen=True)
class WorkflowRunIdentity:
    repository: str
    reviewed_head_sha: str
    workflow_run_id: int
    workflow_run_attempt: int
    workflow_name: str
    workflow_run_url: str
    artifact_name: str
    pull_request_number_hint: int | None


@dataclass(frozen=True)
class PublicationIdentity:
    repository: str
    pull_request_number: int
    base_sha: str
    reviewed_head_sha: str
    workflow_run_id: int
    workflow_run_attempt: int
    workflow_name: str
    workflow_run_url: str
    artifact_name: str


@dataclass(frozen=True)
class ExistingPublication:
    reviewed_head_sha: str
    current_head_sha: str
    workflow_run_id: int
    workflow_run_attempt: int


@dataclass(frozen=True)
class PublicationBundle:
    identity: PublicationIdentity
    envelope: dict[str, Any]
    report: dict[str, Any]
    report_bytes: bytes
    summary: str
    summary_bytes: bytes


def _reject(condition: bool, message: str) -> None:
    if condition:
        raise PublicationRejected(message)

def _read_json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise PublicationRejected(f"{label} is not UTF-8") from error
    except json.JSONDecodeError as error:
        raise PublicationRejected(f"{label} is not valid JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise PublicationRejected(f"{label} root must be an object")
    return value


def _require_int(value: Any, label: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise PublicationRejected(f"{label} must be an integer >= {minimum}")
    return value


def _require_str(value: Any, label: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise PublicationRejected(f"{label} must be a non-empty string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise PublicationRejected(f"{label} has invalid format")
    return value

def publication_decision(
    incoming: PublicationIdentity,
    *,
    current_head_sha: str,
    existing: ExistingPublication | None,
) -> PublicationDecision:
    """Select an idempotent update while preventing stale-run rollback."""

    _reject(_SHA40.fullmatch(current_head_sha) is None, "current head SHA has invalid format")
    if existing is None:
        return PublicationDecision.CREATE
    incoming_order = (incoming.workflow_run_id, incoming.workflow_run_attempt)
    existing_order = (existing.workflow_run_id, existing.workflow_run_attempt)
    if incoming_order == existing_order:
        return PublicationDecision.UPDATE_CURRENT

    incoming_is_current = incoming.reviewed_head_sha == current_head_sha
    existing_is_current = existing.reviewed_head_sha == current_head_sha
    if incoming_is_current and not existing_is_current:
        return PublicationDecision.UPDATE_CURRENT
    if existing_is_current and not incoming_is_current:
        return PublicationDecision.SKIP_OLDER
    if incoming_order <= existing_order:
        return PublicationDecision.SKIP_OLDER
    return PublicationDecision.UPDATE_CURRENT


def _publication_marker(identity: PublicationIdentity, current_head_sha: str) -> str:
    metadata = {
        "current_head_sha": current_head_sha,
        "reviewed_head_sha": identity.reviewed_head_sha,
        "workflow_run_attempt": identity.workflow_run_attempt,
        "workflow_run_id": identity.workflow_run_id,
    }
    compact = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return f"{_PUBLICATION_MARKER_PREFIX}{compact}{_PUBLICATION_MARKER_SUFFIX}"


def parse_existing_publication(comment_body: str) -> ExistingPublication | None:
    """Read trusted publication metadata from the stable hidden comment marker."""

    start = comment_body.find(_PUBLICATION_MARKER_PREFIX)
    if start < 0:
        return None
    payload_start = start + len(_PUBLICATION_MARKER_PREFIX)
    end = comment_body.find(_PUBLICATION_MARKER_SUFFIX, payload_start)
    if end < 0:
        return None
    try:
        value = json.loads(comment_body[payload_start:end])
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    try:
        reviewed = value["reviewed_head_sha"]
        current = value["current_head_sha"]
        run_id = value["workflow_run_id"]
        attempt = value["workflow_run_attempt"]
    except KeyError:
        return None
    if not isinstance(reviewed, str) or _SHA40.fullmatch(reviewed) is None:
        return None
    if not isinstance(current, str) or _SHA40.fullmatch(current) is None:
        return None
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
        return None
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        return None
    return ExistingPublication(reviewed, current, run_id, attempt)


def _truncate_utf8(text: str, byte_limit: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= byte_limit:
        return text
    suffix = "\n\n_Review summary truncated; use the retained workflow artifact for full details._\n"
    suffix_bytes = suffix.encode("utf-8")
    available = max(byte_limit - len(suffix_bytes), 0)
    prefix = encoded[:available]
    while prefix:
        try:
            decoded = prefix.decode("utf-8")
            return decoded + suffix
        except UnicodeDecodeError as error:
            prefix = prefix[: error.start]
    return suffix[:byte_limit]


def render_publication_comment(
    identity: PublicationIdentity,
    *,
    current_head_sha: str,
    deterministic_summary: str,
    advisory_summary: str | None = None,
    max_comment_bytes: int,
) -> str:
    """Render one bounded PR comment with stable identity and authority separation."""

    _reject(max_comment_bytes < 512, "comment byte limit is too small")
    state = "CURRENT" if identity.reviewed_head_sha == current_head_sha else "STALE"
    artifact_url = f"{identity.workflow_run_url}#artifacts"
    marker = _publication_marker(identity, current_head_sha)
    header = "\n".join(
        [
            marker,
            "## AXIOM automated review publication",
            "",
            f"- State: **{state}**",
            f"- Reviewed head: `{identity.reviewed_head_sha}`",
            f"- Current PR head: `{current_head_sha}`",
            f"- Workflow run: [{identity.workflow_run_id} attempt {identity.workflow_run_attempt}]({identity.workflow_run_url})",
            f"- Full retained artifact: [{identity.artifact_name}]({artifact_url})",
            "",
            "## Deterministic review",
            "",
        ]
    )
    advisory = advisory_summary or "Not run. Advisory AI review has no blocking or merge authority."
    footer = "\n".join(["", "## Advisory AI review", "", advisory.strip(), ""])
    fixed_bytes = len((header + footer).encode("utf-8"))
    _reject(fixed_bytes > max_comment_bytes, "comment metadata exceeds byte limit")
    body = header + _truncate_utf8(deterministic_summary.strip(), max_comment_bytes - fixed_bytes) + footer
    if len(body.encode("utf-8")) > max_comment_bytes:
        body = _truncate_utf8(body, max_comment_bytes)
    return body


def create_publication_envelope(
    identity: PublicationIdentity,
    report_bytes: bytes,
    summary_bytes: bytes,
) -> dict[str, Any]:
    """Create the bounded identity-and-digest envelope uploaded by the read-only run."""

    return {
        "document_kind": "axiom.automated-review.publication-envelope",
        "schema_version": "0.1.0",
        "repository": identity.repository,
        "pull_request_number": identity.pull_request_number,
        "base_sha": identity.base_sha,
        "reviewed_head_sha": identity.reviewed_head_sha,
        "workflow_run_id": identity.workflow_run_id,
        "workflow_run_attempt": identity.workflow_run_attempt,
        "workflow_name": identity.workflow_name,
        "artifact_name": identity.artifact_name,
        "report_path": "review-report.json",
        "report_bytes": len(report_bytes),
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "summary_path": "review-summary.md",
        "summary_bytes": len(summary_bytes),
        "summary_sha256": hashlib.sha256(summary_bytes).hexdigest(),
    }


def parse_workflow_run_event(
    event: dict[str, Any],
    *,
    expected_workflow_name: str,
) -> WorkflowRunIdentity:
    """Parse a completed pull-request workflow_run without trusting PR linkage."""

    _reject(not isinstance(event, dict), "workflow_run event root must be an object")
    _reject(event.get("action") != "completed", "workflow_run action must be completed")
    repository_object = event.get("repository")
    run = event.get("workflow_run")
    _reject(not isinstance(repository_object, dict), "workflow_run repository must be an object")
    _reject(not isinstance(run, dict), "workflow_run payload must contain a workflow_run object")

    repository = _require_str(
        repository_object.get("full_name"), "workflow_run repository", pattern=_REPOSITORY
    )
    _reject(run.get("event") != "pull_request", "workflow_run did not originate from pull_request")
    _reject(run.get("status") != "completed", "workflow_run status must be completed")
    workflow_name = _require_str(run.get("name"), "workflow_run name")
    _reject(workflow_name != expected_workflow_name, "workflow_run name mismatch")
    run_id = _require_int(run.get("id"), "workflow_run id")
    run_attempt = _require_int(run.get("run_attempt"), "workflow_run attempt")
    run_url = _require_str(run.get("html_url"), "workflow_run URL")
    reviewed_head_sha = _require_str(
        run.get("head_sha"), "workflow_run head SHA", pattern=_SHA40
    )

    pull_requests = run.get("pull_requests")
    _reject(not isinstance(pull_requests, list), "workflow_run pull_requests must be an array")
    _reject(len(pull_requests) > 1, "workflow_run contains ambiguous pull request hints")
    pull_request_number_hint: int | None = None
    if pull_requests:
        pull_request = pull_requests[0]
        _reject(not isinstance(pull_request, dict), "workflow_run pull request hint must be an object")
        pull_request_number_hint = _require_int(
            pull_request.get("number"), "workflow_run pull request hint number"
        )
        head = pull_request.get("head")
        if head is not None:
            _reject(not isinstance(head, dict), "workflow_run pull request hint head must be an object")
            hinted_head_sha = _require_str(
                head.get("sha"), "workflow_run pull request hint head SHA", pattern=_SHA40
            )
            _reject(hinted_head_sha != reviewed_head_sha, "workflow_run head identity mismatch")

    return WorkflowRunIdentity(
        repository=repository,
        reviewed_head_sha=reviewed_head_sha,
        workflow_run_id=run_id,
        workflow_run_attempt=run_attempt,
        workflow_name=workflow_name,
        workflow_run_url=run_url,
        artifact_name=f"axiom-deterministic-review-{run_id}",
        pull_request_number_hint=pull_request_number_hint,
    )


def resolve_publication_identity(
    run: WorkflowRunIdentity,
    associated_pull_requests: list[dict[str, Any]],
) -> PublicationIdentity:
    """Bind a workflow run to exactly one GitHub-associated PR for its exact head."""

    _reject(not isinstance(associated_pull_requests, list), "associated pull requests must be an array")
    matches: list[dict[str, Any]] = []
    for pull_request in associated_pull_requests:
        if not isinstance(pull_request, dict):
            continue
        number = pull_request.get("number")
        head = pull_request.get("head")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            continue
        if run.pull_request_number_hint is not None and number != run.pull_request_number_hint:
            continue
        if not isinstance(head, dict) or head.get("sha") != run.reviewed_head_sha:
            continue
        matches.append(pull_request)
    _reject(
        len(matches) != 1,
        f"expected exactly one associated pull request for reviewed head; found {len(matches)}",
    )
    pull_request = matches[0]
    number = _require_int(pull_request.get("number"), "associated pull request number")
    base = pull_request.get("base")
    _reject(not isinstance(base, dict), "associated pull request base is missing")
    base_sha = _require_str(base.get("sha"), "associated pull request base SHA", pattern=_SHA40)
    return PublicationIdentity(
        repository=run.repository,
        pull_request_number=number,
        base_sha=base_sha,
        reviewed_head_sha=run.reviewed_head_sha,
        workflow_run_id=run.workflow_run_id,
        workflow_run_attempt=run.workflow_run_attempt,
        workflow_name=run.workflow_name,
        workflow_run_url=run.workflow_run_url,
        artifact_name=run.artifact_name,
    )


def find_existing_publication_comment(
    comments: list[dict[str, Any]],
) -> tuple[int, ExistingPublication] | None:
    """Select the single trusted Actions-bot publication comment, ignoring forgeries."""

    matches: list[tuple[int, ExistingPublication]] = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user")
        body = comment.get("body")
        comment_id = comment.get("id")
        if not isinstance(user, dict) or not isinstance(body, str):
            continue
        if user.get("login") != "github-actions[bot]" or user.get("type") != "Bot":
            continue
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id < 1:
            continue
        parsed = parse_existing_publication(body)
        if parsed is not None:
            matches.append((comment_id, parsed))
    _reject(len(matches) > 1, "multiple trusted publication comments exist")
    return matches[0] if matches else None
