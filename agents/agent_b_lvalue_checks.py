from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from axiom_proof.arithmetic import PANIC_DIVIDE_BY_ZERO, PANIC_INDEX_OUT_OF_BOUNDS
from axiom_proof.driver import compile_source, prove
from axiom_proof.formatter import Formatter
from axiom_proof.hir import lower_program
from axiom_proof.interpreter import Interpreter
from .agent_b_support import check, exact_diagnostic, fixture, require, sha256, write_temp_source


def structured_target_and_formatter() -> dict[str, Any]:
    result = compile_source(fixture("lvalue_nested.ax"))
    require(not result["diagnostics"], "nested l-value fixture has diagnostics")
    program = result["program"]
    assert program is not None
    assignment = next(
        statement
        for statement in program.fields["functions"][0].fields["body"].fields["statements"]
        if statement.kind == "AssignmentStmt"
    )
    target = assignment.fields["target"]
    require(target.kind == "IndexExpr", "outer target is not IndexExpr")
    require(target.fields["base"].kind == "IndexExpr", "nested target lost inner index")
    require(target.fields["base"].fields["base"].kind == "FieldExpr", "nested target lost field")
    formatted = Formatter().format(program)
    require("holder.values[row][0] = 35;" in formatted, "formatter lost structured target")
    reparsed = compile_source(write_temp_source(formatted))
    require(not reparsed["diagnostics"], "formatted structured l-value did not recompile")
    return {"target": "IndexExpr(IndexExpr(FieldExpr(NameExpr)))", "roundtrip": True}


def mutation_differential() -> dict[str, int]:
    cases = {
        "lvalue_field.ax": 42,
        "lvalue_array.ax": 52,
        "lvalue_dynamic.ax": 42,
        "lvalue_nested.ax": 40,
        "lvalue_copy_independence.ax": 23,
        "lvalue_index_once.ax": 42,
    }
    results: dict[str, int] = {}
    for name, expected in cases.items():
        with tempfile.TemporaryDirectory() as directory:
            result = prove(fixture(name), Path(directory))
            require(result["status"] == "passed", f"{name}: proof failed")
            require(result["interpreter_exit_code"] == expected, f"{name}: interpreter mismatch")
            require(result["native_exit_code"] == expected, f"{name}: native mismatch")
            results[name] = expected
    return results


def write_bounds_and_order() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        bounds = prove(fixture("lvalue_oob_write.ax"), Path(directory) / "bounds")
        require(bounds["interpreter_exit_code"] == PANIC_INDEX_OUT_OF_BOUNDS, "write OOB interpreter mismatch")
        require(bounds["native_exit_code"] == PANIC_INDEX_OUT_OF_BOUNDS, "write OOB native mismatch")
        llvm = (Path(directory) / "bounds" / "program.ll").read_text(encoding="utf-8")
        guard = llvm.index("icmp slt i32")
        gep = llvm.index("getelementptr [3 x i32]")
        store = llvm.index("store i32 99", gep)
        require(guard < gep < store, "write bounds guard/GEP/store order is wrong")

        order = prove(fixture("lvalue_rhs_first.ax"), Path(directory) / "order")
        require(order["interpreter_exit_code"] == PANIC_DIVIDE_BY_ZERO, "interpreter did not evaluate RHS first")
        require(order["native_exit_code"] == PANIC_DIVIDE_BY_ZERO, "native code did not evaluate RHS first")
        return {"bounds_code": 108, "rhs_first_code": 104, "guard_before_gep_before_store": True}


def dynamic_index_once() -> dict[str, Any]:
    result = compile_source(fixture("lvalue_index_once.ax"))
    require(not result["diagnostics"], "index-once fixture has diagnostics")
    program = result["program"]
    assert program is not None
    interpreter = Interpreter(program)
    require(interpreter.run_main() == 42, "index-once interpreter result mismatch")
    require(interpreter.call_count == 2, f"index function evaluated more than once: calls={interpreter.call_count}")
    with tempfile.TemporaryDirectory() as directory:
        proof = prove(fixture("lvalue_index_once.ax"), Path(directory))
        llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
    require(proof["native_exit_code"] == 42, "index-once native result mismatch")
    require(llvm.count("call i32 @selected_index(") == 1, "native index function call count is not one")
    return {"interpreter_calls_including_main": 2, "native_index_calls": 1}


