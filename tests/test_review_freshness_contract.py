from __future__ import annotations

import unittest

from axiom_review.freshness import SourceResult
from axiom_review.freshness_contract import (
    build_freshness_envelope,
    render_freshness_markdown,
    validate_freshness_envelope,
)


CURRENT = "a" * 40
BASE = "b" * 40
DIGEST = "sha256:" + "c" * 64


def source(source_id: str, *, head: str = CURRENT, run_id: int = 100) -> SourceResult:
    return SourceResult(
        source_id=source_id,
        conclusion="passed",
        reviewed_head_sha=head,
        run_id=run_id,
        run_attempt=1,
        artifact_name=f"{source_id}.zip",
        artifact_digest=DIGEST,
    )


class FreshnessEnvelopeContractTests(unittest.TestCase):
    def envelope(self):
        return build_freshness_envelope(
            repository="schluegge/AXIOM",
            pull_request_number=44,
            base_sha=BASE,
            current_head_sha=CURRENT,
            publisher_run_id=200,
            publisher_run_attempt=2,
            sources=[
                source("axiom-proof", run_id=101),
                source("deterministic-review", run_id=102),
            ],
        )

    def test_current_exact_head_envelope_validates(self) -> None:
        envelope = self.envelope()
        self.assertEqual(envelope["schema_version"], "0.2.0")
        self.assertEqual(validate_freshness_envelope(envelope), [])

    def test_semantic_digest_detects_tampering(self) -> None:
        envelope = self.envelope()
        envelope["publisher_run_attempt"] = 3
        self.assertIn(
            "AX-REV-FRESH-CONTRACT-2001",
            {item.code for item in validate_freshness_envelope(envelope)},
        )

    def test_stale_source_is_rejected(self) -> None:
        envelope = build_freshness_envelope(
            repository="schluegge/AXIOM",
            pull_request_number=44,
            base_sha=BASE,
            current_head_sha=CURRENT,
            publisher_run_id=200,
            publisher_run_attempt=1,
            sources=[source("axiom-proof", head="d" * 40)],
        )
        self.assertIn(
            "AX-REV-FRESH-0102",
            {item.code for item in validate_freshness_envelope(envelope)},
        )

    def test_markdown_exposes_exact_execution_identity(self) -> None:
        markdown = render_freshness_markdown(self.envelope())
        self.assertIn(f"Current head SHA: `{CURRENT}`", markdown)
        self.assertIn("Publisher execution: `200/2`", markdown)
        self.assertIn("axiom-proof", markdown)
        self.assertIn("`101/1`", markdown)
        self.assertIn(DIGEST, markdown)


if __name__ == "__main__":
    unittest.main()
