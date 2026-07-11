from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from hashlib import sha256
from pathlib import Path

from axiom_proof.arithmetic import PANIC_NAMES
from axiom_proof.driver import canonical_json, compile_source, prove

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "evidence" / "repo-proof"
ZIP = ROOT / "evidence" / "AXIOM_REPO_PROOF_EVIDENCE.zip"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    ZIP.unlink(missing_ok=True)

    tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    (OUT / "tests.stdout.txt").write_text(tests.stdout, encoding="utf-8")
    (OUT / "tests.stderr.txt").write_text(tests.stderr, encoding="utf-8")
    require(tests.returncode == 0, "unit tests failed")

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
    }
    results: dict[str, object] = {}
    for name, (fixture, expected_exit, expected_panic) in cases.items():
        result = prove(ROOT / "examples" / fixture, OUT / name)
        require(result["status"] == "passed", f"{name}: compile/proof failed")
        require(result["interpreter_exit_code"] == expected_exit, f"{name}: interpreter mismatch")
        require(result["native_exit_code"] == expected_exit, f"{name}: native mismatch")
        if expected_panic is not None:
            require(result["interpreter_outcome"]["panic_name"] == expected_panic, f"{name}: panic mismatch")
            require(result["native_panic_name"] == expected_panic, f"{name}: native panic mismatch")
        results[name] = result

    invalid = compile_source(ROOT / "examples" / "invalid_i32_literal.ax")
    invalid_codes = sorted({item.code for item in invalid["diagnostics"]})
    require("AX-INT-0001" in invalid_codes, "literal range diagnostic missing")

    manifest = {
        "document_kind": "axiom.repo-proof",
        "schema_version": "0.4.0",
        "status": "passed",
        "unit_test_exit_code": tests.returncode,
        "cases": {
            name: {
                "interpreter_exit_code": result["interpreter_exit_code"],
                "native_exit_code": result["native_exit_code"],
                "panic_name": result["native_panic_name"],
            }
            for name, result in results.items()
        },
        "invalid_diagnostics": invalid_codes,
        "panic_code_map": {str(code): name for code, name in sorted(PANIC_NAMES.items())},
        "files": {},
        "known_unproven": [
            "full ownership and lifetime semantics",
            "complete effects and capability system",
            "self-hosting",
            "GPU execution",
        ],
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
    manifest["files"] = {
        path.relative_to(OUT).as_posix(): digest(path)
        for path in sorted(OUT.rglob("*"))
        if path.is_file() and path != manifest_path
    }
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(OUT).as_posix())
    with zipfile.ZipFile(ZIP) as archive:
        require(archive.testzip() is None, "evidence ZIP CRC failure")

    print(canonical_json({"status": "passed", "evidence_zip": ZIP.as_posix(), "cases": len(cases)}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
