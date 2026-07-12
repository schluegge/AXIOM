from __future__ import annotations

import copy
from typing import Any

from axiom_review.freshness import (
    PublicationIdentity,
    SourceResult,
    publication_replacement_findings,
    validate_freshness,
)
from axiom_review.freshness_contract import (
    build_freshness_envelope,
    validate_freshness_envelope,
)

from .agent_b_support import check, require


CURRENT = "a" * 40
PREVIOUS = "b" * 40
DIGEST = "sha256:" + "c" * 64


def _codes(findings: list[Any]) -> set[str]:
    codes: set[str] = set()
    for finding in findings:
        if isinstance(finding, dict):
            codes.add(str(finding["code"]))
        else:
            codes.add(str(finding.code))
    return codes


def _source(
    source_id: str,
    *,
    conclusion: str = "passed",
    head_sha: str = CURRENT,
    run_id: int = 100,
    run_attempt: int = 1,
    artifact_name: str | None = None,
    artifact_digest: str | None = DIGEST,
) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        conclusion=conclusion,
        reviewed_head_sha=head_sha,
        run_id=run_id,
        run_attempt=run_attempt,
        artifact_name=artifact_name if artifact_name is not None else f"{source_id}.zip",
        artifact_digest=artifact_digest,
    )


def _identity(head_sha: str, run_id: int, run_attempt: int) -> PublicationIdentity:
    return PublicationIdentity(
        reviewed_head_sha=head_sha,
        run_id=run_id,
        run_attempt=run_attempt,
    )


def register() -> None:
    def clean_exact_head_accepted() -> str:
        findings = validate_freshness(
            CURRENT,
            [
                _source("axiom-proof", run_id=101),
                _source("roadmap-contract", run_id=102),
                _source("deterministic-review", run_id=103),
            ],
        )
        require(findings == [], f"clean exact-head evidence blocked: {findings}")
        return "current-head sources accepted"

    check("review-freshness-clean-exact-head-accepted", clean_exact_head_accepted)

    def stale_workflow_metadata_blocked() -> str:
        findings = validate_freshness(
            CURRENT,
            [_source("axiom-proof", head_sha=PREVIOUS)],
        )
        require("AX-REV-FRESH-0102" in _codes(findings), f"stale source passed: {findings}")
        return "blocked with AX-REV-FRESH-0102"

    check("review-freshness-stale-workflow-metadata-blocked", stale_workflow_metadata_blocked)

    def mixed_head_sources_blocked() -> str:
        findings = validate_freshness(
            CURRENT,
            [
                _source("axiom-proof", head_sha=CURRENT),
                _source("deterministic-review", head_sha=PREVIOUS),
            ],
        )
        require("AX-REV-FRESH-0103" in _codes(findings), f"mixed heads passed: {findings}")
        return "blocked with AX-REV-FRESH-0103"

    check("review-freshness-mixed-head-sources-blocked", mixed_head_sources_blocked)

    def tampered_digest_blocked() -> str:
        envelope = build_freshness_envelope(
            repository="schluegge/AXIOM",
            pull_request_number=44,
            base_sha="d" * 40,
            current_head_sha=CURRENT,
            publisher_run_id=200,
            publisher_run_attempt=1,
            sources=[_source("axiom-proof")],
        )
        tampered = copy.deepcopy(envelope)
        tampered["sources"][0]["artifact_digest"] = "sha256:" + "e" * 64
        findings = validate_freshness_envelope(tampered)
        require(
            "AX-REV-FRESH-CONTRACT-2001" in _codes(findings),
            f"tampered envelope digest passed: {findings}",
        )
        return "blocked with AX-REV-FRESH-CONTRACT-2001"

    check("review-freshness-tampered-envelope-digest-blocked", tampered_digest_blocked)

    def rerun_identity_preserved() -> str:
        findings = validate_freshness(
            CURRENT,
            [_source("axiom-proof", run_id=300, run_attempt=2)],
        )
        require(findings == [], f"valid rerun attempt blocked: {findings}")
        replacement = publication_replacement_findings(
            current_head_sha=CURRENT,
            candidate=_identity(CURRENT, 300, 2),
            existing=_identity(CURRENT, 300, 1),
        )
        require(replacement == [], f"new rerun attempt rejected: {replacement}")
        return "same-head rerun attempt remains distinguishable"

    check("review-freshness-rerun-identity-preserved", rerun_identity_preserved)

    def delayed_older_publisher_blocked() -> str:
        findings = publication_replacement_findings(
            current_head_sha=CURRENT,
            candidate=_identity(CURRENT, 399, 3),
            existing=_identity(CURRENT, 400, 1),
        )
        require("AX-REV-FRESH-0201" in _codes(findings), f"older publisher replaced newer state: {findings}")
        return "blocked with AX-REV-FRESH-0201"

    check("review-freshness-delayed-older-publisher-blocked", delayed_older_publisher_blocked)

    def missing_proof_artifact_blocked() -> str:
        findings = validate_freshness(
            CURRENT,
            [
                _source(
                    "axiom-proof",
                    artifact_name="",
                    artifact_digest=None,
                )
            ],
        )
        require("AX-REV-FRESH-0105" in _codes(findings), f"missing proof artifact passed: {findings}")
        return "blocked with AX-REV-FRESH-0105"

    check("review-freshness-missing-proof-artifact-blocked", missing_proof_artifact_blocked)

    def terminal_nonpassing_states_blocked() -> str:
        for conclusion in ("cancelled", "skipped", "missing", "pending", "unavailable", "stale"):
            findings = validate_freshness(
                CURRENT,
                [_source("axiom-proof", conclusion=conclusion)],
            )
            require(
                "AX-REV-FRESH-0104" in _codes(findings),
                f"{conclusion} source was converted into passing evidence: {findings}",
            )
        return "all non-passing states remain blocking"

    check("review-freshness-nonpassing-states-blocked", terminal_nonpassing_states_blocked)
