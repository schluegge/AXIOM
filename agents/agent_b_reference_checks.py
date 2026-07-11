from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from axiom_proof.driver import compile_source, prove, structural_ast
from axiom_proof.formatter import Formatter
from .agent_b_support import check, exact_diagnostic, fixture, require, sha256, write_temp_source


def reference_surface_and_formatter() -> dict[str, Any]:
    result = compile_source(fixture("ref_mut_call.ax"))
    require(not result["diagnostics"], "mutable reference fixture has diagnostics")
    program = result["program"]
    assert program is not None and result["ast"] is not None
    serialized = json.dumps(result["ast"], sort_keys=True)
    for kind in ["BorrowExpr", "DerefExpr"]:
        require(f'"kind": "{kind}"' in serialized, f"AST missing {kind}")
    formatted = Formatter().format(program)
    require("value: &mut i32" in formatted, "formatter lost mutable reference type")
    require("*value = (*value + 1);" in formatted, "formatter lost dereference assignment")
    reparsed = compile_source(write_temp_source(formatted))
    require(not reparsed["diagnostics"], "formatted reference fixture did not compile")
    assert reparsed["ast"] is not None
    require(
        structural_ast(result["ast"]["root"]) == structural_ast(reparsed["ast"]["root"]),
        "reference formatter changed structural AST",
    )
    return {"kinds": ["BorrowExpr", "DerefExpr"], "roundtrip": True}


def reference_differential() -> dict[str, int]:
    cases = {
        "ref_shared_call.ax": 42,
        "ref_mut_call.ax": 42,
        "ref_shared_alias.ax": 42,
        "ref_field_mut.ax": 42,
        "ref_array_mut.ax": 44,
        "ref_local_shared.ax": 42,
        "ref_scope_release.ax": 42,
        "ref_argument_order.ax": 42,
        "ref_dynamic_once.ax": 42,
        "ref_forward.ax": 42,
        "ref_shared_local_alias.ax": 42,
        "ref_shared_then_mut_scope.ax": 42,
        "ref_nested_call_release.ax": 42,
    }
    for name, expected in cases.items():
        with tempfile.TemporaryDirectory() as directory:
            result = prove(fixture(name), Path(directory))
            require(result["status"] == "passed", f"{name}: proof failed")
            require(result["interpreter_exit_code"] == expected, f"{name}: interpreter mismatch")
            require(result["native_exit_code"] == expected, f"{name}: native mismatch")
    return cases


def reference_diagnostics() -> dict[str, str]:
    expected = {
        "invalid_ref_mut_immutable.ax": "AX-BORROW-0001",
        "invalid_ref_shared_during_mut.ax": "AX-BORROW-0002",
        "invalid_ref_mut_conflict.ax": "AX-BORROW-0003",
        "invalid_ref_read_during_mut.ax": "AX-BORROW-0004",
        "invalid_ref_write_during_shared.ax": "AX-BORROW-0005",
        "invalid_ref_shared_write.ax": "AX-BORROW-0006",
        "invalid_ref_reborrow.ax": "AX-BORROW-0007",
        "invalid_ref_duplicate_mut_value.ax": "AX-BORROW-0008",
        "invalid_ref_use_after_loan_in_args.ax": "AX-BORROW-0009",
        "invalid_ref_return.ax": "AX-REF-0001",
        "invalid_ref_field.ax": "AX-REF-0002",
        "invalid_ref_array.ax": "AX-REF-0002",
        "invalid_ref_var_binding.ax": "AX-REF-0004",
        "invalid_ref_nonborrow_initializer.ax": "AX-REF-0005",
        "invalid_ref_deref_scalar.ax": "AX-REF-0006",
        "invalid_ref_temporary.ax": "AX-MUT-0002",
        "invalid_ref_two_mut_args.ax": "AX-BORROW-0003",
        "invalid_ref_argument_order.ax": "AX-BORROW-0004",
        "invalid_ref_nested_call_loan.ax": "AX-BORROW-0009",
    }
    for name, code in expected.items():
        exact_diagnostic(name, code)
    return expected


def borrow_scope_and_argument_order() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        scope = prove(fixture("ref_scope_release.ax"), Path(directory) / "scope")
        order = prove(fixture("ref_argument_order.ax"), Path(directory) / "order")
        nested = prove(fixture("ref_nested_call_release.ax"), Path(directory) / "nested")
    require(scope["native_exit_code"] == 42, "borrow did not end at block boundary")
    require(order["native_exit_code"] == 42, "left-to-right copied argument case failed")
    require(nested["native_exit_code"] == 42, "inner mutable loan did not release before the next outer argument")
    exact_diagnostic("invalid_ref_argument_order.ax", "AX-BORROW-0004")
    exact_diagnostic("invalid_ref_duplicate_mut_value.ax", "AX-BORROW-0008")
    exact_diagnostic("invalid_ref_use_after_loan_in_args.ax", "AX-BORROW-0009")
    exact_diagnostic("invalid_ref_nested_call_loan.ax", "AX-BORROW-0009")
    return {"lexical_release": True, "left_to_right": True, "nested_inner_release": True, "mutable_loan_linear_per_call": True}


