from __future__ import annotations

import hashlib
import io
import json
import unittest
import zipfile

from axiom_review.publisher import (
    ArtifactLimits,
    ExistingPublication,
    GitHubRestApi,
    HttpResponse,
    PublicationDecision,
    PublicationIdentity,
    WorkflowRunIdentity,
    PublicationRejected,
    create_publication_envelope,
    find_existing_publication_comment,
    inspect_publication_archive,
    parse_existing_publication,
    parse_workflow_run_event,
    publication_decision,
    render_publication_comment,
    resolve_publication_identity,
)


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def fixture_identity(*, head: str = "2" * 40, run_id: int = 100, attempt: int = 1) -> PublicationIdentity:
    return PublicationIdentity(
        repository="schluegge/AXIOM",
        pull_request_number=35,
        base_sha="1" * 40,
        reviewed_head_sha=head,
        workflow_run_id=run_id,
        workflow_run_attempt=attempt,
        workflow_name="AXIOM deterministic review",
        workflow_run_url=f"https://github.com/schluegge/AXIOM/actions/runs/{run_id}",
        artifact_name=f"axiom-deterministic-review-{run_id}",
    )


def fixture_report(identity: PublicationIdentity) -> dict[str, object]:
    return {
        "document_kind": "axiom.automated-review.report",
        "schema_version": "0.1.0",
        "report_id": f"deterministic-review-{identity.reviewed_head_sha}",
        "repository": identity.repository,
        "pull_request_number": identity.pull_request_number,
        "base_sha": identity.base_sha,
        "reviewed_head_sha": identity.reviewed_head_sha,
        "generated_at": "2026-07-12T08:00:00Z",
        "reviewer_class": "deterministic",
        "status": "passed",
        "findings": [],
        "checks": [{"check_id": "fixture", "title": "Fixture", "input_sha256": "3" * 64, "conclusion": "passed", "evidence_path": "checks/fixture.json"}],
        "known_unreviewed": [],
        "unavailable": [],
        "semantic_sha256": "4" * 64,
    }


