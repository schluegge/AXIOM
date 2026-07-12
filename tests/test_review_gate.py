from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from axiom_bench import check_benchmark_contract
from axiom_contract import check_project_contract
from axiom_review import validate_report
from axiom_review.gate import (
    EXIT_BLOCKED,
    EXIT_INTERNAL,
    EXIT_PASSED,
    EXIT_USAGE,
    GateInputError,
    load_event,
    run_deterministic_review,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "review/contracts/0.1.0/report.schema.json").read_text(encoding="utf-8")
)
FIXTURE_IGNORE = shutil.ignore_patterns(
    ".git", "evidence", "__pycache__", ".pytest_cache", "*.pyc"
)


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-c", "user.email=gate@axiom.invalid", "-c", "user.name=gate", *arguments],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def make_fixture_repository(directory: Path) -> tuple[Path, str]:
    """Copy the real repository into a fixture root with one git commit."""

    fixture = directory / "repo"
    shutil.copytree(ROOT, fixture, ignore=FIXTURE_IGNORE)
    _git(fixture, "init", "-q")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", "fixture")
    return fixture, _git(fixture, "rev-parse", "HEAD")


def synthesize_proof_evidence(root: Path, evidence_dir: Path) -> None:
    """Write proof evidence equivalent to a passing run_repo_proof.py result."""

    evidence_dir.mkdir(parents=True)
    project = check_project_contract(root)
    benchmark = check_benchmark_contract(root)
    payloads = {
        "project-contract.json": project,
        "benchmark-contract.json": benchmark,
    }
    for name, value in payloads.items():
        (evidence_dir / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    manifest = {
        "document_kind": "axiom.repo-proof",
        "schema_version": "0.7.0",
        "status": "passed",
        "project_contract": {
            "status": project["status"],
            "exit_code": project["exit_code"],
            "current_features": project["counts"]["current_features"],
            "deferred_features": project["counts"]["deferred_features"],
            "findings": project["counts"]["findings"],
        },
        "benchmark_contract": {
            "status": benchmark["status"],
            "exit_code": benchmark["exit_code"],
            "schemas_checked": benchmark["schemas_checked"],
            "findings": benchmark["finding_count"],
        },
        "unit_test_exit_code": 0,
        "unit_tests": 1,
        "agent_b": {"exit_code": 0, "passed": 1, "failed": 0},
        "files": {},
    }
    manifest_path = evidence_dir / "manifest.json"
    manifest["files"] = {
        path.relative_to(evidence_dir).as_posix(): sha256(path.read_bytes()).hexdigest()
        for path in sorted(evidence_dir.rglob("*"))
        if path.is_file()
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


class ReviewGateFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="axiom-review-gate-")
        self.addCleanup(self._directory.cleanup)
        self.base = Path(self._directory.name)
        self.fixture, self.head = make_fixture_repository(self.base)
        self.evidence = self.base / "proof-evidence"
        self.output = self.base / "review-output"

    def run_gate(self, **overrides: object):
        arguments: dict[str, object] = {
            "repository": "schluegge/AXIOM",
            "pull_request_number": 34,
            "base_sha": "1" * 40,
            "head_sha": self.head,
            "evidence_dir": self.evidence,
            "output_dir": self.output,
        }
        arguments.update(overrides)
        return run_deterministic_review(self.fixture, **arguments)

    def synthesize_evidence(self) -> None:
        synthesize_proof_evidence(self.fixture, self.evidence)

    def finding_codes(self, result) -> set[str]:
        return {item["code"] for item in result.report["findings"]}

    def read_report(self) -> dict[str, object]:
        return json.loads((self.output / "review-report.json").read_text(encoding="utf-8"))


class CleanFixtureTests(ReviewGateFixture):
    def test_clean_fixture_passes_and_emits_valid_bounded_outputs(self) -> None:
        self.synthesize_evidence()
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_PASSED, result.report["findings"])
        self.assertEqual(result.report["status"], "passed")
        self.assertEqual(result.report["reviewed_head_sha"], self.head)
        self.assertEqual(result.report["reviewer_class"], "deterministic")
        self.assertEqual(validate_report(self.read_report(), SCHEMA), [])
        summary = (self.output / "review-summary.md").read_text(encoding="utf-8")
        self.assertIn("Status: **PASSED**", summary)
        self.assertLessEqual(
            (self.output / "review-report.json").stat().st_size, 1_048_576
        )
        self.assertLessEqual(
            (self.output / "review-summary.md").stat().st_size, 262_144
        )
        for check in result.report["checks"]:
            self.assertEqual(check["conclusion"], "passed", check)
            evidence_path = check["evidence_path"]
            self.assertIsNotNone(evidence_path)
            self.assertFalse(Path(evidence_path).is_absolute())
            self.assertNotIn("\\", evidence_path)
            self.assertTrue((self.output / evidence_path).is_file(), evidence_path)

    def test_existing_nonempty_output_directory_is_never_replaced(self) -> None:
        self.synthesize_evidence()
        self.output.mkdir(parents=True)
        marker = self.output / "existing.txt"
        marker.write_text("keep", encoding="utf-8")
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_USAGE)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")


