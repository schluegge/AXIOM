from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from axiom_bench import RunnerError, replay_conformance, run_conformance
from axiom_bench.bundle import canonical_json, semantic_sha256, sha256_bytes
from tests.benchmark_test_repository import create_trusted_test_repository

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "benchmark_runner"
FIXTURE = FIXTURE_ROOT / "task.json"


class TrustedTaskAuthorityTests(unittest.TestCase):
    def write_bundle(self, destination: Path, files: dict[str, bytes]) -> None:
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in sorted(files.items()):
                archive.writestr(name, payload)

    def repair_manifest(self, files: dict[str, bytes]) -> None:
        manifest = json.loads(files["bundle-manifest.json"])
        for relative in manifest["files"]:
            payload = files[relative]
            manifest["files"][relative] = {
                "sha256": sha256_bytes(payload),
                "size_bytes": len(payload),
            }
        manifest["semantic_sha256"] = semantic_sha256(
            {
                "bundle_kind": manifest["bundle_kind"],
                "task_id": manifest["task_id"],
                "language": manifest["language"],
                "adapter": manifest["adapter"],
                "files": manifest["files"],
            }
        )
        files["bundle-manifest.json"] = canonical_json(manifest).encode("utf-8")

    def rewrite_seeded_wrong_bundle_as_reference(self, bundle: Path, destination: Path) -> None:
        with zipfile.ZipFile(bundle, "r") as source:
            files = {info.filename: source.read(info) for info in source.infolist()}

        attempt = json.loads(files["attempt.json"])
        attempt["adapter"] = "reference"
        attempt["trust_class"] = "trusted_reference"
        attempt_bytes = canonical_json(attempt).encode("utf-8")
        files["attempt.json"] = attempt_bytes

        report = json.loads(files["conformance-report.json"])
        report["adapter"] = "reference"
        report["trust_class"] = "trusted_reference"
        report["attempt_sha256"] = sha256_bytes(attempt_bytes)
        files["conformance-report.json"] = canonical_json(report).encode("utf-8")

        manifest = json.loads(files["bundle-manifest.json"])
        manifest["adapter"] = "reference"
        files["bundle-manifest.json"] = canonical_json(manifest).encode("utf-8")
        self.repair_manifest(files)
        self.write_bundle(destination, files)

    def rewrite_report_task_hash(self, bundle: Path, destination: Path) -> None:
        with zipfile.ZipFile(bundle, "r") as source:
            files = {info.filename: source.read(info) for info in source.infolist()}
        report = json.loads(files["conformance-report.json"])
        report["task_sha256"] = "0" * 64
        files["conformance-report.json"] = canonical_json(report).encode("utf-8")
        self.repair_manifest(files)
        self.write_bundle(destination, files)

    def test_runner_rejects_unregistered_external_task_before_output_or_process(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied_task_root = root / "external-task"
            shutil.copytree(FIXTURE_ROOT, copied_task_root)
            output = root / "output"

            with patch(
                "axiom_bench.runner.execute_bounded",
                side_effect=AssertionError("unregistered task reached process execution"),
            ):
                with self.assertRaises(RunnerError) as context:
                    run_conformance(
                        ROOT,
                        copied_task_root / "task.json",
                        language="axiom",
                        adapter="reference",
                        output_directory=output,
                    )

            self.assertEqual(context.exception.finding.code, "AX-BENCH-RUNNER-UNTRUSTED-TASK")
            self.assertFalse(output.exists())

    def test_runner_rejects_registry_path_drift_from_benchmark_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            repository_root, task_path = create_trusted_test_repository(base)
            contract_path = repository_root / "benchmarks" / "contracts" / "0.1.0" / "contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["trusted_task_registry_path"] = "benchmarks/contracts/0.1.0/other.json"
            contract_path.write_text(canonical_json(contract), encoding="utf-8")
            output = base / "output"

            with self.assertRaises(RunnerError) as context:
                run_conformance(
                    repository_root,
                    task_path,
                    language="axiom",
                    adapter="reference",
                    output_directory=output,
                )

            self.assertEqual(context.exception.finding.code, "AX-BENCH-RUNNER-AUTHORITY")
            self.assertFalse(output.exists())

    def test_replay_rejects_reference_expectation_redefined_inside_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_conformance(
                ROOT,
                FIXTURE,
                language="axiom",
                adapter="seeded_wrong",
                output_directory=root / "seeded-wrong",
            )
            rewritten = root / "rewritten-reference.zip"
            self.rewrite_seeded_wrong_bundle_as_reference(result.bundle_path, rewritten)
            replay = replay_conformance(ROOT, rewritten)

        self.assertEqual(replay["status"], "failed", replay)
        self.assertIn("AX-BENCH-REPLAY-AUTHORITY", {item["code"] for item in replay["findings"]})
        self.assertIn(
            "conformance-report.expected_outcome",
            {item["path"] for item in replay["findings"]},
        )

    def test_replay_rejects_task_hash_rewritten_with_repaired_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_conformance(
                ROOT,
                FIXTURE,
                language="axiom",
                adapter="reference",
                output_directory=root / "reference",
            )
            rewritten = root / "rewritten-task-hash.zip"
            self.rewrite_report_task_hash(result.bundle_path, rewritten)
            replay = replay_conformance(ROOT, rewritten)

        self.assertEqual(replay["status"], "failed", replay)
        self.assertIn(
            "conformance-report.task_sha256",
            {item["path"] for item in replay["findings"]},
        )


if __name__ == "__main__":
    unittest.main()
