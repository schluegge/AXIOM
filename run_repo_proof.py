from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from hashlib import sha256
from pathlib import Path

from axiom_bench import check_benchmark_contract, replay_conformance, run_conformance
from axiom_contract import check_project_contract, render_text
from axiom_proof.arithmetic import PANIC_NAMES
from axiom_proof.driver import canonical_json, compile_source, prove

ROOT = Path(__file__).resolve().parent
OUT = Path("evidence") / "repo-proof"
ZIP = Path("evidence") / "AXIOM_REPO_PROOF_EVIDENCE.zip"
FIXED_ZIP_TIME = (2026, 7, 11, 0, 0, 0)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def normalize_test_log(text: str) -> str:
    return re.sub(r"Ran (\d+) tests? in [0-9.]+s", r"Ran \1 tests", text)


def write_deterministic_zip(source: Path, destination: Path) -> None:
    destination.unlink(missing_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(destination) as archive:
        require(archive.testzip() is None, "evidence ZIP CRC failure")
        require(all("\\" not in name for name in archive.namelist()), "non-portable ZIP path")


def canonical_replay_report(report: dict[str, object], bundle_name: str) -> dict[str, object]:
    value = json.loads(json.dumps(report))
    value["bundle_path"] = f"benchmark-conformance/{bundle_name}"
    return value


def prove_benchmark_conformance() -> dict[str, object]:
    evidence_root = OUT / "benchmark-conformance"
    evidence_root.mkdir(parents=True)
    fixture = ROOT / "tests" / "fixtures" / "benchmark_runner" / "task.json"

    with tempfile.TemporaryDirectory(prefix="axiom-repo-bench-") as directory:
        temporary = Path(directory)
        reference_first = run_conformance(
            ROOT,
            fixture,
            language="axiom",
            adapter="reference",
            output_directory=temporary / "reference-first",
        )
        reference_second = run_conformance(
            ROOT,
            fixture,
            language="axiom",
            adapter="reference",
            output_directory=temporary / "reference-second",
        )
        seeded_wrong = run_conformance(
            ROOT,
            fixture,
            language="axiom",
            adapter="seeded_wrong",
            output_directory=temporary / "seeded-wrong",
        )

        require(reference_first.conformance_passed, "reference conformance did not pass")
        require(reference_first.full_success, "reference conformance was not fully successful")
        require(reference_second.conformance_passed, "second reference conformance did not pass")
        require(
            reference_first.bundle_sha256 == reference_second.bundle_sha256,
            "reference conformance bundle hashes differ",
        )
        require(
            reference_first.bundle_path.read_bytes() == reference_second.bundle_path.read_bytes(),
            "reference conformance bundle bytes differ",
        )
        require(seeded_wrong.conformance_passed, "seeded-wrong harness conformance did not pass")
        require(not seeded_wrong.full_success, "seeded-wrong candidate unexpectedly succeeded")
        require(
            seeded_wrong.failure_reason == "acceptance_test_failure",
            "seeded-wrong candidate failed at the wrong phase",
        )

        reference_bundle = evidence_root / "reference.zip"
        seeded_wrong_bundle = evidence_root / "seeded-wrong.zip"
        shutil.copyfile(reference_first.bundle_path, reference_bundle)
        shutil.copyfile(seeded_wrong.bundle_path, seeded_wrong_bundle)
        (evidence_root / "reference-report.json").write_text(
            canonical_json(reference_first.report), encoding="utf-8"
        )
        (evidence_root / "seeded-wrong-report.json").write_text(
            canonical_json(seeded_wrong.report), encoding="utf-8"
        )

    reference_replay = replay_conformance(ROOT, reference_bundle)
    seeded_wrong_replay = replay_conformance(ROOT, seeded_wrong_bundle)
    require(reference_replay["status"] == "passed", "reference replay failed")
    require(seeded_wrong_replay["status"] == "passed", "seeded-wrong replay failed")
    require(reference_replay["subprocesses_executed"] == 0, "reference replay executed a process")
    require(
        seeded_wrong_replay["subprocesses_executed"] == 0,
        "seeded-wrong replay executed a process",
    )
    (evidence_root / "reference-replay.json").write_text(
        canonical_json(canonical_replay_report(reference_replay, "reference.zip")),
        encoding="utf-8",
    )
    (evidence_root / "seeded-wrong-replay.json").write_text(
        canonical_json(canonical_replay_report(seeded_wrong_replay, "seeded-wrong.zip")),
        encoding="utf-8",
    )

    summary = {
        "document_kind": "axiom.bench.trusted-conformance-proof",
        "schema_version": "0.1.0",
        "fixture": "tests/fixtures/benchmark_runner/task.json",
        "language": "axiom",
        "reference": {
            "conformance_passed": reference_first.conformance_passed,
            "full_success": reference_first.full_success,
            "bundle_sha256": digest(reference_bundle),
            "byte_reproducible": True,
            "replay_status": reference_replay["status"],
            "replay_subprocesses": reference_replay["subprocesses_executed"],
        },
        "seeded_wrong": {
            "conformance_passed": seeded_wrong.conformance_passed,
            "full_success": seeded_wrong.full_success,
            "failure_reason": seeded_wrong.failure_reason,
            "bundle_sha256": digest(seeded_wrong_bundle),
            "replay_status": seeded_wrong_replay["status"],
            "replay_subprocesses": seeded_wrong_replay["subprocesses_executed"],
        },
    }
    (evidence_root / "summary.json").write_text(canonical_json(summary), encoding="utf-8")
    return summary


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    ZIP.unlink(missing_ok=True)

    contract_result = check_project_contract(ROOT)
    (OUT / "project-contract.json").write_text(canonical_json(contract_result), encoding="utf-8")
    (OUT / "project-contract.txt").write_text(render_text(contract_result), encoding="utf-8")
    require(contract_result["status"] == "passed", "project contract consistency gate failed")

    benchmark_contract = check_benchmark_contract(ROOT)
    (OUT / "benchmark-contract.json").write_text(canonical_json(benchmark_contract), encoding="utf-8")
    require(benchmark_contract["status"] == "passed", "benchmark contract consistency gate failed")

    tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    normalized_test_stdout = normalize_test_log(tests.stdout)
    normalized_test_stderr = normalize_test_log(tests.stderr)
    (OUT / "tests.stdout.txt").write_text(normalized_test_stdout, encoding="utf-8")
    (OUT / "tests.stderr.txt").write_text(normalized_test_stderr, encoding="utf-8")
    (OUT / "tests.exit-code.txt").write_text(f"{tests.returncode}\n", encoding="ascii")
    require(tests.returncode == 0, "unit/integration tests failed")
    count_match = re.search(r"Ran (\d+) tests?", normalized_test_stdout + normalized_test_stderr)
    require(count_match is not None, "could not derive executed unit-test count")
    test_count = int(count_match.group(1))

    agent_b_dir = OUT / "agent-b"
    agent_b = run(
        [
            sys.executable,
            "agents/agent_b_review.py",
            "--root",
            ".",
            "--output",
            str(agent_b_dir),
        ]
    )
    (OUT / "agent-b.stdout.txt").write_text(agent_b.stdout, encoding="utf-8")
    (OUT / "agent-b.stderr.txt").write_text(agent_b.stderr, encoding="utf-8")
    (OUT / "agent-b.exit-code.txt").write_text(f"{agent_b.returncode}\n", encoding="ascii")
    require(agent_b.returncode == 0, "Agent B adversarial review failed")
    agent_b_report = json.loads((agent_b_dir / "agent-b-review.json").read_text(encoding="utf-8"))
    require(agent_b_report["status"] == "passed", "Agent B report is not passed")

    benchmark_conformance = prove_benchmark_conformance()

    cases = {
        "loop": ("loop.ax", 55, None),
        "normal": ("arithmetic_normal.ax", 17, None),
        "add-overflow": ("overflow_add.ax", 101, "i32_add_overflow"),
        "sub-overflow": ("overflow_sub.ax", 102, "i32_sub_overflow"),
        "mul-overflow": ("overflow_mul.ax", 103, "i32_mul_overflow"),
        "divide-zero": ("divide_zero.ax", 104, "i32_divide_by_zero"),
        "divide-overflow": ("divide_overflow.ax", 105, "i32_divide_overflow"),
        "remainder-zero": ("remainder_zero.ax", 106, "i32_remainder_by_zero"),
        "remainder-overflow": ("remainder_overflow.ax", 107, "i32_remainder_overflow"),
        "aggregates": ("aggregates.ax", 48, None),
        "aggregate-return": ("aggregate_return.ax", 42, None),
        "aggregate-assignment": ("aggregate_assignment.ax", 42, None),
        "nested-arrays": ("nested_arrays.ax", 42, None),
        "layout-value": ("layout.ax", 39, None),
        "bounds-upper": ("array_oob_runtime.ax", 108, "array_index_out_of_bounds"),
        "bounds-negative": ("negative_index_runtime.ax", 108, "array_index_out_of_bounds"),
        "lvalue-field": ("lvalue_field.ax", 42, None),
        "lvalue-array": ("lvalue_array.ax", 52, None),
        "lvalue-dynamic": ("lvalue_dynamic.ax", 42, None),
        "lvalue-nested": ("lvalue_nested.ax", 40, None),
        "lvalue-copy": ("lvalue_copy_independence.ax", 23, None),
        "lvalue-index-once": ("lvalue_index_once.ax", 42, None),
        "lvalue-oob-write": ("lvalue_oob_write.ax", 108, "array_index_out_of_bounds"),
        "lvalue-rhs-first": ("lvalue_rhs_first.ax", 104, "i32_divide_by_zero"),
        "ref-shared-call": ("ref_shared_call.ax", 42, None),
        "ref-mut-call": ("ref_mut_call.ax", 42, None),
        "ref-shared-alias": ("ref_shared_alias.ax", 42, None),
        "ref-field-mut": ("ref_field_mut.ax", 42, None),
        "ref-array-mut": ("ref_array_mut.ax", 44, None),
        "ref-local-shared": ("ref_local_shared.ax", 42, None),
        "ref-scope-release": ("ref_scope_release.ax", 42, None),
        "ref-argument-order": ("ref_argument_order.ax", 42, None),
        "ref-dynamic-once": ("ref_dynamic_once.ax", 42, None),
        "ref-forward": ("ref_forward.ax", 42, None),
        "ref-shared-local-alias": ("ref_shared_local_alias.ax", 42, None),
        "ref-shared-then-mut-scope": ("ref_shared_then_mut_scope.ax", 42, None),
        "ref-nested-call-release": ("ref_nested_call_release.ax", 42, None),
        "ref-oob": ("ref_oob.ax", 108, "array_index_out_of_bounds"),
    }
    results: dict[str, object] = {}
    for name, (fixture, expected_exit, expected_panic) in cases.items():
        result = prove(Path("examples") / fixture, OUT / "cases" / name)
        require(result["status"] == "passed", f"{name}: compile/proof failed")
        require(result["interpreter_exit_code"] == expected_exit, f"{name}: interpreter mismatch")
        require(result["native_exit_code"] == expected_exit, f"{name}: native mismatch")
        if expected_panic is not None:
            require(result["interpreter_outcome"]["panic_name"] == expected_panic, f"{name}: interpreter panic mismatch")
            require(result["native_panic_name"] == expected_panic, f"{name}: native panic mismatch")
        results[name] = result

    invalid_expected = {
        "invalid_i32_literal.ax": "AX-INT-0001",
        "invalid_constant_index.ax": "AX-INDEX-0001",
        "invalid_array_length.ax": "AX-ARRAY-0002",
        "invalid_array_element.ax": "AX-ARRAY-0003",
        "invalid_empty_array.ax": "AX-ARRAY-0001",
        "invalid_zero_array.ax": "AX-ARRAY-0004",
        "invalid_index_base.ax": "AX-INDEX-0002",
        "invalid_index_type.ax": "AX-INDEX-0003",
        "invalid_duplicate_struct.ax": "AX-STRUCT-0001",
        "invalid_struct_duplicate_field.ax": "AX-STRUCT-0002",
        "invalid_unknown_struct_literal.ax": "AX-STRUCT-0003",
        "invalid_struct_duplicate_literal.ax": "AX-STRUCT-0004",
        "invalid_struct_extra.ax": "AX-STRUCT-0005",
        "invalid_struct_missing.ax": "AX-STRUCT-0006",
        "invalid_struct_field_type.ax": "AX-STRUCT-0007",
        "invalid_field_access_base.ax": "AX-STRUCT-0008",
        "invalid_unknown_field.ax": "AX-STRUCT-0009",
        "invalid_empty_struct.ax": "AX-STRUCT-0010",
        "invalid_unknown_struct_type.ax": "AX-TYPE-0013",
        "invalid_recursive_struct.ax": "AX-TYPE-0014",
        "invalid_aggregate_equality.ax": "AX-TYPE-0015",
        "invalid_lvalue_temporary.ax": "AX-MUT-0002",
        "invalid_lvalue_immutable_field.ax": "AX-MUT-0001",
        "invalid_lvalue_immutable_index.ax": "AX-MUT-0001",
        "invalid_lvalue_type.ax": "AX-TYPE-0011",
        "invalid_lvalue_field_base.ax": "AX-STRUCT-0008",
        "invalid_lvalue_unknown_field.ax": "AX-STRUCT-0009",
        "invalid_lvalue_index_base.ax": "AX-INDEX-0002",
        "invalid_lvalue_index_type.ax": "AX-INDEX-0003",
        "invalid_lvalue_constant_oob.ax": "AX-INDEX-0001",
        "invalid_lvalue_parameter.ax": "AX-MUT-0001",
        "invalid_lvalue_temporary_field.ax": "AX-MUT-0002",
        "invalid_lvalue_binary.ax": "AX-MUT-0002",
        "invalid_ref_mut_immutable.ax": "AX-BORROW-0001",
        "invalid_ref_shared_during_mut.ax": "AX-BORROW-0002",
        "invalid_ref_mut_conflict.ax": "AX-BORROW-0003",
        "invalid_ref_read_during_mut.ax": "AX-BORROW-0004",
        "invalid_ref_write_during_shared.ax": "AX-BORROW-0005",
        "invalid_ref_shared_write.ax": "AX-BORROW-0006",
        "invalid_ref_reborrow.ax": "AX-BORROW-0007",
        "invalid_ref_duplicate_mut_value.ax": "AX-BORROW-0008",
        "invalid_ref_use_after_loan_in_args.ax": "AX-BORROW-0009",
        "invalid_ref_nested_call_loan.ax": "AX-BORROW-0009",
        "invalid_ref_return.ax": "AX-REF-0001",
        "invalid_ref_field.ax": "AX-REF-0002",
        "invalid_ref_array.ax": "AX-REF-0002",
        "invalid_ref_var_binding.ax": "AX-REF-0004",
        "invalid_ref_nonborrow_initializer.ax": "AX-REF-0005",
        "invalid_ref_deref_scalar.ax": "AX-REF-0006",
        "invalid_ref_temporary.ax": "AX-MUT-0002",
        "invalid_ref_two_mut_args.ax": "AX-BORROW-0003",
        "invalid_ref_argument_order.ax": "AX-BORROW-0004",
    }
    invalid_documents: dict[str, list[str]] = {}
    for fixture, expected_code in invalid_expected.items():
        invalid = compile_source(Path("examples") / fixture)
        codes = sorted({item.code for item in invalid["diagnostics"]})
        require(expected_code in codes, f"{fixture}: missing {expected_code}; got {codes}")
        invalid_documents[fixture] = codes
    (OUT / "invalid-diagnostics.json").write_text(canonical_json(invalid_documents), encoding="utf-8")

    layout_result = compile_source(Path("examples") / "layout.ax")
    require(not layout_result["diagnostics"], "layout fixture did not compile")
    semantic = layout_result["semantic"]
    assert semantic is not None
    layout_document = semantic.layout_document("Mixed")
    require(layout_document["layout"]["size"] == 28, "Mixed layout size mismatch")
    require(layout_document["layout"]["alignment"] == 4, "Mixed layout alignment mismatch")
    (OUT / "layout-mixed.json").write_text(canonical_json(layout_document), encoding="utf-8")

    manifest = {
        "document_kind": "axiom.repo-proof",
        "schema_version": "0.7.0",
        "status": "passed",
        "project_contract": {
            "status": contract_result["status"],
            "exit_code": contract_result["exit_code"],
            "validator": contract_result["validator"],
            "dependencies": contract_result["dependencies"],
            "current_features": contract_result["counts"]["current_features"],
            "deferred_features": contract_result["counts"]["deferred_features"],
            "findings": contract_result["counts"]["findings"],
        },
        "benchmark_contract": {
            "status": benchmark_contract["status"],
            "exit_code": benchmark_contract["exit_code"],
            "schemas_checked": benchmark_contract["schemas_checked"],
            "findings": benchmark_contract["finding_count"],
        },
        "benchmark_conformance": benchmark_conformance,
        "unit_test_exit_code": tests.returncode,
        "unit_tests": test_count,
        "agent_b": {
            "exit_code": agent_b.returncode,
            "passed": agent_b_report["passed"],
            "failed": agent_b_report["failed"],
        },
        "cases": {
            name: {
                "interpreter_exit_code": result["interpreter_exit_code"],
                "native_exit_code": result["native_exit_code"],
                "panic_name": result["native_panic_name"],
            }
            for name, result in results.items()
        },
        "invalid_diagnostics": invalid_documents,
        "layout": layout_document,
        "panic_code_map": {str(code): name for code, name in sorted(PANIC_NAMES.items())},
        "known_unproven": [
            "AXIOM-Bench 0.1 frozen suite, equal-spec language packs, real seed tasks, and frozen toolchains",
            "approved sandbox and live-model adapters for untrusted model output",
            "raw pointers, null pointers, pointer arithmetic, and unsafe blocks",
            "reference returns, reference fields, arrays of references, and reborrowing",
            "lifetime parameters, non-lexical lifetimes, and partial-field borrowing",
            "slices, heap allocation, and owned-resource destruction semantics",
            "broad cross-platform ABI stability",
            "complete effects and capability system",
            "Rust bootstrap parity",
            "self-hosting",
            "GPU execution",
        ],
        "files": {},
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
    manifest["files"] = {
        path.relative_to(OUT).as_posix(): digest(path)
        for path in sorted(OUT.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")

    write_deterministic_zip(OUT, ZIP)
    print(
        canonical_json({
            "status": "passed",
            "schema_version": "0.7.0",
            "evidence_zip": ZIP.as_posix(),
            "project_contract": contract_result["status"],
            "benchmark_contract": benchmark_contract["status"],
            "benchmark_schemas": benchmark_contract["schemas_checked"],
            "benchmark_conformance": benchmark_conformance,
            "unit_tests": test_count,
            "agent_b_checks": agent_b_report["passed"],
            "differential_cases": len(cases),
            "invalid_fixtures": len(invalid_expected),
            "evidence_sha256": digest(ZIP),
        }),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
