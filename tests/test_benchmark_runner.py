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
from axiom_bench.bundle import (
    canonical_json,
    safe_relative_path,
    safe_zip_entries,
    semantic_sha256,
    sha256_bytes,
    sha256_file,
)
from axiom_bench.executor import execute_bounded, minimal_environment
from axiom_bench.runner import expand_command
from tests.benchmark_test_repository import create_trusted_test_repository

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "benchmark_runner"
FIXTURE = FIXTURE_ROOT / "task.json"


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

    def copied_fixture(
        self,
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        repository_root, task_path = create_trusted_test_repository(base)
        return temporary, repository_root, task_path, base / "output"

    def modify_task(self, mutator):
        _, repository_root, task_path, output = self.copied_fixture()
        document = json.loads(task_path.read_text(encoding="utf-8"))
        mutator(document)
        task_path.write_text(canonical_json(document), encoding="utf-8")
        return repository_root, task_path, output

    def rewrite_bundle_report_path(self, bundle: Path, value: str) -> Path:
        destination = bundle.with_name(f"tampered-{len(value)}.zip")
        with zipfile.ZipFile(bundle, "r") as source:
            files = {info.filename: source.read(info) for info in source.infolist()}

        report = json.loads(files["conformance-report.json"])
        report["attempt_path"] = value
        files["conformance-report.json"] = canonical_json(report).encode("utf-8")

        manifest = json.loads(files["bundle-manifest.json"])
        report_bytes = files["conformance-report.json"]
        manifest["files"]["conformance-report.json"] = {
            "sha256": sha256_bytes(report_bytes),
            "size_bytes": len(report_bytes),
        }
        semantic_payload = {
            "bundle_kind": manifest["bundle_kind"],
            "task_id": manifest["task_id"],
            "language": manifest["language"],
            "adapter": manifest["adapter"],
            "files": manifest["files"],
        }
        manifest["semantic_sha256"] = semantic_sha256(semantic_payload)
        files["bundle-manifest.json"] = canonical_json(manifest).encode("utf-8")

        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in sorted(files.items()):
                archive.writestr(name, payload)
        return destination

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

    def test_replay_rejects_unsafe_internal_report_paths_even_with_updated_manifest(self) -> None:
        result = self.run_fixture("reference")
        for unsafe in ("../outside.json", "C:/outside.json", "nested//attempt.json"):
            with self.subTest(path=unsafe):
                tampered = self.rewrite_bundle_report_path(result.bundle_path, unsafe)
                report = replay_conformance(ROOT, tampered)
                self.assertEqual(report["status"], "failed", report)
                self.assertTrue(
                    any("unsafe conformance-report.attempt_path" in item["message"] for item in report["findings"]),
                    report,
                )

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

    def test_existing_output_directory_is_rejected_without_deletion(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "existing"
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_text("keep\n", encoding="utf-8")
        with self.assertRaises(RunnerError) as context:
            run_conformance(
                ROOT,
                FIXTURE,
                language="axiom",
                adapter="reference",
                output_directory=output,
            )
        self.assertEqual(context.exception.finding.code, "AX-BENCH-RUNNER-INVALID-PATH")
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")

    def test_missing_candidate_path_is_rejected_by_runner_boundary(self) -> None:
        def mutate(document):
            del document["variants"]["axiom"]["candidate_path"]

        repository_root, task_path, output = self.modify_task(mutate)
        with self.assertRaises(RunnerError) as context:
            run_conformance(
                repository_root,
                task_path,
                language="axiom",
                adapter="reference",
                output_directory=output,
            )
        self.assertEqual(context.exception.finding.code, "AX-BENCH-RUNNER-AUTHORITY")

    def test_runner_records_process_start_failure(self) -> None:
        def mutate(document):
            document["variants"]["axiom"]["formatter_command"] = [
                "axiom-command-that-does-not-exist"
            ]

        repository_root, task_path, output = self.modify_task(mutate)
        result = run_conformance(
            repository_root,
            task_path,
            language="axiom",
            adapter="reference",
            output_directory=output,
        )
        self.assertFalse(result.conformance_passed)
        self.assertEqual(result.failure_reason, "runner_error")
        record = json.loads(
            (output / "canonical" / "commands" / "c01.format.json").read_text(encoding="utf-8")
        )
        self.assertEqual(record["termination"], "not_started")
        self.assertIsNone(record["return_code"])

    def test_runner_enforces_compiler_invocation_budget(self) -> None:
        def mutate(document):
            document["budgets"]["max_compiler_invocations"] = 1

        repository_root, task_path, output = self.modify_task(mutate)
        result = run_conformance(
            repository_root,
            task_path,
            language="axiom",
            adapter="reference",
            output_directory=output,
        )
        self.assertFalse(result.conformance_passed)
        self.assertEqual(result.failure_reason, "resource_limit")
        self.assertEqual(result.report["actual_failure_reason"], "resource_limit")

    def test_runner_enforces_feedback_budget(self) -> None:
        def mutate(document):
            document["budgets"]["max_feedback_bytes"] = 1
            document["variants"]["axiom"]["formatter_command"] = [
                "{python}",
                "-c",
                "print('feedback')",
            ]

        repository_root, task_path, output = self.modify_task(mutate)
        result = run_conformance(
            repository_root,
            task_path,
            language="axiom",
            adapter="reference",
            output_directory=output,
        )
        self.assertFalse(result.conformance_passed)
        self.assertEqual(result.failure_reason, "resource_limit")

    def test_runner_enforces_total_task_timeout(self) -> None:
        def mutate(document):
            document["budgets"]["task_timeout_seconds"] = 1
            document["variants"]["axiom"]["formatter_command"] = [
                "{python}",
                "-c",
                "import time; time.sleep(30)",
            ]

        repository_root, task_path, output = self.modify_task(mutate)
        result = run_conformance(
            repository_root,
            task_path,
            language="axiom",
            adapter="reference",
            output_directory=output,
        )
        self.assertFalse(result.conformance_passed)
        self.assertEqual(result.failure_reason, "timeout")

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

    def test_safe_relative_path_rejects_noncanonical_and_windows_paths(self) -> None:
        for value in ("a//b", "a/./b", "C:/outside", "file:stream", "a\\b"):
            with self.subTest(path=value), self.assertRaises(ValueError):
                safe_relative_path(value)

    def test_bundle_hash_matches_file_bytes(self) -> None:
        result = self.run_fixture("reference")
        self.assertEqual(result.bundle_sha256, sha256_file(result.bundle_path))


if __name__ == "__main__":
    unittest.main()