def make_archive(
    identity: PublicationIdentity,
    *,
    report: dict[str, object] | None = None,
    summary: str = "## AXIOM automated review\n\n- Status: **PASSED**\n",
    extra_entries: list[tuple[str, bytes]] | None = None,
    envelope_overrides: dict[str, object] | None = None,
) -> bytes:
    report_bytes = canonical_json(report or fixture_report(identity))
    summary_bytes = summary.encode("utf-8")
    envelope: dict[str, object] = {
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
    if envelope_overrides:
        envelope.update(envelope_overrides)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("review-report.json", report_bytes)
        archive.writestr("review-summary.md", summary_bytes)
        archive.writestr("publication-envelope.json", canonical_json(envelope))
        archive.writestr("checks/fixture.json", b"{}\n")
        for name, payload in extra_entries or []:
            archive.writestr(name, payload)
    return output.getvalue()


class PublicationEventTests(unittest.TestCase):
    def _workflow_event(self, pull_requests: list[dict[str, object]]) -> dict[str, object]:
        return {
            "action": "completed",
            "repository": {"full_name": "schluegge/AXIOM"},
            "workflow_run": {
                "id": 100,
                "run_attempt": 2,
                "name": "AXIOM deterministic review",
                "event": "pull_request",
                "status": "completed",
                "html_url": "https://github.com/schluegge/AXIOM/actions/runs/100",
                "head_sha": "2" * 40,
                "pull_requests": pull_requests,
            },
        }

    def test_completed_workflow_run_records_optional_pull_request_hint(self) -> None:
        run = parse_workflow_run_event(
            self._workflow_event([{"number": 35, "head": {"sha": "2" * 40}}]),
            expected_workflow_name="AXIOM deterministic review",
        )
        self.assertEqual(
            run,
            WorkflowRunIdentity(
                repository="schluegge/AXIOM",
                reviewed_head_sha="2" * 40,
                workflow_run_id=100,
                workflow_run_attempt=2,
                workflow_name="AXIOM deterministic review",
                workflow_run_url="https://github.com/schluegge/AXIOM/actions/runs/100",
                artifact_name="axiom-deterministic-review-100",
                pull_request_number_hint=35,
            ),
        )

    def test_fork_style_workflow_run_without_pull_request_list_is_accepted(self) -> None:
        run = parse_workflow_run_event(
            self._workflow_event([]),
            expected_workflow_name="AXIOM deterministic review",
        )
        self.assertIsNone(run.pull_request_number_hint)
        self.assertEqual(run.reviewed_head_sha, "2" * 40)

    def test_associated_pull_request_resolves_run_bound_identity_before_artifact_base_binding(self) -> None:
        run = parse_workflow_run_event(
            self._workflow_event([]),
            expected_workflow_name="AXIOM deterministic review",
        )
        identity = resolve_publication_identity(
            run,
            [{"number": 35, "head": {"sha": "2" * 40}, "base": {"sha": "1" * 40}}],
        )
        self.assertEqual(identity.repository, "schluegge/AXIOM")
        self.assertEqual(identity.pull_request_number, 35)
        self.assertIsNone(identity.base_sha)
        self.assertEqual(identity.reviewed_head_sha, "2" * 40)
        self.assertEqual(identity.workflow_run_id, 100)
        self.assertEqual(identity.workflow_run_attempt, 2)

    def test_associated_pull_request_resolution_fails_closed_on_none_or_many(self) -> None:
        run = parse_workflow_run_event(
            self._workflow_event([]),
            expected_workflow_name="AXIOM deterministic review",
        )
        for associated in (
            [],
            [
                {"number": 35, "head": {"sha": "2" * 40}, "base": {"sha": "1" * 40}},
                {"number": 36, "head": {"sha": "2" * 40}, "base": {"sha": "1" * 40}},
            ],
        ):
            with self.subTest(count=len(associated)):
                with self.assertRaisesRegex(PublicationRejected, "exactly one associated pull request"):
                    resolve_publication_identity(run, associated)

    def test_event_hint_filters_commit_associations_without_binding_mutable_live_head(self) -> None:
        run = parse_workflow_run_event(
            self._workflow_event([{"number": 35, "head": {"sha": "2" * 40}}]),
            expected_workflow_name="AXIOM deterministic review",
        )
        identity = resolve_publication_identity(
            run,
            [
                {"number": 34, "head": {"sha": "2" * 40}, "base": {"sha": "1" * 40}},
                {"number": 35, "head": {"sha": "2" * 40}, "base": {"sha": "1" * 40}},
            ],
        )
        self.assertEqual(identity.pull_request_number, 35)
        advanced = resolve_publication_identity(
            run,
            [{"number": 35, "head": {"sha": "9" * 40}, "base": {"sha": "8" * 40}}],
        )
        self.assertEqual(advanced.pull_request_number, 35)
        self.assertEqual(advanced.reviewed_head_sha, "2" * 40)
        self.assertIsNone(advanced.base_sha)

    def test_envelope_binds_report_and_summary_bytes(self) -> None:
        identity = fixture_identity()
        report_bytes = canonical_json(fixture_report(identity))
        summary_bytes = b"summary\n"
        envelope = create_publication_envelope(identity, report_bytes, summary_bytes)
        self.assertEqual(envelope["report_sha256"], hashlib.sha256(report_bytes).hexdigest())
        self.assertEqual(envelope["summary_sha256"], hashlib.sha256(summary_bytes).hexdigest())
        self.assertEqual(envelope["workflow_run_id"], identity.workflow_run_id)

    def test_rendered_marker_round_trips_existing_publication(self) -> None:
        identity = fixture_identity(run_id=700, attempt=3)
        body = render_publication_comment(
            identity,
            current_head_sha=identity.reviewed_head_sha,
            deterministic_summary="clean",
            max_comment_bytes=10_000,
        )
        self.assertEqual(
            parse_existing_publication(body),
            ExistingPublication(identity.reviewed_head_sha, identity.reviewed_head_sha, 700, 3),
        )


class PublicationArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = fixture_identity()
        self.limits = ArtifactLimits(
            max_archive_bytes=2_000_000,
            max_entries=32,
            max_file_bytes=1_000_000,
            max_total_uncompressed_bytes=2_000_000,
            max_compression_ratio=50,
            max_report_bytes=200_000,
            max_summary_bytes=100_000,
            max_comment_bytes=60_000,
        )

    def test_valid_archive_is_read_without_extracting_files(self) -> None:
        bundle = inspect_publication_archive(make_archive(self.identity), self.identity, self.limits)
        self.assertEqual(bundle.identity, self.identity)
        self.assertEqual(bundle.report["repository"], self.identity.repository)
        self.assertIn("Status: **PASSED**", bundle.summary)

    def test_path_traversal_is_rejected(self) -> None:
        archive = make_archive(self.identity, extra_entries=[("../escape.txt", b"owned")])
        with self.assertRaisesRegex(PublicationRejected, "unsafe archive path"):
            inspect_publication_archive(archive, self.identity, self.limits)

    def test_duplicate_file_is_rejected(self) -> None:
        archive = make_archive(self.identity, extra_entries=[("review-report.json", b"{}")])
        with self.assertRaisesRegex(PublicationRejected, "duplicate archive entry"):
            inspect_publication_archive(archive, self.identity, self.limits)

    def test_decompression_bomb_is_rejected(self) -> None:
        limits = ArtifactLimits(**{**self.limits.__dict__, "max_total_uncompressed_bytes": 100_000})
        archive = make_archive(self.identity, extra_entries=[("checks/bomb.txt", b"0" * 200_000)])
        with self.assertRaisesRegex(PublicationRejected, "uncompressed size"):
            inspect_publication_archive(archive, self.identity, limits)

    def test_oversized_report_is_rejected(self) -> None:
        report = fixture_report(self.identity)
        report["padding"] = "x" * 250_000
        archive = make_archive(self.identity, report=report)
        with self.assertRaisesRegex(PublicationRejected, "report exceeds"):
            inspect_publication_archive(archive, self.identity, self.limits)

    def test_tampered_report_digest_is_rejected(self) -> None:
        archive = make_archive(self.identity, envelope_overrides={"report_sha256": "0" * 64})
        with self.assertRaisesRegex(PublicationRejected, "report digest mismatch"):
            inspect_publication_archive(archive, self.identity, self.limits)

    def test_repository_or_pr_mismatch_is_rejected(self) -> None:
        archive = make_archive(self.identity, envelope_overrides={"repository": "foreign/repo"})
        with self.assertRaisesRegex(PublicationRejected, "envelope identity mismatch"):
            inspect_publication_archive(archive, self.identity, self.limits)


class GitHubRestApiTests(unittest.TestCase):
    def test_artifact_redirect_does_not_forward_authorization(self) -> None:
        calls: list[tuple[str, dict[str, str], bool]] = []

        def transport(method, url, headers, body, max_bytes, follow_redirects):
            calls.append((url, dict(headers), follow_redirects))
            if len(calls) == 1:
                return HttpResponse(302, {"Location": "https://signed.invalid/artifact.zip"}, b"")
            return HttpResponse(200, {}, b"zip-bytes")

        api = GitHubRestApi("secret-token", transport=transport)
        self.assertEqual(api.download_artifact("schluegge/AXIOM", 9, max_bytes=100), b"zip-bytes")
        self.assertIn("Authorization", calls[0][1])
        self.assertNotIn("Authorization", calls[1][1])
        self.assertFalse(calls[0][2])
        self.assertTrue(calls[1][2])

    def test_artifact_download_rejects_non_https_redirect(self) -> None:
        def transport(method, url, headers, body, max_bytes, follow_redirects):
            return HttpResponse(302, {"Location": "http://attacker.invalid/artifact.zip"}, b"")

        api = GitHubRestApi("secret-token", transport=transport)
        with self.assertRaisesRegex(PublicationRejected, "HTTPS"):
            api.download_artifact("schluegge/AXIOM", 9, max_bytes=100)


class PublicationCommentSelectionTests(unittest.TestCase):
    def test_forged_human_marker_is_ignored(self) -> None:
        identity = fixture_identity()
        body = render_publication_comment(
            identity,
            current_head_sha=identity.reviewed_head_sha,
            deterministic_summary="clean",
            max_comment_bytes=10_000,
        )
        comments = [
            {"id": 1, "body": body, "user": {"login": "attacker", "type": "User"}},
        ]
        self.assertIsNone(find_existing_publication_comment(comments))

    def test_single_actions_bot_marker_is_selected(self) -> None:
        identity = fixture_identity()
        body = render_publication_comment(
            identity,
            current_head_sha=identity.reviewed_head_sha,
            deterministic_summary="clean",
            max_comment_bytes=10_000,
        )
        selected = find_existing_publication_comment(
            [{"id": 44, "body": body, "user": {"login": "github-actions[bot]", "type": "Bot"}}]
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected[0], 44)
        self.assertEqual(selected[1].workflow_run_id, identity.workflow_run_id)

    def test_duplicate_actions_bot_markers_fail_closed(self) -> None:
        identity = fixture_identity()
        body = render_publication_comment(
            identity,
            current_head_sha=identity.reviewed_head_sha,
            deterministic_summary="clean",
            max_comment_bytes=10_000,
        )
        comments = [
            {"id": 44, "body": body, "user": {"login": "github-actions[bot]", "type": "Bot"}},
            {"id": 45, "body": body, "user": {"login": "github-actions[bot]", "type": "Bot"}},
        ]
        with self.assertRaisesRegex(PublicationRejected, "multiple trusted publication comments"):
            find_existing_publication_comment(comments)


class PublicationOrderingTests(unittest.TestCase):
    def test_current_head_replaces_stale_existing_result(self) -> None:
        incoming = fixture_identity(head="b" * 40, run_id=200)
        existing = ExistingPublication(
            reviewed_head_sha="a" * 40,
            current_head_sha="b" * 40,
            workflow_run_id=100,
            workflow_run_attempt=1,
        )
        self.assertEqual(
            publication_decision(incoming, current_head_sha="b" * 40, existing=existing),
            PublicationDecision.UPDATE_CURRENT,
        )

    def test_older_stale_result_cannot_overwrite_current_result(self) -> None:
        incoming = fixture_identity(head="a" * 40, run_id=100)
        existing = ExistingPublication(
            reviewed_head_sha="b" * 40,
            current_head_sha="b" * 40,
            workflow_run_id=200,
            workflow_run_attempt=1,
        )
        self.assertEqual(
            publication_decision(incoming, current_head_sha="b" * 40, existing=existing),
            PublicationDecision.SKIP_OLDER,
        )

    def test_older_current_result_cannot_overwrite_newer_current_result(self) -> None:
        incoming = fixture_identity(head="b" * 40, run_id=100, attempt=1)
        existing = ExistingPublication(
            reviewed_head_sha="b" * 40,
            current_head_sha="b" * 40,
            workflow_run_id=200,
            workflow_run_attempt=1,
        )
        self.assertEqual(
            publication_decision(incoming, current_head_sha="b" * 40, existing=existing),
            PublicationDecision.SKIP_OLDER,
        )

    def test_same_run_is_idempotently_updated(self) -> None:
        incoming = fixture_identity(head="b" * 40, run_id=200, attempt=2)
        existing = ExistingPublication(
            reviewed_head_sha="b" * 40,
            current_head_sha="b" * 40,
            workflow_run_id=200,
            workflow_run_attempt=2,
        )
        self.assertEqual(
            publication_decision(incoming, current_head_sha="b" * 40, existing=existing),
            PublicationDecision.UPDATE_CURRENT,
        )

    def test_comment_is_bounded_and_links_full_artifact(self) -> None:
        identity = fixture_identity()
        summary = "finding\n" * 20_000
        body = render_publication_comment(
            identity,
            current_head_sha=identity.reviewed_head_sha,
            deterministic_summary=summary,
            max_comment_bytes=10_000,
        )
        self.assertLessEqual(len(body.encode("utf-8")), 10_000)
        self.assertIn("## Deterministic review", body)
        self.assertIn("## Advisory AI review", body)
        self.assertIn("#artifacts", body)
        self.assertIn("truncated", body.lower())

    def test_commit_association_api_uses_exact_head_endpoint(self) -> None:
        calls: list[str] = []

        def transport(method, url, headers, body, max_bytes, follow_redirects):
            calls.append(url)
            return HttpResponse(200, {}, b'[{"number":35,"head":{"sha":"' + b'2' * 40 + b'"},"base":{"sha":"' + b'1' * 40 + b'"}}]')

        api = GitHubRestApi("token", transport=transport)
        pulls = api.list_pull_requests_for_commit("schluegge/AXIOM", "2" * 40)
        self.assertEqual([item["number"] for item in pulls], [35])
        self.assertTrue(calls[0].endswith("/repos/schluegge/AXIOM/commits/" + "2" * 40 + "/pulls?per_page=100"))


if __name__ == "__main__":
    unittest.main()
