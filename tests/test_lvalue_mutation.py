from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from axiom_proof.arithmetic import PANIC_INDEX_OUT_OF_BOUNDS
from axiom_proof.driver import compile_source, prove
from axiom_proof.formatter import Formatter

ROOT = Path(__file__).resolve().parents[1]


class StructuredLValueTests(unittest.TestCase):
    def test_assignment_target_is_structured_and_roundtrips(self) -> None:
        result = compile_source(ROOT / "examples" / "lvalue_nested.ax")
        self.assertEqual(result["diagnostics"], [])
        program = result["program"]
        assert program is not None
        assignment = next(
            statement
            for statement in program.fields["functions"][0].fields["body"].fields["statements"]
            if statement.kind == "AssignmentStmt"
        )
        target = assignment.fields["target"]
        self.assertEqual(target.kind, "IndexExpr")
        self.assertEqual(target.fields["base"].kind, "IndexExpr")
        self.assertEqual(target.fields["base"].fields["base"].kind, "FieldExpr")
        formatted = Formatter().format(program)
        self.assertIn("holder.values[row][0] = 35;", formatted)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "formatted.ax"
            source.write_text(formatted, encoding="utf-8")
            reparsed = compile_source(source)
        self.assertEqual(reparsed["diagnostics"], [])

        def semantic_shape(value):
            if isinstance(value, dict):
                return {
                    key: semantic_shape(item)
                    for key, item in value.items()
                    if key not in {"node_id", "span"}
                }
            if isinstance(value, list):
                return [semantic_shape(item) for item in value]
            return value

        self.assertEqual(
            semantic_shape(result["ast"]["root"]),
            semantic_shape(reparsed["ast"]["root"]),
        )

    def test_field_array_dynamic_and_nested_mutation_match_native(self) -> None:
        cases = {
            "lvalue_field.ax": 42,
            "lvalue_array.ax": 52,
            "lvalue_dynamic.ax": 42,
            "lvalue_nested.ax": 40,
        }
        for fixture, expected in cases.items():
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as directory:
                result = prove(ROOT / "examples" / fixture, Path(directory))
                self.assertEqual(result["status"], "passed")
                self.assertEqual(result["interpreter_exit_code"], expected)
                self.assertEqual(result["native_exit_code"], expected)

    def test_out_of_bounds_write_matches_native(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(ROOT / "examples" / "lvalue_oob_write.ax", Path(directory))
            self.assertEqual(result["interpreter_exit_code"], PANIC_INDEX_OUT_OF_BOUNDS)
            self.assertEqual(result["native_exit_code"], PANIC_INDEX_OUT_OF_BOUNDS)
            self.assertEqual(result["native_panic_name"], "array_index_out_of_bounds")
            llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
            guard = llvm.index("icmp slt i32")
            gep = llvm.index("getelementptr [3 x i32]")
            store = llvm.index("store i32 99", gep)
            self.assertLess(guard, gep)
            self.assertLess(gep, store)


    def test_copy_by_value_remains_independent_after_subobject_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(ROOT / "examples" / "lvalue_copy_independence.ax", Path(directory))
            self.assertEqual(result["interpreter_exit_code"], 23)
            self.assertEqual(result["native_exit_code"], 23)

    def test_rhs_fault_precedes_lvalue_bounds_fault(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(ROOT / "examples" / "lvalue_rhs_first.ax", Path(directory))
            self.assertEqual(result["interpreter_exit_code"], 104)
            self.assertEqual(result["native_exit_code"], 104)
            self.assertEqual(result["native_panic_name"], "i32_divide_by_zero")

    def test_dynamic_write_index_is_evaluated_once(self) -> None:
        result = compile_source(ROOT / "examples" / "lvalue_index_once.ax")
        self.assertEqual(result["diagnostics"], [])
        program = result["program"]
        assert program is not None
        from axiom_proof.interpreter import Interpreter
        interpreter = Interpreter(program)
        self.assertEqual(interpreter.run_main(), 42)
        self.assertEqual(interpreter.call_count, 2)
        with tempfile.TemporaryDirectory() as directory:
            proof = prove(ROOT / "examples" / "lvalue_index_once.ax", Path(directory))
            self.assertEqual(proof["native_exit_code"], 42)
            llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
        self.assertEqual(llvm.count("call i32 @selected_index("), 1)

    def test_write_diagnostics_are_stable(self) -> None:
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
        for fixture, code in expected.items():
            with self.subTest(fixture=fixture):
                result = compile_source(ROOT / "examples" / fixture)
                self.assertIn(code, [diagnostic.code for diagnostic in result["diagnostics"]])

    def test_hir_effect_ownership_and_symbol_facts_expose_writes(self) -> None:
        result = compile_source(ROOT / "examples" / "lvalue_nested.ax")
        self.assertEqual(result["diagnostics"], [])
        semantic = result["semantic"]
        program = result["program"]
        assert semantic is not None and program is not None
        effects = next(item for item in semantic.effect_document()["functions"] if item["name"] == "main")
        self.assertEqual(effects["effects"], ["panic"])
        self.assertEqual(effects["local_facts"]["field_writes"], 1)
        self.assertEqual(effects["local_facts"]["index_writes"], 2)
        self.assertEqual(effects["local_facts"]["bounds_check_sites"], 1)
        references = semantic.symbol_document()["references"]
        self.assertIn("field_write", {item["kind"] for item in references})
        self.assertIn("index_write", {item["kind"] for item in references})
        from axiom_proof.hir import lower_program
        hir = lower_program(program, semantic.node_types)
        assignment = next(
            statement
            for statement in hir["functions"][0]["body"]
            if statement["op"] == "AssignmentStmt"
        )
        self.assertEqual(assignment["target"]["op"], "IndexExpr")

    def test_subobject_store_does_not_rewrite_whole_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prove(ROOT / "examples" / "lvalue_field.ax", Path(directory))
            llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
        assignment_gep = llvm.index("getelementptr %struct.Pair")
        scalar_store = llvm.index("store i32 20", assignment_gep)
        self.assertLess(assignment_gep, scalar_store)
        after_assignment = llvm[assignment_gep:]
        self.assertNotIn("store %struct.Pair", after_assignment)


if __name__ == "__main__":
    unittest.main()
