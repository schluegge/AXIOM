from __future__ import annotations

import hashlib
import io
import json
import unittest
import zipfile

from axiom_review.publisher import (
    ArtifactLimits,
    PublicationIdentity,
    WorkflowRunIdentity,
    inspect_publication_archive,
    resolve_publication_identity,
)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _run() -> WorkflowRunIdentity:
    return WorkflowRunIdentity(
        repository="schluegge/AXIOM",
        reviewed_head_sha="2" * 40,
        workflow_run_id=100,
        workflow_run_attempt=1,
        workflow_name="AXIOM deterministic review",
        workflow_run_url="https://github.com/schluegge/AXIOM/actions/runs/100",
        artifact_name="axiom-deterministic-review-100",
        pull_request_number_hint=35,
    )


def _archive(identity: PublicationIdentity) -> bytes:
    report = {
        "repository": identity.repository,
        "pull_request_number": identity.pull_request_number,
        "base_sha": "1" * 40,
        "reviewed_head_sha": identity.reviewed_head_sha,
    }
    report_bytes = _canonical(report)
    summary_bytes = b"summary\n"
    envelope = {
        "document_kind": "axiom.automated-review.publication-envelope",
        "schema_version": "0.1.0",
        "repository": identity.repository,
        "pull_request_number": identity.pull_request_number,
        "base_sha": "1" * 40,
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
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("publication-envelope.json", _canonical(envelope))
        archive.writestr("review-report.json", report_bytes)
        archive.writestr("review-summary.md", summary_bytes)
    return output.getvalue()


class LivePullRequestStateTests(unittest.TestCase):
    def test_commit_association_survives_a_newer_live_pr_head(self) -> None:
        identity = resolve_publication_identity(
            _run(),
            [{"number": 35, "head": {"sha": "3" * 40}, "base": {"sha": "9" * 40}}],
        )
        self.assertEqual(identity.pull_request_number, 35)
        self.assertEqual(identity.reviewed_head_sha, "2" * 40)
        self.assertIsNone(identity.base_sha)

    def test_artifact_base_identity_is_not_bound_to_the_later_live_base(self) -> None:
        unresolved = resolve_publication_identity(
            _run(),
            [{"number": 35, "head": {"sha": "2" * 40}, "base": {"sha": "9" * 40}}],
        )
        limits = ArtifactLimits(
            max_archive_bytes=1_000_000,
            max_entries=16,
            max_file_bytes=500_000,
            max_total_uncompressed_bytes=1_000_000,
            max_compression_ratio=100,
            max_report_bytes=200_000,
            max_summary_bytes=100_000,
            max_comment_bytes=60_000,
        )
        bundle = inspect_publication_archive(_archive(unresolved), unresolved, limits)
        self.assertEqual(bundle.identity.base_sha, "1" * 40)
        self.assertEqual(bundle.report["base_sha"], "1" * 40)


if __name__ == "__main__":
    unittest.main()