class ProofEvidenceTests(ReviewGateFixture):
    def test_missing_exact_head_proof_fails(self) -> None:
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertEqual(result.report["status"], "failed")
        self.assertIn("AX-REV-GATE-0301", self.finding_codes(result))
        self.assertEqual(validate_report(self.read_report(), SCHEMA), [])

    def test_failed_proof_manifest_fails(self) -> None:
        self.synthesize_evidence()
        manifest_path = self.evidence / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "failed"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0302", self.finding_codes(result))

    def test_tampered_proof_evidence_digest_fails(self) -> None:
        self.synthesize_evidence()
        target = self.evidence / "project-contract.json"
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0303", self.finding_codes(result))

    def test_inserted_proof_evidence_file_fails(self) -> None:
        self.synthesize_evidence()
        (self.evidence / "inserted.json").write_text("{}\n", encoding="utf-8")
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0303", self.finding_codes(result))

    def test_stale_proof_contract_record_fails(self) -> None:
        self.synthesize_evidence()
        manifest_path = self.evidence / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["project_contract"]["current_features"] += 1
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0304", self.finding_codes(result))


class HeadIdentityTests(ReviewGateFixture):
    def test_head_mismatch_fails(self) -> None:
        self.synthesize_evidence()
        result = self.run_gate(head_sha="a" * 40)
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0102", self.finding_codes(result))

    def test_malformed_head_sha_is_a_usage_failure(self) -> None:
        self.synthesize_evidence()
        result = self.run_gate(head_sha="not-a-sha")
        self.assertEqual(result.exit_code, EXIT_USAGE)


