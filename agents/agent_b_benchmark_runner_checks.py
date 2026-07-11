from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from axiom_bench import RunnerError, assert_local_trust, replay_conformance, run_conformance
from axiom_bench.executor import execute_bounded, minimal_environment

from .agent_b_support import check, require


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
            tampered = base / "tampered.zip"
            with zipfile.ZipFile(result.bundle_path, "r") as source, zipfile.ZipFile(
                tampered, "w", zipfile.ZIP_DEFLATED
            ) as destination:
                for info in source.infolist():
                    data = source.read(info)
                    if info.filename == "candidate.bin":
                        data = b"tampered\n"
                    destination.writestr(info, data)
            report = replay_conformance(root, tampered)
            require(report["status"] == "failed", "tampered replay unexpectedly passed")
            codes = {item["code"] for item in report["findings"]}
            require("AX-BENCH-REPLAY-TAMPERED" in codes, f"tamper code missing: {codes}")
            return "tampered bundle blocked"

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
