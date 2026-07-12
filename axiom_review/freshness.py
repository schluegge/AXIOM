from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ARTIFACT_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_SOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ALLOWED_CONCLUSIONS = {
    "passed",
    "failed",
    "missing",
    "pending",
    "cancelled",
    "skipped",
    "unavailable",
    "stale",
}


@dataclass(frozen=True)
class SourceResult:
    """Identity and outcome of one independently executed review source."""

    source_id: str
    conclusion: str
    reviewed_head_sha: str
    run_id: int
    run_attempt: int
    artifact_name: str | None
    artifact_digest: str | None


@dataclass(frozen=True)
class PublicationIdentity:
    """Monotonic identity used to prevent stale publisher overwrites."""

    reviewed_head_sha: str
    run_id: int
    run_attempt: int


Finding = dict[str, Any]


def _finding(code: str, title: str, explanation: str, remediation: str) -> Finding:
    return {
        "code": code,
        "title": title,
        "explanation": explanation,
        "severity": "high",
        "authority": "blocking",
        "remediation": remediation,
    }


def _valid_execution_identity(source: SourceResult) -> bool:
    return (
        isinstance(source.source_id, str)
        and _SOURCE_ID.fullmatch(source.source_id) is not None
        and isinstance(source.run_id, int)
        and not isinstance(source.run_id, bool)
        and source.run_id > 0
        and isinstance(source.run_attempt, int)
        and not isinstance(source.run_attempt, bool)
        and source.run_attempt > 0
        and isinstance(source.reviewed_head_sha, str)
        and _SHA40.fullmatch(source.reviewed_head_sha) is not None
        and source.conclusion in _ALLOWED_CONCLUSIONS
    )


def _valid_artifact(source: SourceResult) -> bool:
    return (
        isinstance(source.artifact_name, str)
        and bool(source.artifact_name)
        and "/" not in source.artifact_name
        and "\\" not in source.artifact_name
        and source.artifact_name not in {".", ".."}
        and isinstance(source.artifact_digest, str)
        and _ARTIFACT_DIGEST.fullmatch(source.artifact_digest) is not None
    )


def validate_freshness(
    current_head_sha: str,
    sources: Iterable[SourceResult],
) -> list[Finding]:
    """Validate that all review sources are passing evidence for one exact head.

    The function is pure and deterministic. It does not fetch workflow data or
    trust PR-body text; callers must construct ``SourceResult`` values from
    independently verified workflow metadata and artifacts.
    """

    findings: list[Finding] = []
    materialized = list(sources)
    if _SHA40.fullmatch(current_head_sha) is None:
        findings.append(
            _finding(
                "AX-REV-FRESH-0101",
                "Current head identity is invalid",
                f"current head {current_head_sha!r} is not a lowercase 40-character SHA",
                "Resolve the current pull-request head from trusted workflow metadata.",
            )
        )
        return findings

    observed_heads: set[str] = set()
    for source in materialized:
        if not _valid_execution_identity(source):
            findings.append(
                _finding(
                    "AX-REV-FRESH-0101",
                    "Source execution identity is invalid",
                    f"source {source.source_id!r} lacks a valid source ID, conclusion, head SHA, run ID, or run attempt",
                    "Record the source result from trusted workflow metadata with positive run identity values.",
                )
            )
        elif source.reviewed_head_sha != current_head_sha:
            findings.append(
                _finding(
                    "AX-REV-FRESH-0102",
                    "Source result is stale",
                    f"source {source.source_id!r} reviewed {source.reviewed_head_sha}, not current head {current_head_sha}",
                    "Re-run the source against the exact current pull-request head.",
                )
            )
        if isinstance(source.reviewed_head_sha, str) and _SHA40.fullmatch(source.reviewed_head_sha):
            observed_heads.add(source.reviewed_head_sha)
        if source.conclusion != "passed":
            findings.append(
                _finding(
                    "AX-REV-FRESH-0104",
                    "Non-passing source cannot authorize a passing review",
                    f"source {source.source_id!r} concluded {source.conclusion!r}",
                    "Preserve the source state and wait for new passing exact-head evidence.",
                )
            )
        if not _valid_artifact(source):
            findings.append(
                _finding(
                    "AX-REV-FRESH-0105",
                    "Source artifact identity is missing or malformed",
                    f"source {source.source_id!r} lacks a portable artifact name and sha256 digest",
                    "Bind the source to the independently observed artifact name and SHA-256 digest.",
                )
            )

    if len(observed_heads) > 1:
        findings.append(
            _finding(
                "AX-REV-FRESH-0103",
                "Review sources contain mixed head identities",
                f"observed reviewed heads: {sorted(observed_heads)}",
                "Discard mixed evidence and re-run every required source for one exact head.",
            )
        )

    return sorted(
        findings,
        key=lambda item: (item["code"], item["title"], item["explanation"]),
    )


def _valid_publication_identity(identity: PublicationIdentity) -> bool:
    return (
        isinstance(identity.reviewed_head_sha, str)
        and _SHA40.fullmatch(identity.reviewed_head_sha) is not None
        and isinstance(identity.run_id, int)
        and not isinstance(identity.run_id, bool)
        and identity.run_id > 0
        and isinstance(identity.run_attempt, int)
        and not isinstance(identity.run_attempt, bool)
        and identity.run_attempt > 0
    )


def publication_replacement_findings(
    *,
    current_head_sha: str,
    candidate: PublicationIdentity,
    existing: PublicationIdentity | None,
) -> list[Finding]:
    """Return blockers when a publisher candidate must not replace current state."""

    if _SHA40.fullmatch(current_head_sha) is None or not _valid_publication_identity(candidate):
        return [
            _finding(
                "AX-REV-FRESH-0202",
                "Publisher target identity is invalid",
                "the current head or publisher candidate lacks valid exact-head execution identity",
                "Resolve the current head and publisher run identity from trusted workflow metadata.",
            )
        ]
    if candidate.reviewed_head_sha != current_head_sha:
        return [
            _finding(
                "AX-REV-FRESH-0202",
                "Publisher targets a stale pull-request head",
                f"candidate targets {candidate.reviewed_head_sha}, current head is {current_head_sha}",
                "Do not publish; start a new run for the exact current head.",
            )
        ]
    if existing is None:
        return []
    if not _valid_publication_identity(existing):
        return [
            _finding(
                "AX-REV-FRESH-0201",
                "Existing publication identity is invalid",
                "the existing summary cannot be ordered safely against the candidate",
                "Repair or remove the malformed managed summary before replacement.",
            )
        ]
    if existing.reviewed_head_sha != current_head_sha:
        return []
    if (candidate.run_id, candidate.run_attempt) <= (existing.run_id, existing.run_attempt):
        return [
            _finding(
                "AX-REV-FRESH-0201",
                "Delayed publisher cannot replace newer state",
                f"candidate execution {(candidate.run_id, candidate.run_attempt)} is not newer than existing {(existing.run_id, existing.run_attempt)}",
                "Leave the newer exact-head summary unchanged.",
            )
        ]
    return []