class DocumentationDriftTests(ReviewGateFixture):
    def test_readme_claim_drift_fails(self) -> None:
        self.synthesize_evidence()
        readme = self.fixture / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(
            text.replace(
                "- `core.vertical-pipeline`",
                "- `stdlib.cli-data-json`\n- `core.vertical-pipeline`",
            ),
            encoding="utf-8",
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0201", self.finding_codes(result))

    def test_benchmark_contract_break_fails(self) -> None:
        self.synthesize_evidence()
        contract = self.fixture / "benchmarks/contracts/0.1.0/contract.json"
        contract.write_text("{}\n", encoding="utf-8")
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0202", self.finding_codes(result))

    def test_roadmap_contract_break_fails(self) -> None:
        self.synthesize_evidence()
        roadmap = self.fixture / "roadmap/v1.json"
        value = json.loads(roadmap.read_text(encoding="utf-8"))
        value["active_milestone"] = "M2"
        roadmap.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0203", self.finding_codes(result))


class ProtectedBaselineTests(ReviewGateFixture):
    def test_removed_regression_test_fails(self) -> None:
        self.synthesize_evidence()
        (self.fixture / "tests/test_references.py").unlink()
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0401", self.finding_codes(result))

    def test_removed_agent_b_registration_fails(self) -> None:
        self.synthesize_evidence()
        review = self.fixture / "agents/agent_b_review.py"
        text = review.read_text(encoding="utf-8")
        text = text.replace(
            "from agents.agent_b_reference_checks import register as register_references\n",
            "",
        ).replace("        register_references()\n", "")
        review.write_text(text, encoding="utf-8")
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0402", self.finding_codes(result))

    def test_registration_moved_into_dead_code_fails(self) -> None:
        self.synthesize_evidence()
        review = self.fixture / "agents/agent_b_review.py"
        text = review.read_text(encoding="utf-8")
        text = text.replace("        register_references()\n", "")
        text += "\n\ndef _unexecuted_helper() -> None:\n    register_references()\n"
        review.write_text(text, encoding="utf-8")
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0402", self.finding_codes(result))

    def test_invalid_policy_fails_closed(self) -> None:
        self.synthesize_evidence()
        policy = self.fixture / "review/policy/0.1.0/gate-policy.json"
        value = json.loads(policy.read_text(encoding="utf-8"))
        value["protected_paths"].append("../outside.txt")
        policy.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0403", self.finding_codes(result))


class WorkflowSecurityTests(ReviewGateFixture):
    def write_workflow(self, name: str, text: str) -> None:
        (self.fixture / ".github/workflows" / name).write_text(text, encoding="utf-8")

    def test_unpinned_action_fails(self) -> None:
        self.synthesize_evidence()
        proof = self.fixture / ".github/workflows/proof.yml"
        proof.write_text(
            proof.read_text(encoding="utf-8").replace(
                "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6",
                "actions/checkout@v6",
            ),
            encoding="utf-8",
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0501", self.finding_codes(result))

    def test_pull_request_target_fails(self) -> None:
        self.synthesize_evidence()
        self.write_workflow(
            "innocent.yml",
            "name: innocent\n"
            "on: [push, pull_request_target]\n"
            "permissions:\n  contents: read\n"
            "jobs:\n  noop:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: 'true'\n",
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0502", self.finding_codes(result))

    def test_widened_workflow_permission_fails(self) -> None:
        self.synthesize_evidence()
        proof = self.fixture / ".github/workflows/proof.yml"
        proof.write_text(
            proof.read_text(encoding="utf-8").replace(
                "permissions:\n  contents: read",
                "permissions:\n  contents: write",
            ),
            encoding="utf-8",
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0503", self.finding_codes(result))

    def test_new_workflow_receives_strict_default_allowlist(self) -> None:
        self.synthesize_evidence()
        self.write_workflow(
            "helper.yml",
            "name: helper\non: [push]\n"
            "permissions:\n  issues: write\n"
            "jobs:\n  noop:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: 'true'\n",
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0503", self.finding_codes(result))

    def test_missing_permissions_declaration_fails(self) -> None:
        self.synthesize_evidence()
        self.write_workflow(
            "nopermissions.yml",
            "name: nopermissions\non: [push]\n"
            "jobs:\n  noop:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: 'true'\n",
        )
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0503", self.finding_codes(result))

    def test_unparseable_workflow_fails_closed(self) -> None:
        self.synthesize_evidence()
        self.write_workflow("broken.yml", "{{{ not yaml ::::\n")
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        self.assertIn("AX-REV-GATE-0504", self.finding_codes(result))


class EventParsingTests(unittest.TestCase):
    def test_valid_pull_request_event_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="axiom-review-event-") as directory:
            event_path = Path(directory) / "event.json"
            event_path.write_text(
                json.dumps(
                    {
                        "pull_request": {
                            "number": 34,
                            "head": {"sha": "2" * 40},
                            "base": {"sha": "1" * 40},
                        },
                        "repository": {"full_name": "schluegge/AXIOM"},
                    }
                ),
                encoding="utf-8",
            )
            identity = load_event(event_path)
        self.assertEqual(identity["repository"], "schluegge/AXIOM")
        self.assertEqual(identity["pull_request_number"], 34)
        self.assertEqual(identity["base_sha"], "1" * 40)
        self.assertEqual(identity["head_sha"], "2" * 40)

    def test_malformed_event_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="axiom-review-event-") as directory:
            event_path = Path(directory) / "event.json"
            for payload in ("{not json", "[]", '{"pull_request": {}}'):
                event_path.write_text(payload, encoding="utf-8")
                with self.assertRaises(GateInputError):
                    load_event(event_path)
            with self.assertRaises(GateInputError):
                load_event(Path(directory) / "missing.json")


class CommandLineTests(ReviewGateFixture):
    def test_cli_produces_report_and_summary_from_event(self) -> None:
        self.synthesize_evidence()
        event_path = self.base / "event.json"
        event_path.write_text(
            json.dumps(
                {
                    "pull_request": {
                        "number": 34,
                        "head": {"sha": self.head},
                        "base": {"sha": "1" * 40},
                    },
                    "repository": {"full_name": "schluegge/AXIOM"},
                }
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(self.fixture / "tools/run_deterministic_review.py"),
                "--root",
                str(self.fixture),
                "--event",
                str(event_path),
                "--evidence-dir",
                str(self.evidence),
                "--output",
                str(self.output),
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, EXIT_PASSED, completed.stderr)
        report = self.read_report()
        self.assertEqual(validate_report(report, SCHEMA), [])
        self.assertEqual(report["pull_request_number"], 34)
        self.assertTrue((self.output / "review-summary.md").is_file())

    def test_cli_fails_closed_on_malformed_event(self) -> None:
        self.synthesize_evidence()
        event_path = self.base / "event.json"
        event_path.write_text("{broken", encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(self.fixture / "tools/run_deterministic_review.py"),
                "--root",
                str(self.fixture),
                "--event",
                str(event_path),
                "--evidence-dir",
                str(self.evidence),
                "--output",
                str(self.output),
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, EXIT_USAGE)
        self.assertFalse((self.output / "review-report.json").exists())

    def test_cli_reports_blocking_exit_code_for_seeded_defect(self) -> None:
        self.synthesize_evidence()
        (self.fixture / "tests/test_vertical.py").unlink()
        completed = subprocess.run(
            [
                sys.executable,
                str(self.fixture / "tools/run_deterministic_review.py"),
                "--root",
                str(self.fixture),
                "--repository",
                "schluegge/AXIOM",
                "--pull-request",
                "34",
                "--base-sha",
                "1" * 40,
                "--head-sha",
                self.head,
                "--evidence-dir",
                str(self.evidence),
                "--output",
                str(self.output),
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, EXIT_BLOCKED, completed.stderr)
        report = self.read_report()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(validate_report(report, SCHEMA), [])


class FailClosedReportTests(ReviewGateFixture):
    def test_internal_exit_codes_are_distinct(self) -> None:
        self.assertEqual(EXIT_PASSED, 0)
        self.assertEqual(EXIT_BLOCKED, 1)
        self.assertEqual(EXIT_USAGE, 2)
        self.assertEqual(EXIT_INTERNAL, 3)

    def test_every_blocking_finding_has_evidence_and_high_severity(self) -> None:
        result = self.run_gate()
        self.assertEqual(result.exit_code, EXIT_BLOCKED)
        for finding in result.report["findings"]:
            if finding["authority"] == "blocking":
                self.assertIn(finding["severity"], {"critical", "high"})
                self.assertTrue(finding["evidence_path"].strip())


if __name__ == "__main__":
    unittest.main()
