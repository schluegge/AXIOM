from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from axiom_bench import RunnerError, assert_local_trust, replay_conformance, run_conformance
from axiom_bench.bundle import safe_zip_entries, sha256_file
from axiom_bench.executor import execute_bounded, minimal_environment
from axiom_bench.runner import expand_command

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "benchmark_runner" / "task.json"


class BenchmarkRunnerTests(unittest.TestCase):
    def run_fixture(self, adapter: str, *, language: str = "axiom"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / f"{language}-{adapter}"
        result = run_conformance(
            ROOT,
            FIXTURE,
            language=language,  # type: ignore[arg-type]
            adapter=adapter,  # type: ignore[arg-type]
            output_directory=output,
        )
        return result

    def test_reference_conformance_passes_for_all_variant_keys(self) -> None:
        for language in ("axiom", "rust", "zig", "go"):
            with self.subTest(language=language):
                result = self.run_fixture("reference", language=language)
                self.assertTrue(result.conformance_passed, result.report)
                self.assertTrue(result.full_success)
                self.assertIsNone(result.failure_reason)
                self.assertTrue(result.bundle_path.is_file())

    def test_seeded_wrong_fails_only_at_acceptance_and_passes_harness_conformance(self) -> None:
        result = self.run_fixture("seeded_wrong")
        self.assertTrue(result.conformance_passed, result.report)
        self.assertFalse(result.full_success)
        self.assertEqual(result.failure_reason, "acceptance_test_failure")
        attempt = json.loads(
            (result.output_directory / "canonical" / "attempt.json").read_text(encoding="utf-8")
        )
        self.assertTrue(attempt["outcomes"]["public_test_success"])
        self.assertFalse(attempt["outcomes"]["acceptance_test_success"])
        self.assertIsNone(attempt["outcomes"]["security_success"])

    def test_reference_bundle_is_byte_reproducible(self) -> None:
        first = self.run_fixture("reference")
        first_bytes = first.bundle_path.read_bytes()
        second = self.run_fixture("reference")
        self.assertEqual(first.bundle_sha256, second.bundle_sha256)
        self.assertEqual(first_bytes, second.bundle_path.read_bytes())

    def test_replay_passes_without_subprocess_execution(self) -> None:
        result = self.run_fixture("reference")
        with patch("subprocess.Popen", side_effect=AssertionError("replay executed a subprocess")):
            report = replay_conformance(ROOT, result.bundle_path)
        self.assertEqual(report["status"], "passed", report)
        self.assertEqual(report["subprocesses_executed"], 0)
        self.assertTrue(report["recorded_conformance_passed"])
        self.assertTrue(report["recomputed_conformance_passed"])

    def test_replay_rejects_tampered_candidate(self) -> None:
        result = self.run_fixture("reference")
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tampered = Path(temporary.name) / "tampered.zip"
        with zipfile.ZipFile(result.bundle_path, "r") as source, zipfile.ZipFile(
            tampered, "w", zipfile.ZIP_DEFLATED
        ) as destination:
            for info in source.infolist():
                data = source.read(info)
                if info.filename == "candidate.bin":
                    data = b"tampered\n"
                destination.writestr(info, data)
        report = replay_conformance(ROOT, tampered)
        self.assertEqual(report["status"], "failed")
        self.assertIn("AX-BENCH-REPLAY-TAMPERED", {item["code"] for item in report["findings"]})

    def test_replay_rejects_duplicate_zip_paths(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "duplicate.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("duplicate.txt", b"one")
            archive.writestr("duplicate.txt", b"two")
        report = replay_conformance(ROOT, path)
        self.assertEqual(report["status"], "failed")
        self.assertIn("AX-BENCH-REPLAY-TAMPERED", {item["code"] for item in report["findings"]})

    def test_untrusted_local_execution_is_rejected_before_workspace_or_process(self) -> None:
        with self.assertRaises(RunnerError) as context:
            assert_local_trust("untrusted_model_output")
        self.assertEqual(context.exception.finding.code, "AX-BENCH-SANDBOX-REQUIRED")

    def test_unknown_placeholder_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RunnerError) as context:
                expand_command(
                    ["{unknown}"],
                    workspace=root,
                    task_root=root,
                    candidate=root / "candidate.txt",
                    language="axiom",
                )
        self.assertEqual(
            context.exception.finding.code, "AX-BENCH-RUNNER-UNKNOWN-PLACEHOLDER"
        )

    def test_bounded_executor_enforces_combined_output_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            environment = minimal_environment(workspace)
            result = execute_bounded(
                [
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.write('x'*100000); sys.stdout.flush()",
                ],
                cwd=workspace,
                environment=environment,
                timeout_seconds=5,
                max_output_bytes=1024,
            )
        self.assertTrue(result.output_limited)
        self.assertLessEqual(len(result.stdout) + len(result.stderr), 1024)

    def test_bounded_executor_enforces_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            environment = minimal_environment(workspace)
            result = execute_bounded(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                cwd=workspace,
                environment=environment,
                timeout_seconds=1,
                max_output_bytes=1024,
            )
        self.assertTrue(result.timed_out)
        self.assertIn(result.termination, {"terminate", "kill"})

    def test_minimal_environment_does_not_inherit_seeded_secret(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = minimal_environment(
                Path(directory),
                {"PATH": os.environ.get("PATH", ""), "AXIOM_SEEDED_SECRET": "secret"},
            )
        self.assertNotIn("AXIOM_SEEDED_SECRET", environment)
        self.assertEqual(environment["PYTHONHASHSEED"], "0")
        self.assertEqual(environment["TZ"], "UTC")

    def test_safe_zip_entries_rejects_absolute_or_parent_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("../escape.txt", b"x")
            with zipfile.ZipFile(path, "r") as archive:
                with self.assertRaises(ValueError):
                    safe_zip_entries(archive)

    def test_bundle_hash_matches_file_bytes(self) -> None:
        result = self.run_fixture("reference")
        self.assertEqual(result.bundle_sha256, sha256_file(result.bundle_path))


if __name__ == "__main__":
    unittest.main()
