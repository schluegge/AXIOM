from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from axiom_bench import RunnerError, assert_local_trust, replay_conformance, run_conformance
from axiom_bench.bundle import canonical_json, semantic_sha256, sha256_bytes
from axiom_bench.executor import execute_bounded, minimal_environment

from .agent_b_support import check, require


def _read_bundle(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def _repair_manifest(files: dict[str, bytes]) -> None:
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


def _write_bundle(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(files.items()):
            archive.writestr(name, payload)


def register() -> None:
    from . import agent_b_support as support

    root = support.ROOT
    fixture = root / "tests" / "fixtures" / "benchmark_runner" / "task.json"

    def reference_passes() -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            result = run_conformance(
                root,
                fixture,
                language="axiom",
                adapter="reference",
                output_directory=Path(directory) / "reference",
            )
            require(result.conformance_passed, f"reference conformance failed: {result.report}")
            require(result.full_success, "reference did not achieve full success")
            return {"bundle_sha256": result.bundle_sha256}

    check("benchmark-runner-reference-conformance", reference_passes)

    def wrong_rejected() -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            result = run_conformance(
                root,
                fixture,
                language="axiom",
                adapter="seeded_wrong",
                output_directory=Path(directory) / "wrong",
            )
            require(result.conformance_passed, f"seeded wrong conformance failed: {result.report}")
            require(not result.full_success, "seeded wrong unexpectedly achieved full success")
            require(
                result.failure_reason == "acceptance_test_failure",
                f"unexpected seeded-wrong failure: {result.failure_reason}",
            )
            return {"failure_reason": result.failure_reason}

    check("benchmark-runner-seeded-wrong-rejection", wrong_rejected)

    def reproducible_bundle() -> str:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first = run_conformance(
                root,
                fixture,
                language="axiom",
                adapter="reference",
                output_directory=base / "first",
            )
            second = run_conformance(
                root,
                fixture,
                language="axiom",
                adapter="reference",
                output_directory=base / "second",
            )
            require(first.bundle_sha256 == second.bundle_sha256, "bundle hashes differ")
            require(first.bundle_path.read_bytes() == second.bundle_path.read_bytes(), "bundle bytes differ")
            return first.bundle_sha256

    check("benchmark-runner-byte-reproducible", reproducible_bundle)

    def replay_no_process() -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            result = run_conformance(
                root,
                fixture,
                language="axiom",
                adapter="reference",
                output_directory=Path(directory) / "run",
            )
            with patch("subprocess.Popen", side_effect=AssertionError("replay executed process")):
                report = replay_conformance(root, result.bundle_path)
            require(report["status"] == "passed", f"replay failed: {report}")
            require(report["subprocesses_executed"] == 0, "replay subprocess count is non-zero")
            return {"files_verified": report["files_verified"]}

    check("benchmark-runner-replay-no-process", replay_no_process)

    def tamper_blocked() -> str:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            result = run_conformance(
                root,
                fixture,
                language="axiom",
                adapter="reference",
                output_directory=base / "run",
            )

            candidate_files = _read_bundle(result.bundle_path)
            candidate_files["candidate.bin"] = b"tampered candidate\n"
            _repair_manifest(candidate_files)
            candidate_tampered = base / "candidate-tampered.zip"
            _write_bundle(candidate_tampered, candidate_files)
            candidate_report = replay_conformance(root, candidate_tampered)
            require(candidate_report["status"] == "failed", "candidate tamper passed replay")
            candidate_paths = {item["path"] for item in candidate_report["findings"]}
            require(
                "attempt.raw_completion_sha256" in candidate_paths,
                f"candidate hash finding missing: {candidate_paths}",
            )

            command_files = _read_bundle(result.bundle_path)
            command_path = "commands/c04.acceptance-test.json"
            command = json.loads(command_files[command_path])
            command["return_code"] = 1
            command_files[command_path] = canonical_json(command).encode("utf-8")
            attempt = json.loads(command_files["attempt.json"])
            reference = next(
                item for item in attempt["command_records"] if item["path"] == command_path
            )
            reference["sha256"] = sha256_bytes(command_files[command_path])
            command_files["attempt.json"] = canonical_json(attempt).encode("utf-8")
            report = json.loads(command_files["conformance-report.json"])
            report["attempt_sha256"] = sha256_bytes(command_files["attempt.json"])
            command_files["conformance-report.json"] = canonical_json(report).encode("utf-8")
            _repair_manifest(command_files)
            command_tampered = base / "command-tampered.zip"
            _write_bundle(command_tampered, command_files)
            command_report = replay_conformance(root, command_tampered)
            require(command_report["status"] == "failed", "command tamper passed replay")
            command_paths = {item["path"] for item in command_report["findings"]}
            require(
                "attempt.outcomes.acceptance_test_success" in command_paths,
                f"command-derived outcome finding missing: {command_paths}",
            )
            return "candidate and command-chain tampering blocked"

    check("benchmark-runner-replay-tamper-blocked", tamper_blocked)

    def untrusted_blocked() -> str:
        try:
            assert_local_trust("untrusted_model_output")
        except RunnerError as error:
            require(error.finding.code == "AX-BENCH-SANDBOX-REQUIRED", error.finding.code)
            return "untrusted local execution blocked"
        raise AssertionError("untrusted local execution was accepted")

    check("benchmark-runner-untrusted-local-blocked", untrusted_blocked)

    def output_limit() -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            result = execute_bounded(
                [sys.executable, "-c", "import sys; sys.stdout.write('x'*100000); sys.stdout.flush()"],
                cwd=workspace,
                environment=minimal_environment(workspace),
                timeout_seconds=5,
                max_output_bytes=1024,
            )
            require(result.output_limited, "output limit did not trigger")
            require(len(result.stdout) + len(result.stderr) <= 1024, "retained output exceeded cap")
            return {"retained": len(result.stdout) + len(result.stderr)}

    check("benchmark-runner-output-limit", output_limit)
