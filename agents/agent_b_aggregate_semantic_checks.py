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

def aggregate_ast_surface() -> dict[str, Any]:
        result = compile_source(fixture("aggregates.ax"))
        require(not result["diagnostics"], "aggregate fixture has diagnostics")
        assert result["ast"] is not None
        serialized = json.dumps(result["ast"], sort_keys=True)
        required = ["StructDecl", "StructLiteral", "ArrayLiteral", "FieldExpr", "IndexExpr"]
        for kind in required:
            require(f'"kind": "{kind}"' in serialized, f"aggregate AST missing {kind}")
        return {"kinds": required}

def aggregate_differential() -> dict[str, Any]:
        cases = {
            "aggregates.ax": 48,
            "aggregate_return.ax": 42,
            "aggregate_assignment.ax": 42,
            "nested_arrays.ax": 42,
        }
        results = {}
        for fixture, expected in cases.items():
            with tempfile.TemporaryDirectory() as directory:
                result = prove(Path("examples") / fixture, Path(directory))
                require(result["status"] == "passed", f"{fixture}: proof failed")
                require(result["interpreter_exit_code"] == expected, f"{fixture}: interpreter mismatch")
                require(result["native_exit_code"] == expected, f"{fixture}: native mismatch")
                results[fixture] = expected
        return results

def bounds_differential() -> dict[str, Any]:
        results = {}
        for fixture in ["array_oob_runtime.ax", "negative_index_runtime.ax"]:
            with tempfile.TemporaryDirectory() as directory:
                result = prove(Path("examples") / fixture, Path(directory))
                require(result["interpreter_exit_code"] == PANIC_INDEX_OUT_OF_BOUNDS, f"{fixture}: interpreter bounds code")
                require(result["native_exit_code"] == PANIC_INDEX_OUT_OF_BOUNDS, f"{fixture}: native bounds code")
                require(result["interpreter_outcome"]["kind"] == "bounds_fault", f"{fixture}: wrong outcome kind")
                require(result["native_panic_name"] == "array_index_out_of_bounds", f"{fixture}: wrong panic identity")
                llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
                require(llvm.index("icmp slt i32") < llvm.index("getelementptr"), f"{fixture}: negative guard after GEP")
                require(llvm.index("icmp sge i32") < llvm.index("getelementptr"), f"{fixture}: upper guard after GEP")
                results[fixture] = PANIC_INDEX_OUT_OF_BOUNDS
        return results

def aggregate_diagnostics() -> dict[str, str]:
        expected = {
            "invalid_constant_index.ax": "AX-INDEX-0001",
            "invalid_array_length.ax": "AX-ARRAY-0002",
            "invalid_array_element.ax": "AX-ARRAY-0003",
            "invalid_struct_missing.ax": "AX-STRUCT-0006",
            "invalid_struct_extra.ax": "AX-STRUCT-0005",
            "invalid_struct_duplicate_field.ax": "AX-STRUCT-0002",
            "invalid_struct_duplicate_literal.ax": "AX-STRUCT-0004",
            "invalid_struct_field_type.ax": "AX-STRUCT-0007",
            "invalid_unknown_field.ax": "AX-STRUCT-0009",
            "invalid_unknown_struct_type.ax": "AX-TYPE-0013",
            "invalid_recursive_struct.ax": "AX-TYPE-0014",
            "invalid_zero_array.ax": "AX-ARRAY-0004",
            "invalid_empty_struct.ax": "AX-STRUCT-0010",
            "invalid_duplicate_struct.ax": "AX-STRUCT-0001",
            "invalid_field_access_base.ax": "AX-STRUCT-0008",
            "invalid_index_base.ax": "AX-INDEX-0002",
            "invalid_index_type.ax": "AX-INDEX-0003",
            "invalid_aggregate_equality.ax": "AX-TYPE-0015",
            "invalid_empty_array.ax": "AX-ARRAY-0001",
            "invalid_unknown_struct_literal.ax": "AX-STRUCT-0003",
        }
        for fixture, code in expected.items():
            exact_diagnostic(fixture, code)
        return expected

def register() -> None:
    check("aggregate-ast-surface", aggregate_ast_surface)
    check("aggregate-interpreter-native-differential", aggregate_differential)
    check("array-bounds-differential", bounds_differential)
    check("aggregate-diagnostics", aggregate_diagnostics)