def stable_write_diagnostics() -> dict[str, str]:
    expected = {
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
    for name, code in expected.items():
        exact_diagnostic(name, code)
    return expected


def mutation_documents() -> dict[str, Any]:
    result = compile_source(fixture("lvalue_nested.ax"))
    require(not result["diagnostics"], "nested l-value fixture has diagnostics")
    semantic = result["semantic"]
    program = result["program"]
    assert semantic is not None and program is not None
    facts = next(item for item in semantic.effect_document()["functions"] if item["name"] == "main")
    require(facts["local_facts"]["field_writes"] == 1, "field write count mismatch")
    require(facts["local_facts"]["index_writes"] == 2, "index write count mismatch")
    require(facts["local_facts"]["bounds_check_sites"] == 1, "write bounds fact mismatch")
    reference_kinds = {item["kind"] for item in semantic.symbol_document()["references"]}
    require("field_write" in reference_kinds and "index_write" in reference_kinds, "write references missing")
    hir = lower_program(program, semantic.node_types)
    assignment = next(item for item in hir["functions"][0]["body"] if item["op"] == "AssignmentStmt")
    require(assignment["target"]["op"] == "IndexExpr", "HIR target is not structured")
    return {"facts": facts["local_facts"], "reference_kinds": sorted(reference_kinds)}


def direct_subobject_store_shape() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        prove(fixture("lvalue_field.ax"), Path(directory) / "field")
        field_llvm = (Path(directory) / "field" / "program.ll").read_text(encoding="utf-8")
        gep = field_llvm.index("getelementptr %struct.Pair")
        store = field_llvm.index("store i32 20", gep)
        require(gep < store, "field GEP does not precede scalar store")
        require("store %struct.Pair" not in field_llvm[gep:], "field write rewrote whole struct")

        prove(fixture("lvalue_nested.ax"), Path(directory) / "nested")
        nested_llvm = (Path(directory) / "nested" / "program.ll").read_text(encoding="utf-8")
        require(nested_llvm.count("getelementptr") >= 3, "nested l-value missing GEP chain")
        require("store i32 35" in nested_llvm, "nested scalar store missing")
        return {"field_direct_store": True, "nested_geps": nested_llvm.count("getelementptr")}


def generated_write_matrix() -> dict[str, Any]:
    cases = [
        ([1, 2, 3, 4], 0, 20),
        ([10, 20, 30, 40], 1, 2),
        ([4, 8, 15, 16], 2, 9),
        ([31, 6, 27, 4], 3, 12),
        ([0, 1, 2, 3], 0, 7),
        ([7, 6, 5, 4], 1, 8),
        ([3, 1, 4, 1], 2, 5),
        ([9, 2, 6, 5], 3, 3),
    ]
    exits: list[int] = []
    for values, index, replacement in cases:
        expected = sum(values) - values[index] + replacement
        source_text = f"""profile system;
fn main() -> i32 {{
    var values: [i32; 4] = [{values[0]}, {values[1]}, {values[2]}, {values[3]}];
    let index: i32 = {index};
    values[index] = {replacement};
    return values[0] + values[1] + values[2] + values[3];
}}
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "generated.ax"
            source.write_text(source_text, encoding="utf-8")
            result = prove(source, Path(directory) / "proof")
            require(result["interpreter_exit_code"] == expected, "generated write interpreter mismatch")
            require(result["native_exit_code"] == expected, "generated write native mismatch")
            exits.append(expected)
    for index in [-3, -1, 4, 12]:
        expression = str(index) if index >= 0 else f"0 - {abs(index)}"
        source_text = f"""profile system;
fn main() -> i32 {{
    var values: [i32; 4] = [1, 2, 3, 4];
    let index: i32 = {expression};
    values[index] = 9;
    return 0;
}}
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "generated-oob.ax"
            source.write_text(source_text, encoding="utf-8")
            result = prove(source, Path(directory) / "proof")
            require(result["interpreter_exit_code"] == 108, "generated OOB write interpreter mismatch")
            require(result["native_exit_code"] == 108, "generated OOB write native mismatch")
    return {"valid_cases": len(cases), "oob_cases": 4, "exit_codes": exits}


def mutation_determinism() -> dict[str, str]:
    with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
        first = Path(first_dir)
        second = Path(second_dir)
        prove(fixture("lvalue_nested.ax"), first)
        prove(fixture("lvalue_nested.ax"), second)
        names = [
            "tokens.json", "ast.json", "formatted.ax", "symbols.json", "types.json",
            "effects.json", "ownership.json", "layouts.json", "hir.json",
            "control-flow.json", "interpreter.json", "program.ll", "differential.json",
        ]
        hashes: dict[str, str] = {}
        for name in names:
            left = sha256(first / name)
            right = sha256(second / name)
            require(left == right, f"l-value non-determinism: {name}")
            hashes[name] = left
        return hashes


def register() -> None:
    check("lvalue-structured-target-and-formatter", structured_target_and_formatter)
    check("lvalue-interpreter-native-differential", mutation_differential)
    check("lvalue-write-bounds-and-evaluation-order", write_bounds_and_order)
    check("lvalue-dynamic-index-evaluated-once", dynamic_index_once)
    check("lvalue-stable-diagnostics", stable_write_diagnostics)
    check("lvalue-structured-documents", mutation_documents)
    check("lvalue-direct-subobject-store-shape", direct_subobject_store_shape)
    check("lvalue-generated-write-matrix", generated_write_matrix)
    check("lvalue-deterministic-outputs", mutation_determinism)
