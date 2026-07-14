from __future__ import annotations

import hashlib
import io
import json
import unittest
import zipfile

from axiom_review.publisher import (
    ArtifactLimits,
    PublicationIdentity,
    inspect_publication_archive,
)


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


class RetainedProofArtifactTests(unittest.TestCase):
    def test_known_retained_proof_zip_can_exceed_auxiliary_file_limit(self) -> None:
        identity = PublicationIdentity(
            repository="schluegge/AXIOM",
            pull_request_number=35,
            base_sha="1" * 40,
            reviewed_head_sha="2" * 40,
            workflow_run_id=425,
            workflow_run_attempt=1,
            workflow_name="AXIOM deterministic review",
            workflow_run_url="https://github.com/schluegge/AXIOM/actions/runs/425",
            artifact_name="axiom-deterministic-review-425",
        )
        report = {
            "repository": identity.repository,
            "pull_request_number": identity.pull_request_number,
            "base_sha": identity.base_sha,
            "reviewed_head_sha": identity.reviewed_head_sha,
        }
        report_bytes = _canonical_json(report)
        summary_bytes = b"summary\n"
        envelope = {
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
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("publication-envelope.json", _canonical_json(envelope))
            archive.writestr("review-report.json", report_bytes)
            archive.writestr("review-summary.md", summary_bytes)
            archive.writestr(
                f"axiom-repo-proof-{identity.workflow_run_id}.zip",
                b"p" * 1_500_000,
            )

        limits = ArtifactLimits(
            max_archive_bytes=2_000_000,
            max_entries=16,
            max_file_bytes=1_000_000,
            max_total_uncompressed_bytes=2_000_000,
            max_compression_ratio=50,
            max_report_bytes=200_000,
            max_summary_bytes=100_000,
            max_comment_bytes=60_000,
        )

        bundle = inspect_publication_archive(output.getvalue(), identity, limits)
        self.assertEqual(bundle.identity, identity)


if __name__ == "__main__":
    unittest.main()
