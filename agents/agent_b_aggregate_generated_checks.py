from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from axiom_proof.arithmetic import PANIC_INDEX_OUT_OF_BOUNDS
from axiom_proof.driver import compile_source, prove
from axiom_proof.llvm_backend import LLVMBackend
from .agent_b_support import ROOT, check, exact_diagnostic, fixture, require, sha256

def generated_aggregate_matrix() -> dict[str, Any]:
        cases = [
            ([31, 6, 27, 4], 1, 5, 7),
            ([0, 1, 2, 3], 3, 20, 19),
            ([40, 39, 38, 37], 0, 1, 1),
            ([11, 12, 13, 14], 2, 7, 9),
            ([8, 5, 3, 2], 0, 21, 13),
            ([17, 0, 19, 4], 2, 8, 6),
            ([4, 9, 16, 25], 1, 4, 5),
            ([33, 22, 11, 0], 3, 30, 10),
        ]
        valid_results: list[int] = []
        for values, index, left, right in cases:
            expected = values[index] + left + right
            source_text = f"""profile system;

struct Pair {{
    left: i32,
    right: i32,
}}

fn sum_pair(value: Pair) -> i32 {{
    return value.left + value.right;
}}

fn main() -> i32 {{
    let values: [i32; 4] = [{values[0]}, {values[1]}, {values[2]}, {values[3]}];
    let index: i32 = {index};
    let pair: Pair = Pair {{ left: {left}, right: {right} }};
    return values[index] + sum_pair(pair);
}}
"""
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "generated.ax"
                source.write_text(source_text, encoding="utf-8")
                result = prove(source, Path(directory) / "proof")
                require(result["status"] == "passed", "generated aggregate proof failed")
                require(result["interpreter_exit_code"] == expected, "generated interpreter mismatch")
                require(result["native_exit_code"] == expected, "generated native mismatch")
                valid_results.append(expected)

        for index in [-20, -2, 4, 17]:
            index_expression = str(index) if index >= 0 else f"0 - {abs(index)}"
            source_text = f"""profile system;
fn main() -> i32 {{
    let values: [i32; 4] = [1, 2, 3, 4];
    let index: i32 = {index_expression};
    return values[index];
}}
"""
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "generated-oob.ax"
                source.write_text(source_text, encoding="utf-8")
                result = prove(source, Path(directory) / "proof")
                require(result["interpreter_exit_code"] == PANIC_INDEX_OUT_OF_BOUNDS, "generated OOB interpreter mismatch")
                require(result["native_exit_code"] == PANIC_INDEX_OUT_OF_BOUNDS, "generated OOB native mismatch")
        return {"valid_cases": len(valid_results), "oob_cases": 4, "exit_codes": valid_results}

def aggregate_determinism() -> dict[str, str]:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            prove(fixture("aggregates.ax"), first)
            prove(fixture("aggregates.ax"), second)
            names = [
                "tokens.json", "ast.json", "formatted.ax", "symbols.json", "types.json",
                "effects.json", "ownership.json", "layouts.json", "hir.json",
                "control-flow.json", "interpreter.json", "program.ll", "differential.json",
            ]
            hashes = {}
            for name in names:
                first_hash = sha256(first / name)
                second_hash = sha256(second / name)
                require(first_hash == second_hash, f"aggregate non-determinism: {name}")
                hashes[name] = first_hash
            return hashes

def register() -> None:
    check("aggregate-deterministic-outputs", aggregate_determinism)
    check("generated-aggregate-matrix", generated_aggregate_matrix)
