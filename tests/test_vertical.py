from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from axiom_proof.arithmetic import (
    PANIC_ADD_OVERFLOW,
    PANIC_DIVIDE_BY_ZERO,
    PANIC_DIVIDE_OVERFLOW,
    PANIC_MUL_OVERFLOW,
    PANIC_REMAINDER_BY_ZERO,
    PANIC_REMAINDER_OVERFLOW,
    PANIC_SUB_OVERFLOW,
    ArithmeticFault,
    checked_add,
    checked_mul,
    checked_sub,
    truncating_division,
    truncating_remainder,
)
from axiom_proof.control_flow import build_control_flow_document
from axiom_proof.driver import compile_source, prove
from axiom_proof.interpreter import Interpreter

ROOT = Path(__file__).resolve().parents[1]


class VerticalProofTests(unittest.TestCase):
    def test_valid_program_proves_native_differential(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(ROOT / "examples" / "vertical.ax", Path(directory))
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["interpreter_exit_code"], 55)
            self.assertEqual(result["native_exit_code"], 55)

    def test_loop_and_mutation_prove_native_differential(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(ROOT / "examples" / "loop.ax", Path(directory))
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["interpreter_exit_code"], 55)
            self.assertEqual(result["native_exit_code"], 55)

    def test_nested_block_assignment_mutates_outer_variable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(ROOT / "examples" / "mutation_if.ax", Path(directory))
            self.assertEqual(result["interpreter_exit_code"], 9)
            self.assertEqual(result["native_exit_code"], 9)

    def test_unresolved_name_has_stable_code(self) -> None:
        result = compile_source(ROOT / "examples" / "invalid_name.ax")
        self.assertIn("AX-NAME-0001", [diagnostic.code for diagnostic in result["diagnostics"]])

    def test_invalid_arithmetic_has_stable_code(self) -> None:
        result = compile_source(ROOT / "examples" / "invalid_type.ax")
        self.assertIn("AX-TYPE-0007", [diagnostic.code for diagnostic in result["diagnostics"]])

    def test_assignment_to_let_has_stable_code(self) -> None:
        result = compile_source(ROOT / "examples" / "invalid_assign_let.ax")
        self.assertIn("AX-MUT-0001", [diagnostic.code for diagnostic in result["diagnostics"]])

    def test_assignment_type_mismatch_has_stable_code(self) -> None:
        result = compile_source(ROOT / "examples" / "invalid_assign_type.ax")
        self.assertIn("AX-TYPE-0011", [diagnostic.code for diagnostic in result["diagnostics"]])

    def test_while_condition_requires_bool(self) -> None:
        result = compile_source(ROOT / "examples" / "invalid_while_condition.ax")
        self.assertIn("AX-TYPE-0012", [diagnostic.code for diagnostic in result["diagnostics"]])

    def test_block_local_does_not_escape(self) -> None:
        result = compile_source(ROOT / "examples" / "invalid_block_scope.ax")
        self.assertIn("AX-NAME-0001", [diagnostic.code for diagnostic in result["diagnostics"]])

    def test_interpreter_stops_infinite_loop(self) -> None:
        result = compile_source(ROOT / "examples" / "infinite_loop.ax")
        self.assertEqual(result["diagnostics"], [])
        assert result["program"] is not None
        with self.assertRaisesRegex(RuntimeError, "AX-RUNTIME-0001"):
            Interpreter(result["program"], step_limit=25).run_main()

    def test_control_flow_contains_loop_back_edge(self) -> None:
        result = compile_source(ROOT / "examples" / "loop.ax")
        self.assertEqual(result["diagnostics"], [])
        assert result["program"] is not None
        document = build_control_flow_document(result["program"])
        function = document["functions"][0]
        edge_kinds = {edge["kind"] for edge in function["edges"]}
        self.assertIn("true", edge_kinds)
        self.assertIn("false", edge_kinds)
        self.assertIn("loop_back", edge_kinds)
        self.assertTrue(function["all_reachable_paths_terminate"])

    def test_ast_is_deterministic(self) -> None:
        first = compile_source(ROOT / "examples" / "loop.ax")["ast"]
        second = compile_source(ROOT / "examples" / "loop.ax")["ast"]
        self.assertEqual(first, second)

    def test_script_profile_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(ROOT / "examples" / "script.ax", Path(directory))
            self.assertEqual(result["interpreter_exit_code"], 42)
            self.assertEqual(result["native_exit_code"], 42)

    def test_c_abi_fixture_is_semantically_valid(self) -> None:
        result = compile_source(ROOT / "examples" / "c_abi.ax")
        self.assertEqual(result["diagnostics"], [])

    def test_tokens_include_exact_source_hash(self) -> None:
        result = compile_source(ROOT / "examples" / "loop.ax")
        source = (ROOT / "examples" / "loop.ax").read_bytes()
        self.assertEqual(result["tokens"]["source"]["sha256"], hashlib.sha256(source).hexdigest())

    def test_i32_literal_out_of_range_has_stable_code(self) -> None:
        result = compile_source(ROOT / "examples" / "invalid_i32_literal.ax")
        self.assertIn("AX-INT-0001", [diagnostic.code for diagnostic in result["diagnostics"]])

    def test_checked_arithmetic_helpers(self) -> None:
        self.assertEqual(checked_add(20, 22), 42)
        self.assertEqual(checked_sub(20, 22), -2)
        self.assertEqual(checked_mul(-7, 6), -42)
        self.assertEqual(truncating_division(-7, 3), -2)
        self.assertEqual(truncating_remainder(-7, 3), -1)

    def test_checked_overflow_helpers_have_exact_codes(self) -> None:
        cases = [
            (lambda: checked_add(2147483647, 1), PANIC_ADD_OVERFLOW),
            (lambda: checked_sub(-2147483648, 1), PANIC_SUB_OVERFLOW),
            (lambda: checked_mul(50000, 50000), PANIC_MUL_OVERFLOW),
            (lambda: truncating_division(1, 0), PANIC_DIVIDE_BY_ZERO),
            (lambda: truncating_division(-2147483648, -1), PANIC_DIVIDE_OVERFLOW),
            (lambda: truncating_remainder(1, 0), PANIC_REMAINDER_BY_ZERO),
            (lambda: truncating_remainder(-2147483648, -1), PANIC_REMAINDER_OVERFLOW),
        ]
        for action, exit_code in cases:
            with self.subTest(exit_code=exit_code):
                with self.assertRaises(ArithmeticFault) as captured:
                    action()
                self.assertEqual(captured.exception.exit_code, exit_code)

    def test_normal_signed_division_and_remainder_match_native(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(ROOT / "examples" / "arithmetic_normal.ax", Path(directory))
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["interpreter_exit_code"], 17)
            self.assertEqual(result["native_exit_code"], 17)

    def test_arithmetic_faults_match_native_panic_codes(self) -> None:
        cases = {
            "overflow_add.ax": PANIC_ADD_OVERFLOW,
            "overflow_sub.ax": PANIC_SUB_OVERFLOW,
            "overflow_mul.ax": PANIC_MUL_OVERFLOW,
            "divide_zero.ax": PANIC_DIVIDE_BY_ZERO,
            "divide_overflow.ax": PANIC_DIVIDE_OVERFLOW,
            "remainder_zero.ax": PANIC_REMAINDER_BY_ZERO,
            "remainder_overflow.ax": PANIC_REMAINDER_OVERFLOW,
        }
        for fixture, expected in cases.items():
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as directory:
                result = prove(ROOT / "examples" / fixture, Path(directory))
                self.assertEqual(result["status"], "passed")
                self.assertEqual(result["interpreter_exit_code"], expected)
                self.assertEqual(result["native_exit_code"], expected)
                self.assertEqual(result["interpreter_outcome"]["kind"], "arithmetic_fault")
                self.assertEqual(result["interpreter_outcome"]["exit_code"], expected)

    def test_llvm_uses_checked_overflow_intrinsics_and_division_guards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prove(ROOT / "examples" / "arithmetic_normal.ax", Path(directory))
            llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
            self.assertIn("@llvm.sadd.with.overflow.i32", llvm)
            self.assertIn("@llvm.ssub.with.overflow.i32", llvm)
            self.assertIn("call void @axiom_panic_i32", llvm)
            self.assertIn("icmp eq i32", llvm)
            self.assertIn("sdiv i32", llvm)
            self.assertIn("srem i32", llvm)
            self.assertLess(llvm.index("icmp eq i32"), llvm.index("sdiv i32"))

    def test_effect_document_reports_panic_for_checked_arithmetic(self) -> None:
        result = compile_source(ROOT / "examples" / "arithmetic_normal.ax")
        self.assertEqual(result["diagnostics"], [])
        semantic = result["semantic"]
        assert semantic is not None
        functions = semantic.effect_document()["functions"]
        main = next(item for item in functions if item["name"] == "main")
        self.assertEqual(main["effects"], ["panic"])
        self.assertGreater(main["local_facts"]["checked_arithmetic_sites"], 0)


if __name__ == "__main__":
    unittest.main()
