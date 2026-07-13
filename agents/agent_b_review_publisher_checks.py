from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import yaml

from axiom_review.publisher import (
    ArtifactLimits,
    ExistingPublication,
    GitHubRestApi,
    HttpResponse,
    PublicationDecision,
    PublicationIdentity,
    PublicationRejected,
    WorkflowRunIdentity,
    create_publication_envelope,
    find_existing_publication_comment,
    inspect_publication_archive,
    publication_decision,
    render_publication_comment,
    resolve_publication_identity,
)

from .agent_b_support import check, require


def _identity(*, head: str = "2" * 40, run_id: int = 100) -> PublicationIdentity:
    return PublicationIdentity(
        repository="schluegge/AXIOM",
        pull_request_number=35,
        base_sha="1" * 40,
        reviewed_head_sha=head,
        workflow_run_id=run_id,
        workflow_run_attempt=1,
        workflow_name="AXIOM deterministic review",
        workflow_run_url=f"https://github.com/schluegge/AXIOM/actions/runs/{run_id}",
        artifact_name=f"axiom-deterministic-review-{run_id}",
    )


def _report(identity: PublicationIdentity) -> dict[str, Any]:
    return {
        "document_kind": "axiom.automated-review.report",
        "schema_version": "0.1.0",
        "report_id": "agent-b",
        "repository": identity.repository,
        "pull_request_number": identity.pull_request_number,
        "base_sha": identity.base_sha,
        "reviewed_head_sha": identity.reviewed_head_sha,
        "generated_at": "2026-07-12T08:00:00Z",
        "reviewer_class": "deterministic",
        "status": "passed",
        "findings": [],
        "checks": [],
        "known_unreviewed": [],
        "unavailable": [],
        "semantic_sha256": "0" * 64,
    }


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _archive(identity: PublicationIdentity, extras: list[tuple[str, bytes]] | None = None) -> bytes:
    report_bytes = _json_bytes(_report(identity))
    summary_bytes = b"summary\n"
    envelope = create_publication_envelope(identity, report_bytes, summary_bytes)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("review-report.json", report_bytes)
        archive.writestr("review-summary.md", summary_bytes)
        archive.writestr("publication-envelope.json", _json_bytes(envelope))
        for name, payload in extras or []:
            archive.writestr(name, payload)
    return output.getvalue()


def _limits() -> ArtifactLimits:
    return ArtifactLimits(2_000_000, 32, 1_000_000, 2_000_000, 100, 200_000, 100_000, 60_000)


