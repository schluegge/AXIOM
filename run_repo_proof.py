from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from hashlib import sha256
from pathlib import Path

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
    # unittest reports wall-clock duration, which is useful interactively but
    # makes the Evidence archive byte-unstable. Preserve every test name and
    # result while removing only the volatile elapsed-time field.
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


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    ZIP.unlink(missing_ok=True)

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
        "schema_version": "0.6.0",
        "status": "passed",
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
            "references, borrowing, and owned-resource semantics",
            "slices and pointer syntax",
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
            "schema_version": "0.6.0",
            "evidence_zip": ZIP.as_posix(),
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
