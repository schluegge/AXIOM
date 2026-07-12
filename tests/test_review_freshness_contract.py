from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from axiom_review.freshness import SourceResult
from axiom_review.freshness_contract import (
    build_freshness_envelope,
    render_freshness_markdown,
    validate_freshness_envelope,
)
from tools.run_deterministic_review import write_freshness_artifacts


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

    def test_workflow_writer_binds_proof_and_gate_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            report = output / "review-report.json"
            report.write_text('{"status":"passed"}\n', encoding="utf-8")
            envelope_path, markdown_path = write_freshness_artifacts(
                output_dir=output,
                report_path=report,
                repository="schluegge/AXIOM",
                pull_request_number=44,
                base_sha=BASE,
                head_sha=CURRENT,
                workflow_run_id=300,
                workflow_run_attempt=2,
                proof_artifact_name="axiom-repo-proof-300.zip",
                proof_artifact_digest=DIGEST,
            )
            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            self.assertEqual(validate_freshness_envelope(envelope), [])
            self.assertEqual(
                [item["source_id"] for item in envelope["sources"]],
                ["axiom-proof", "deterministic-review"],
            )
            self.assertEqual(envelope["publisher_run_id"], 300)
            self.assertIn(CURRENT, markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