def register() -> None:
    from . import agent_b_support as support

    root = support.ROOT

    def policy_protects_publisher() -> str:
        policy = json.loads((root / "review/policy/0.1.0/gate-policy.json").read_text(encoding="utf-8"))
        protected = set(policy["protected_paths"])
        required = {
            ".github/workflows/publish-review.yml",
            "axiom_review/publisher.py",
            "axiom_review/publisher_core.py",
            "axiom_review/publisher_artifact.py",
            "axiom_review/publisher_github.py",
            "tools/create_review_publication_envelope.py",
            "tools/publish_review_summary.py",
            "review/contracts/0.1.0/publication-envelope.schema.json",
            "tests/test_review_publisher.py",
            "agents/agent_b_review_publisher_checks.py",
        }
        require(required <= protected, f"publisher paths missing from protected baseline: {sorted(required - protected)}")
        require(
            "agents.agent_b_review_publisher_checks" in policy["agent_b_registration_modules"],
            "publisher Agent B registration is not protected",
        )
        return "publisher implementation, tests, workflow, schema, and Agent B registration protected"

    check("review-publisher-policy-self-protection", policy_protects_publisher)

    def workflow_boundary() -> str:
        workflow = yaml.safe_load((root / ".github/workflows/publish-review.yml").read_text(encoding="utf-8"))
        require(isinstance(workflow, dict), "publisher workflow root is not an object")
        trigger = workflow.get(True, workflow.get("on"))
        require(isinstance(trigger, dict) and set(trigger) == {"workflow_run"}, "publisher trigger is not workflow_run-only")
        permissions = workflow.get("permissions")
        require(
            permissions == {"actions": "read", "contents": "read", "pull-requests": "write"},
            f"publisher permissions widened or incomplete: {permissions!r}",
        )
        text = (root / ".github/workflows/publish-review.yml").read_text(encoding="utf-8")
        require("github.event.repository.default_branch" in text, "publisher does not pin checkout to the default branch")
        require("persist-credentials: false" in text, "publisher checkout persists credentials")
        require("pull_request_target" not in text, "publisher uses pull_request_target")
        require("github.event.workflow_run.head_sha" not in text, "publisher workflow directly checks out the PR head")
        return "workflow_run publisher has exact minimal permissions and default-branch checkout"

    check("review-publisher-trusted-workflow-boundary", workflow_boundary)

    def analysis_job_has_no_write_authority() -> str:
        workflow = yaml.safe_load((root / ".github/workflows/deterministic-review.yml").read_text(encoding="utf-8"))
        require(workflow.get("permissions") == {"contents": "read"}, "analysis workflow gained write permission")
        text = (root / ".github/workflows/deterministic-review.yml").read_text(encoding="utf-8")
        require("create_review_publication_envelope.py" in text, "analysis workflow does not create the identity envelope")
        require("secrets.GITHUB_TOKEN" not in text, "analysis workflow received a token secret")
        return "pull-request analysis remains read-only and uploads a bounded envelope"

    check("review-publisher-analysis-remains-unprivileged", analysis_job_has_no_write_authority)

    def fork_style_association_is_server_verified() -> str:
        run = WorkflowRunIdentity(
            repository="schluegge/AXIOM",
            reviewed_head_sha="2" * 40,
            workflow_run_id=100,
            workflow_run_attempt=1,
            workflow_name="AXIOM deterministic review",
            workflow_run_url="https://github.com/schluegge/AXIOM/actions/runs/100",
            artifact_name="axiom-deterministic-review-100",
            pull_request_number_hint=None,
        )
        identity = resolve_publication_identity(
            run,
            [{"number": 35, "head": {"sha": "2" * 40}, "base": {"sha": "1" * 40}}],
        )
        require(identity.pull_request_number == 35, "server-associated PR was not resolved")
        for associated in ([], [
            {"number": 35, "head": {"sha": "2" * 40}, "base": {"sha": "1" * 40}},
            {"number": 36, "head": {"sha": "2" * 40}, "base": {"sha": "1" * 40}},
        ]):
            try:
                resolve_publication_identity(run, associated)
            except PublicationRejected:
                continue
            raise AssertionError("ambiguous or missing commit association was accepted")
        return "empty fork-style event hints resolve only through one exact GitHub commit association"

    check("review-publisher-fork-association-fails-closed", fork_style_association_is_server_verified)

    def path_and_duplicate_attacks_blocked() -> str:
        identity = _identity()
        for extras, expected in (
            ([('../escape', b'x')], "unsafe archive path"),
            ([('review-report.json', b'{}')], "duplicate archive entry"),
        ):
            try:
                inspect_publication_archive(_archive(identity, extras), identity, _limits())
            except PublicationRejected as error:
                require(expected in str(error), f"wrong rejection for {extras!r}: {error}")
            else:
                raise AssertionError(f"archive attack passed: {extras!r}")
        return "path traversal and duplicate ZIP members rejected before extraction"

    check("review-publisher-archive-namespace-attacks-blocked", path_and_duplicate_attacks_blocked)

    def decompression_attack_blocked() -> str:
        identity = _identity()
        limits = ArtifactLimits(2_000_000, 32, 1_000_000, 100_000, 100, 200_000, 100_000, 60_000)
        try:
            inspect_publication_archive(
                _archive(identity, [("checks/bomb.txt", b"0" * 200_000)]),
                identity,
                limits,
            )
        except PublicationRejected as error:
            require("uncompressed size" in str(error), f"wrong decompression rejection: {error}")
        else:
            raise AssertionError("decompression bomb passed")
        return "bounded total decompressed bytes reject the bomb fixture"

    check("review-publisher-decompression-bomb-blocked", decompression_attack_blocked)

    def redirect_drops_authorization() -> str:
        calls: list[dict[str, str]] = []

        def transport(method, url, headers, body, max_bytes, follow_redirects):
            calls.append(dict(headers))
            if len(calls) == 1:
                return HttpResponse(302, {"Location": "https://signed.invalid/artifact.zip"}, b"")
            return HttpResponse(200, {}, b"zip")

        api = GitHubRestApi("secret", transport=transport)
        require(api.download_artifact("schluegge/AXIOM", 1, max_bytes=100) == b"zip", "download bytes changed")
        require("Authorization" in calls[0], "GitHub API request lacks authorization")
        require("Authorization" not in calls[1], "authorization leaked to signed artifact host")
        return "authorization is removed before following the signed artifact redirect"

    check("review-publisher-artifact-redirect-drops-token", redirect_drops_authorization)

    def forged_and_duplicate_comments_blocked() -> str:
        identity = _identity()
        body = render_publication_comment(
            identity,
            current_head_sha=identity.reviewed_head_sha,
            deterministic_summary="clean",
            max_comment_bytes=10_000,
        )
        forged = [{"id": 1, "body": body, "user": {"login": "attacker", "type": "User"}}]
        require(find_existing_publication_comment(forged) is None, "human marker forgery was trusted")
        duplicate = [
            {"id": 2, "body": body, "user": {"login": "github-actions[bot]", "type": "Bot"}},
            {"id": 3, "body": body, "user": {"login": "github-actions[bot]", "type": "Bot"}},
        ]
        try:
            find_existing_publication_comment(duplicate)
        except PublicationRejected:
            return "human forgery ignored and duplicate trusted markers fail closed"
        raise AssertionError("duplicate trusted publication comments were accepted")

    check("review-publisher-comment-marker-attacks-blocked", forged_and_duplicate_comments_blocked)

    def stale_rollback_blocked() -> str:
        incoming = _identity(head="b" * 40, run_id=100)
        existing = ExistingPublication("b" * 40, "b" * 40, 200, 1)
        decision = publication_decision(incoming, current_head_sha="b" * 40, existing=existing)
        require(decision is PublicationDecision.SKIP_OLDER, f"older current result was accepted: {decision}")
        stale = _identity(head="a" * 40, run_id=300)
        decision = publication_decision(stale, current_head_sha="b" * 40, existing=existing)
        require(decision is PublicationDecision.SKIP_OLDER, f"newer stale result displaced current: {decision}")
        return "older current and newer stale runs cannot replace the current publication"

    check("review-publisher-anti-rollback", stale_rollback_blocked)
