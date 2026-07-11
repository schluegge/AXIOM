from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from axiom_proof.driver import compile_source, prove, structural_ast
from axiom_proof.formatter import Formatter

ROOT = Path(__file__).resolve().parents[1]


class ScopedReferenceTests(unittest.TestCase):
    def compile(self, fixture: str):
        return compile_source(ROOT / "examples" / fixture)

    def prove(self, fixture: str):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)
        return prove(ROOT / "examples" / fixture, path), path

    def test_reference_ast_types_and_formatter_roundtrip(self) -> None:
        result = self.compile("ref_mut_call.ax")
        self.assertEqual([], result["diagnostics"])
        program = result["program"]
        assert program is not None and result["ast"] is not None
        formatted = Formatter().format(program)
        self.assertIn("value: &mut i32", formatted)
        self.assertIn("*value = (*value + 1);", formatted)
        self.assertIn("increment(&mut value)", formatted)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "formatted.ax"
            path.write_text(formatted, encoding="utf-8")
            reparsed = compile_source(path)
        self.assertEqual([], reparsed["diagnostics"])
        assert reparsed["ast"] is not None
        self.assertEqual(
            structural_ast(result["ast"]["root"]),
            structural_ast(reparsed["ast"]["root"]),
        )

    def test_shared_mutable_alias_and_forwarding_match_native(self) -> None:
        expected = {
            "ref_shared_call.ax": 42,
            "ref_mut_call.ax": 42,
            "ref_shared_alias.ax": 42,
            "ref_forward.ax": 42,
            "ref_local_shared.ax": 42,
            "ref_scope_release.ax": 42,
            "ref_argument_order.ax": 42,
            "ref_shared_local_alias.ax": 42,
            "ref_shared_then_mut_scope.ax": 42,
            "ref_nested_call_release.ax": 42,
        }
        for fixture, exit_code in expected.items():
            with self.subTest(fixture=fixture):
                result, _ = self.prove(fixture)
                self.assertEqual("passed", result["status"])
                self.assertEqual(exit_code, result["interpreter_exit_code"])
                self.assertEqual(exit_code, result["native_exit_code"])

    def test_field_and_array_reference_mutation_match_native(self) -> None:
        expected = {"ref_field_mut.ax": 42, "ref_array_mut.ax": 44}
        for fixture, exit_code in expected.items():
            with self.subTest(fixture=fixture):
                result, _ = self.prove(fixture)
                self.assertEqual("passed", result["status"])
                self.assertEqual(exit_code, result["interpreter_exit_code"])
                self.assertEqual(exit_code, result["native_exit_code"])

    def test_dynamic_borrow_index_is_evaluated_once(self) -> None:
        result, path = self.prove("ref_dynamic_once.ax")
        self.assertEqual("passed", result["status"])
        self.assertEqual(42, result["native_exit_code"])
        interpreter = json.loads((path / "interpreter.json").read_text(encoding="utf-8"))
        self.assertEqual(3, interpreter["function_calls"])
        llvm = (path / "program.ll").read_text(encoding="utf-8")
        self.assertEqual(1, llvm.count("call i32 @index()"))

    def test_out_of_bounds_borrow_matches_runtime_panic(self) -> None:
        result, path = self.prove("ref_oob.ax")
        self.assertEqual("passed", result["status"])
        self.assertEqual(108, result["interpreter_exit_code"])
        self.assertEqual(108, result["native_exit_code"])
        self.assertEqual("array_index_out_of_bounds", result["native_panic_name"])
        llvm = (path / "program.ll").read_text(encoding="utf-8")
        guard = llvm.index("icmp slt i32")
        gep = llvm.index("getelementptr [2 x i32]")
        call = llvm.index("call i32 @read(ptr")
        self.assertLess(guard, gep)
        self.assertLess(gep, call)

    def test_reference_diagnostics_are_stable(self) -> None:
        expected = {
            "invalid_ref_mut_immutable.ax": "AX-BORROW-0001",
            "invalid_ref_shared_during_mut.ax": "AX-BORROW-0002",
            "invalid_ref_mut_conflict.ax": "AX-BORROW-0003",
            "invalid_ref_read_during_mut.ax": "AX-BORROW-0004",
            "invalid_ref_write_during_shared.ax": "AX-BORROW-0005",
            "invalid_ref_shared_write.ax": "AX-BORROW-0006",
            "invalid_ref_reborrow.ax": "AX-BORROW-0007",
            "invalid_ref_return.ax": "AX-REF-0001",
            "invalid_ref_field.ax": "AX-REF-0002",
            "invalid_ref_array.ax": "AX-REF-0002",
            "invalid_ref_var_binding.ax": "AX-REF-0004",
            "invalid_ref_nonborrow_initializer.ax": "AX-REF-0005",
            "invalid_ref_deref_scalar.ax": "AX-REF-0006",
            "invalid_ref_temporary.ax": "AX-MUT-0002",
            "invalid_ref_two_mut_args.ax": "AX-BORROW-0003",
            "invalid_ref_argument_order.ax": "AX-BORROW-0004",
            "invalid_ref_duplicate_mut_value.ax": "AX-BORROW-0008",
            "invalid_ref_use_after_loan_in_args.ax": "AX-BORROW-0009",
            "invalid_ref_nested_call_loan.ax": "AX-BORROW-0009",
        }
        for fixture, code in expected.items():
            with self.subTest(fixture=fixture):
                codes = {item.code for item in self.compile(fixture)["diagnostics"]}
                self.assertIn(code, codes)

    def test_ownership_and_symbol_documents_expose_borrows(self) -> None:
        result = self.compile("ref_field_mut.ax")
        self.assertEqual([], result["diagnostics"])
        semantic = result["semantic"]
        assert semantic is not None
        ownership = semantic.ownership_document()
        self.assertEqual("copy_values_with_scoped_non_escaping_references", ownership["mode"])
        self.assertTrue(ownership["reference_policy"]["non_null"])
        self.assertFalse(ownership["reference_policy"]["reference_returns"])
        self.assertEqual(1, len(ownership["borrows"]))
        self.assertTrue(ownership["borrows"][0]["mutable"])
        symbols = semantic.symbol_document()
        kinds = {item["kind"] for item in symbols["references"]}
        self.assertIn("mutable_borrow", kinds)
        self.assertIn("dereference_write", kinds)
        facts = {item["name"]: item["local_facts"] for item in semantic.effect_document()["functions"]}
        self.assertEqual(1, facts["main"]["mutable_borrows"])
        self.assertEqual(1, facts["set"]["deref_writes"])

    def test_llvm_uses_pointer_parameters_and_direct_deref_stores(self) -> None:
        result, path = self.prove("ref_mut_call.ax")
        self.assertEqual("passed", result["status"])
        llvm = (path / "program.ll").read_text(encoding="utf-8")
        self.assertIn("define i32 @increment(ptr %arg0)", llvm)
        self.assertIn("alloca ptr", llvm)
        self.assertIn("load ptr, ptr", llvm)
        pointer_load = llvm.index("load ptr, ptr")
        referent_load = llvm.index("load i32, ptr", pointer_load)
        referent_store = llvm.index("store i32", referent_load)
        self.assertLess(pointer_load, referent_load)
        self.assertLess(referent_load, referent_store)

    def test_left_to_right_argument_borrowing(self) -> None:
        valid, _ = self.prove("ref_argument_order.ax")
        self.assertEqual("passed", valid["status"])
        invalid = self.compile("invalid_ref_argument_order.ax")
        self.assertIn("AX-BORROW-0004", {item.code for item in invalid["diagnostics"]})

    def test_nested_call_releases_inner_loan_but_holds_outer_loan(self) -> None:
        valid, _ = self.prove("ref_nested_call_release.ax")
        self.assertEqual("passed", valid["status"])
        self.assertEqual(42, valid["interpreter_exit_code"])
        self.assertEqual(42, valid["native_exit_code"])
        invalid = self.compile("invalid_ref_nested_call_loan.ax")
        self.assertIn("AX-BORROW-0009", {item.code for item in invalid["diagnostics"]})

    def test_reference_outputs_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = prove(ROOT / "examples" / "ref_field_mut.ax", Path(first))
            two = prove(ROOT / "examples" / "ref_field_mut.ax", Path(second))
            self.assertEqual("passed", one["status"])
            self.assertEqual("passed", two["status"])
            for name in ["ast.json", "formatted.ax", "hir.json", "symbols.json", "types.json", "ownership.json", "program.ll", "differential.json"]:
                self.assertEqual(
                    (Path(first) / name).read_bytes(),
                    (Path(second) / name).read_bytes(),
                    name,
                )


if __name__ == "__main__":
    unittest.main()