def dynamic_borrow_address() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        valid = prove(fixture("ref_dynamic_once.ax"), root / "valid")
        oob = prove(fixture("ref_oob.ax"), root / "oob")
        llvm = (root / "valid" / "program.ll").read_text(encoding="utf-8")
        oob_llvm = (root / "oob" / "program.ll").read_text(encoding="utf-8")
    require(valid["native_exit_code"] == 42, "dynamic borrow valid result mismatch")
    require(llvm.count("call i32 @index()") == 1, "dynamic borrow index evaluated more than once")
    require(oob["interpreter_exit_code"] == 108 and oob["native_exit_code"] == 108, "borrow OOB mismatch")
    require(oob_llvm.index("icmp slt i32") < oob_llvm.index("getelementptr [2 x i32]"), "borrow GEP precedes bounds guard")
    return {"index_calls": 1, "oob_code": 108, "guard_before_gep": True}


def pointer_lowering_shape() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        proof = prove(fixture("ref_field_mut.ax"), Path(directory))
        llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
    require(proof["status"] == "passed", "field reference proof failed")
    require("define i32 @set(ptr %arg0)" in llvm, "reference parameter is not a pointer")
    require("load ptr, ptr" in llvm, "reference pointer is not loaded from parameter storage")
    require("getelementptr %struct.Pair" in llvm, "field borrow lacks GEP")
    require("store i32 40, ptr" in llvm, "mutable reference lacks direct referent store")
    require("inttoptr" not in llvm and "ptrtoint" not in llvm, "reference lowering forges/converts pointer integers")
    require("null" not in llvm, "reference lowering introduced null")
    return {"pointer_parameter": True, "direct_store": True, "no_pointer_forging": True}


def reference_documents() -> dict[str, Any]:
    result = compile_source(fixture("ref_field_mut.ax"))
    require(not result["diagnostics"], "reference document fixture has diagnostics")
    semantic = result["semantic"]
    assert semantic is not None
    ownership = semantic.ownership_document()
    require(ownership["mode"] == "copy_values_with_scoped_non_escaping_references", "ownership mode missing")
    require(ownership["reference_policy"]["non_null"], "references are not documented non-null")
    require(not ownership["reference_policy"]["reference_returns"], "reference returns unexpectedly enabled")
    require(len(ownership["borrows"]) == 1 and ownership["borrows"][0]["mutable"], "mutable borrow event missing")
    kinds = {item["kind"] for item in semantic.symbol_document()["references"]}
    require({"mutable_borrow", "dereference_write"} <= kinds, "reference symbol facts missing")
    return {"borrows": len(ownership["borrows"]), "kinds": sorted(kinds)}


def generated_reference_matrix() -> dict[str, Any]:
    exits: list[int] = []
    for initial, delta in [(0, 42), (1, 41), (7, 35), (20, 22), (40, 2), (100, -58)]:
        expression = str(delta) if delta >= 0 else f"0 - {abs(delta)}"
        source_text = f"""profile system;
fn add(value: &mut i32) -> i32 {{
    *value = *value + {expression};
    return *value;
}}
fn main() -> i32 {{
    var value: i32 = {initial};
    return add(&mut value);
}}
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "generated.ax"
            source.write_text(source_text, encoding="utf-8")
            result = prove(source, Path(directory) / "proof")
            expected = initial + delta
            require(result["interpreter_exit_code"] == expected, "generated reference interpreter mismatch")
            require(result["native_exit_code"] == expected, "generated reference native mismatch")
            exits.append(expected)
    return {"cases": len(exits), "exit_codes": exits}


def reference_determinism() -> dict[str, str]:
    with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
        first = Path(first_dir)
        second = Path(second_dir)
        prove(fixture("ref_field_mut.ax"), first)
        prove(fixture("ref_field_mut.ax"), second)
        names = [
            "tokens.json", "ast.json", "formatted.ax", "symbols.json", "types.json",
            "effects.json", "ownership.json", "layouts.json", "hir.json",
            "control-flow.json", "interpreter.json", "program.ll", "differential.json",
        ]
        hashes: dict[str, str] = {}
        for name in names:
            left = sha256(first / name)
            right = sha256(second / name)
            require(left == right, f"reference non-determinism: {name}")
            hashes[name] = left
        return hashes


def register() -> None:
    check("reference-surface-and-formatter", reference_surface_and_formatter)
    check("reference-interpreter-native-differential", reference_differential)
    check("reference-stable-diagnostics", reference_diagnostics)
    check("reference-scope-and-argument-order", borrow_scope_and_argument_order)
    check("reference-dynamic-address-and-bounds", dynamic_borrow_address)
    check("reference-pointer-lowering-shape", pointer_lowering_shape)
    check("reference-ownership-and-symbol-documents", reference_documents)
    check("reference-generated-matrix", generated_reference_matrix)
    check("reference-deterministic-outputs", reference_determinism)
