from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from axiom_bench import RunnerError, replay_conformance, run_conformance
from axiom_bench.bundle import (
    canonical_json,
    canonical_stream_bytes,
    read_bounded_zip_entry,
    semantic_sha256,
    sha256_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "benchmark_runner"
FIXTURE = FIXTURE_ROOT / "task.json"


class BenchmarkReplayIntegrityTests(unittest.TestCase):
    def reference_bundle(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name) / "reference"
        result = run_conformance(
            ROOT,
            FIXTURE,
            language="axiom",
            adapter="reference",
            output_directory=output,
        )
        self.assertTrue(result.conformance_passed, result.report)
        return temporary, result.bundle_path

    def read_bundle(self, bundle: Path) -> dict[str, bytes]:
        with zipfile.ZipFile(bundle, "r") as archive:
            return {info.filename: archive.read(info) for info in archive.infolist()}

    def repair_manifest(self, files: dict[str, bytes]) -> None:
        manifest = json.loads(files["bundle-manifest.json"])
        for relative in manifest["files"]:
            payload = files[relative]
            manifest["files"][relative] = {
                "sha256": sha256_bytes(payload),
                "size_bytes": len(payload),
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

    def write_bundle(self, path: Path, files: dict[str, bytes]) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in sorted(files.items()):
                archive.writestr(name, payload)

    def test_replay_rejects_candidate_replacement_with_repaired_manifest(self) -> None:
        temporary, bundle = self.reference_bundle()
        files = self.read_bundle(bundle)
        files["candidate.bin"] = b"tampered candidate\n"
        self.repair_manifest(files)
        tampered = Path(temporary.name) / "candidate-manifest-repaired.zip"
        self.write_bundle(tampered, files)

        report = replay_conformance(ROOT, tampered)

        self.assertEqual(report["status"], "failed", report)
        paths = {item["path"] for item in report["findings"]}
        self.assertIn("attempt.raw_completion_sha256", paths)
        self.assertIn("attempt.extracted_artifact_sha256", paths)

    def test_replay_rejects_command_failure_with_stale_outcomes_and_repaired_hash_chain(self) -> None:
        temporary, bundle = self.reference_bundle()
        files = self.read_bundle(bundle)
        command_path = "commands/c04.acceptance-test.json"
        command = json.loads(files[command_path])
        command["return_code"] = 1
        files[command_path] = canonical_json(command).encode("utf-8")

        attempt = json.loads(files["attempt.json"])
        reference = next(
            item for item in attempt["command_records"] if item["path"] == command_path
        )
        reference["sha256"] = sha256_bytes(files[command_path])
        files["attempt.json"] = canonical_json(attempt).encode("utf-8")

        report = json.loads(files["conformance-report.json"])
        report["attempt_sha256"] = sha256_bytes(files["attempt.json"])
        files["conformance-report.json"] = canonical_json(report).encode("utf-8")

        self.repair_manifest(files)
        tampered = Path(temporary.name) / "command-chain-repaired.zip"
        self.write_bundle(tampered, files)

        replay = replay_conformance(ROOT, tampered)

        self.assertEqual(replay["status"], "failed", replay)
        paths = {item["path"] for item in replay["findings"]}
        self.assertIn("attempt.outcomes.acceptance_test_success", paths)
        self.assertIn("attempt.failure_reason", paths)
        self.assertIn("conformance-report.actual_full_success", paths)
        self.assertIn("conformance-report.actual_failure_reason", paths)

    def test_path_emitting_command_still_produces_reproducible_canonical_bundle(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        task_root = base / "task"
        shutil.copytree(FIXTURE_ROOT, task_root)
        task_path = task_root / "task.json"
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task["variants"]["axiom"]["formatter_command"] = [
            "{python}",
            "-c",
            "import os,sys; print(os.getcwd()); print(sys.argv[1])",
            "{task_root}",
        ]
        task_path.write_text(canonical_json(task), encoding="utf-8")

        first = run_conformance(
            ROOT,
            task_path,
            language="axiom",
            adapter="reference",
            output_directory=base / "first",
        )
        second = run_conformance(
            ROOT,
            task_path,
            language="axiom",
            adapter="reference",
            output_directory=base / "second",
        )

        self.assertEqual(first.bundle_sha256, second.bundle_sha256)
        self.assertEqual(first.bundle_path.read_bytes(), second.bundle_path.read_bytes())
        with zipfile.ZipFile(first.bundle_path, "r") as archive:
            stdout = archive.read("stdout/c01.format.bin")
        self.assertIn(b"{workspace}", stdout)
        self.assertIn(b"{task_root}", stdout)
        self.assertNotIn(str(base).encode("utf-8"), stdout)

    def test_bounded_zip_reader_enforces_actual_decompressed_bytes(self) -> None:
        class Entry:
            filename = "payload.bin"
            file_size = 1

        class Archive:
            def open(self, entry, mode="r"):
                self.assert_entry = entry
                self.assert_mode = mode
                return io.BytesIO(b"x" * 11)

        with self.assertRaisesRegex(ValueError, "actual replay limit"):
            read_bounded_zip_entry(
                Archive(),  # type: ignore[arg-type]
                Entry(),  # type: ignore[arg-type]
                total_bytes=0,
                max_entry_bytes=10,
                max_total_bytes=20,
            )

    def test_replay_converts_memory_exhaustion_to_failed_report(self) -> None:
        _, bundle = self.reference_bundle()
        with patch(
            "axiom_bench.replay.read_bounded_zip_entry",
            side_effect=MemoryError("seeded exhaustion"),
        ):
            report = replay_conformance(ROOT, bundle)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(
            any("MemoryError" in item["message"] or "seeded exhaustion" in item["message"] for item in report["findings"]),
            report,
        )

    def test_output_directory_creation_failure_is_structured(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        target = (Path(temporary.name) / "blocked").resolve()
        original_mkdir = Path.mkdir

        def fail_target(path: Path, *args, **kwargs):
            if path.resolve() == target:
                raise PermissionError("seeded mkdir denial")
            return original_mkdir(path, *args, **kwargs)

        with patch.object(Path, "mkdir", new=fail_target):
            with self.assertRaises(RunnerError) as context:
                run_conformance(
                    ROOT,
                    FIXTURE,
                    language="axiom",
                    adapter="reference",
                    output_directory=target,
                )
        self.assertEqual(context.exception.finding.code, "AX-BENCH-RUNNER-INVALID-PATH")
        self.assertIn("cannot create output directory", context.exception.finding.message)

    def test_attempt_and_conformance_failure_reason_enums_match(self) -> None:
        attempt = json.loads(
            (ROOT / "benchmarks" / "schemas" / "0.1.0" / "attempt.schema.json").read_text(
                encoding="utf-8"
            )
        )
        report = json.loads(
            (
                ROOT
                / "benchmarks"
                / "schemas"
                / "0.1.0"
                / "conformance-report.schema.json"
            ).read_text(encoding="utf-8")
        )
        attempt_reasons = set(attempt["properties"]["failure_reason"]["enum"])
        report_reasons = set(report["$defs"]["failureReason"]["enum"])
        self.assertEqual(attempt_reasons, report_reasons)

    def test_canonical_stream_bytes_normalizes_native_and_slash_variants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            task_root = Path(directory) / "task"
            payload = (
                f"{workspace}\n{workspace.as_posix()}\n"
                f"{str(task_root).replace('/', chr(92))}\n{task_root.as_posix()}\n"
            ).encode("utf-8")
            canonical = canonical_stream_bytes(payload, workspace, task_root)
        self.assertNotIn(str(workspace).encode("utf-8"), canonical)
        self.assertNotIn(str(task_root).encode("utf-8"), canonical)
        self.assertGreaterEqual(canonical.count(b"{workspace}"), 2)
        self.assertGreaterEqual(canonical.count(b"{task_root}"), 2)


if __name__ == "__main__":
    unittest.main()
