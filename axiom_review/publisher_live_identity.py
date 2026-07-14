from __future__ import annotations

from dataclasses import replace
from typing import Any

from .publisher_artifact import (
    _read_archive_entries,
    inspect_publication_archive as _inspect_publication_archive,
)
from .publisher_core import (
    ArtifactLimits,
    PublicationBundle,
    PublicationIdentity,
    WorkflowRunIdentity,
    _SHA40,
    _read_json_object,
    _reject,
    _require_int,
    _require_str,
)


def resolve_publication_identity(
    run: WorkflowRunIdentity,
    associated_pull_requests: list[dict[str, Any]],
) -> PublicationIdentity:
    """Bind a workflow run to one commit-associated PR without trusting live refs.

    GitHub's commit-associated pull-request response contains the PR's current
    head and base, which may have advanced after the reviewed workflow run. The
    endpoint association and optional workflow-run PR-number hint identify the
    PR; the reviewed head remains bound to the trusted workflow_run event, and
    the historical base is recovered from the validated publication artifact.
    """

    _reject(not isinstance(associated_pull_requests, list), "associated pull requests must be an array")
    matches: list[dict[str, Any]] = []
    for pull_request in associated_pull_requests:
        if not isinstance(pull_request, dict):
            continue
        number = pull_request.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            continue
        if run.pull_request_number_hint is not None and number != run.pull_request_number_hint:
            continue
        matches.append(pull_request)
    _reject(
        len(matches) != 1,
        f"expected exactly one associated pull request for reviewed head; found {len(matches)}",
    )
    number = _require_int(matches[0].get("number"), "associated pull request number")
    return PublicationIdentity(
        repository=run.repository,
        pull_request_number=number,
        base_sha=None,  # type: ignore[arg-type] - resolved from the validated run artifact below
        reviewed_head_sha=run.reviewed_head_sha,
        workflow_run_id=run.workflow_run_id,
        workflow_run_attempt=run.workflow_run_attempt,
        workflow_name=run.workflow_name,
        workflow_run_url=run.workflow_run_url,
        artifact_name=run.artifact_name,
    )


def inspect_publication_archive(
    archive_bytes: bytes,
    expected_identity: PublicationIdentity,
    limits: ArtifactLimits,
) -> PublicationBundle:
    """Validate the archive using trusted run identity and artifact-bound base SHA."""

    if expected_identity.base_sha is not None:
        return _inspect_publication_archive(archive_bytes, expected_identity, limits)

    entries = _read_archive_entries(archive_bytes, limits, expected_identity)
    envelope = _read_json_object(entries["publication-envelope.json"], "publication envelope")

    repository = _require_str(envelope.get("repository"), "envelope repository")
    pull_request_number = _require_int(
        envelope.get("pull_request_number"), "envelope pull request number"
    )
    reviewed_head_sha = _require_str(
        envelope.get("reviewed_head_sha"), "envelope reviewed head SHA", pattern=_SHA40
    )
    workflow_run_id = _require_int(envelope.get("workflow_run_id"), "envelope workflow run id")
    workflow_run_attempt = _require_int(
        envelope.get("workflow_run_attempt"), "envelope workflow run attempt"
    )
    workflow_name = _require_str(envelope.get("workflow_name"), "envelope workflow name")
    artifact_name = _require_str(envelope.get("artifact_name"), "envelope artifact name")
    base_sha = _require_str(envelope.get("base_sha"), "envelope base SHA", pattern=_SHA40)

    _reject(repository != expected_identity.repository, "envelope repository mismatch")
    _reject(
        pull_request_number != expected_identity.pull_request_number,
        "envelope pull request mismatch",
    )
    _reject(reviewed_head_sha != expected_identity.reviewed_head_sha, "envelope reviewed head mismatch")
    _reject(workflow_run_id != expected_identity.workflow_run_id, "envelope workflow run mismatch")
    _reject(
        workflow_run_attempt != expected_identity.workflow_run_attempt,
        "envelope workflow attempt mismatch",
    )
    _reject(workflow_name != expected_identity.workflow_name, "envelope workflow name mismatch")
    _reject(artifact_name != expected_identity.artifact_name, "envelope artifact name mismatch")

    bound_identity = replace(expected_identity, base_sha=base_sha)
    return _inspect_publication_archive(archive_bytes, bound_identity, limits)
