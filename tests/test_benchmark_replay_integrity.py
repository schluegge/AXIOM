from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from axiom_bench import replay_conformance, run_conformance
from axiom_bench.bundle import canonical_json, semantic_sha256, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "benchmark_runner" / "task.json"


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


if __name__ == "__main__":
    unittest.main()
