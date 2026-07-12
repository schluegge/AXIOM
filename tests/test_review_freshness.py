from __future__ import annotations

import unittest

from axiom_review.freshness import (
    PublicationIdentity,
    SourceResult,
    publication_replacement_findings,
    validate_freshness,
)


CURRENT = "a" * 40
PREVIOUS = "b" * 40
DIGEST = "sha256:" + "c" * 64


def source(
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


class FreshnessValidationTests(unittest.TestCase):
    def codes(self, findings) -> set[str]:
        return {finding["code"] for finding in findings}

    def test_complete_current_head_sources_pass(self) -> None:
        findings = validate_freshness(
            CURRENT,
            [
                source("axiom-proof", run_id=101),
                source("roadmap-contract", run_id=102),
                source("deterministic-review", run_id=103),
                source("advisory-review", run_id=104),
            ],
        )
        self.assertEqual(findings, [])

    def test_previous_head_is_stale(self) -> None:
        findings = validate_freshness(
            CURRENT,
            [source("axiom-proof", head_sha=PREVIOUS)],
        )
        self.assertIn("AX-REV-FRESH-0102", self.codes(findings))

    def test_mixed_source_heads_fail(self) -> None:
        findings = validate_freshness(
            CURRENT,
            [
                source("axiom-proof"),
                source("deterministic-review", head_sha=PREVIOUS),
            ],
        )
        self.assertIn("AX-REV-FRESH-0103", self.codes(findings))

    def test_cancelled_and_skipped_sources_cannot_pass(self) -> None:
        for conclusion in ("cancelled", "skipped", "missing", "pending", "unavailable", "stale"):
            with self.subTest(conclusion=conclusion):
                findings = validate_freshness(
                    CURRENT,
                    [source("axiom-proof", conclusion=conclusion)],
                )
                self.assertIn("AX-REV-FRESH-0104", self.codes(findings))

    def test_missing_artifact_digest_fails(self) -> None:
        findings = validate_freshness(
            CURRENT,
            [source("axiom-proof", artifact_digest=None)],
        )
        self.assertIn("AX-REV-FRESH-0105", self.codes(findings))

    def test_missing_artifact_name_fails_independently(self) -> None:
        findings = validate_freshness(
            CURRENT,
            [source("axiom-proof", artifact_name="", artifact_digest=DIGEST)],
        )
        self.assertIn("AX-REV-FRESH-0105", self.codes(findings))

    def test_malformed_execution_identity_fails_closed(self) -> None:
        findings = validate_freshness(
            CURRENT,
            [source("axiom-proof", run_id=0, run_attempt=0)],
        )
        self.assertIn("AX-REV-FRESH-0101", self.codes(findings))

    def test_rerun_attempt_preserves_head_identity(self) -> None:
        findings = validate_freshness(
            CURRENT,
            [source("axiom-proof", run_id=100, run_attempt=2)],
        )
        self.assertEqual(findings, [])


class PublicationOrderingTests(unittest.TestCase):
    def codes(self, findings) -> set[str]:
        return {finding["code"] for finding in findings}

    def identity(self, head_sha: str, run_id: int, run_attempt: int) -> PublicationIdentity:
        return PublicationIdentity(
            reviewed_head_sha=head_sha,
            run_id=run_id,
            run_attempt=run_attempt,
        )

    def test_newer_run_may_replace_current_summary(self) -> None:
        findings = publication_replacement_findings(
            current_head_sha=CURRENT,
            candidate=self.identity(CURRENT, 201, 1),
            existing=self.identity(CURRENT, 200, 1),
        )
        self.assertEqual(findings, [])

    def test_newer_attempt_of_same_run_may_replace_current_summary(self) -> None:
        findings = publication_replacement_findings(
            current_head_sha=CURRENT,
            candidate=self.identity(CURRENT, 200, 2),
            existing=self.identity(CURRENT, 200, 1),
        )
        self.assertEqual(findings, [])

    def test_delayed_older_publisher_cannot_replace_newer_summary(self) -> None:
        findings = publication_replacement_findings(
            current_head_sha=CURRENT,
            candidate=self.identity(CURRENT, 199, 3),
            existing=self.identity(CURRENT, 200, 1),
        )
        self.assertIn("AX-REV-FRESH-0201", self.codes(findings))

    def test_force_updated_branch_rejects_previous_head_publisher(self) -> None:
        findings = publication_replacement_findings(
            current_head_sha=CURRENT,
            candidate=self.identity(PREVIOUS, 201, 1),
            existing=self.identity(PREVIOUS, 200, 1),
        )
        self.assertIn("AX-REV-FRESH-0202", self.codes(findings))

    def test_rapid_successive_push_rejects_old_run_even_if_run_id_is_newer(self) -> None:
        findings = publication_replacement_findings(
            current_head_sha=CURRENT,
            candidate=self.identity(PREVIOUS, 300, 1),
            existing=self.identity(CURRENT, 200, 1),
        )
        self.assertIn("AX-REV-FRESH-0202", self.codes(findings))


if __name__ == "__main__":
    unittest.main()
