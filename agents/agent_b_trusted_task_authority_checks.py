from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from axiom_bench import RunnerError, replay_conformance, run_conformance
from axiom_bench.bundle import canonical_json, semantic_sha256, sha256_bytes

from . import agent_b_support as support


def unregistered_task_stops_before_execution() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        source = support.ROOT / "tests" / "fixtures" / "benchmark_runner"
        copied = base / "external-task"
        shutil.copytree(source, copied)
        output = base / "output"
        with patch(
            "axiom_bench.runner.execute_bounded",
            side_effect=AssertionError("unregistered task reached execution"),
        ):
            try:
                run_conformance(
                    support.ROOT,
                    copied / "task.json",
                    language="axiom",
                    adapter="reference",
                    output_directory=output,
                )
            except RunnerError as error:
                support.require(
                    error.finding.code == "AX-BENCH-RUNNER-UNTRUSTED-TASK",
                    f"wrong unregistered-task finding: {error.finding.as_dict()}",
                )
            else:
                raise AssertionError("unregistered task was accepted")
        support.require(not output.exists(), "unregistered task created output Evidence")
    return {"finding": "AX-BENCH-RUNNER-UNTRUSTED-TASK", "process_started": False}


def coherent_reference_relabel_is_rejected() -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        fixture = support.ROOT / "tests" / "fixtures" / "benchmark_runner" / "task.json"
        result = run_conformance(
            support.ROOT,
            fixture,
            language="axiom",
            adapter="seeded_wrong",
            output_directory=base / "seeded-wrong",
        )
        rewritten = base / "rewritten-reference.zip"
        with zipfile.ZipFile(result.bundle_path, "r") as source:
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
        report_bytes = canonical_json(report).encode("utf-8")
        files["conformance-report.json"] = report_bytes

        manifest = json.loads(files["bundle-manifest.json"])
        manifest["adapter"] = "reference"
        manifest["files"]["attempt.json"] = {
            "sha256": sha256_bytes(attempt_bytes),
            "size_bytes": len(attempt_bytes),
        }
        manifest["files"]["conformance-report.json"] = {
            "sha256": sha256_bytes(report_bytes),
            "size_bytes": len(report_bytes),
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

        with zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in sorted(files.items()):
                archive.writestr(name, payload)

        replay = replay_conformance(support.ROOT, rewritten)
        support.require(replay["status"] == "failed", f"coherent relabel passed: {replay}")
        codes = {item["code"] for item in replay["findings"]}
        support.require("AX-BENCH-REPLAY-AUTHORITY" in codes, f"missing authority finding: {replay}")
    return {"finding": "AX-BENCH-REPLAY-AUTHORITY", "internal_hash_chain_repaired": True}


def register() -> None:
    support.check(
        "trusted-task-registry-blocks-external-task-before-execution",
        unregistered_task_stops_before_execution,
    )
    support.check(
        "replay-rejects-coherent-reference-expectation-redefinition",
        coherent_reference_relabel_is_rejected,
    )
