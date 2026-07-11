from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from axiom_proof.arithmetic import PANIC_INDEX_OUT_OF_BOUNDS
from axiom_proof.cli import main as cli_main
from axiom_proof.driver import compile_source, prove
from axiom_proof.llvm_backend import LLVMBackend

ROOT = Path(__file__).resolve().parents[1]

class AggregateExecutionTests(unittest.TestCase):
    def test_structs_arrays_and_dynamic_index_prove_native_differential(self) -> None:
            with tempfile.TemporaryDirectory() as directory:
                result = prove(ROOT / "examples" / "aggregates.ax", Path(directory))
                self.assertEqual(result["status"], "passed")
                self.assertEqual(result["interpreter_exit_code"], 48)
                self.assertEqual(result["native_exit_code"], 48)
                llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
                self.assertIn("%struct.Pair = type { i32, i32 }", llvm)
                self.assertIn("%struct.Packet = type { i1, %struct.Pair, [3 x i32] }", llvm)
                self.assertIn("insertvalue", llvm)
                self.assertIn("extractvalue", llvm)
                self.assertIn("getelementptr [3 x i32]", llvm)

    def test_aggregate_return_assignment_and_nested_arrays(self) -> None:
            cases = {
                "aggregate_return.ax": 42,
                "aggregate_assignment.ax": 42,
                "nested_arrays.ax": 42,
            }
            for fixture, expected in cases.items():
                with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as directory:
                    result = prove(ROOT / "examples" / fixture, Path(directory))
                    self.assertEqual(result["interpreter_exit_code"], expected)
                    self.assertEqual(result["native_exit_code"], expected)

    def test_dynamic_array_bounds_fault_matches_native(self) -> None:
            for fixture in ["array_oob_runtime.ax", "negative_index_runtime.ax"]:
                with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as directory:
                    result = prove(ROOT / "examples" / fixture, Path(directory))
                    self.assertEqual(result["interpreter_exit_code"], PANIC_INDEX_OUT_OF_BOUNDS)
                    self.assertEqual(result["native_exit_code"], PANIC_INDEX_OUT_OF_BOUNDS)
                    self.assertEqual(result["interpreter_outcome"]["kind"], "bounds_fault")
                    self.assertEqual(result["native_panic_name"], "array_index_out_of_bounds")
                    llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
                    self.assertLess(llvm.index("icmp slt i32"), llvm.index("getelementptr"))
                    self.assertLess(llvm.index("icmp sge i32"), llvm.index("getelementptr"))

    def test_dynamic_index_effect_is_visible(self) -> None:
            result = compile_source(ROOT / "examples" / "aggregates.ax")
            self.assertEqual(result["diagnostics"], [])
            semantic = result["semantic"]
            assert semantic is not None
            main = next(item for item in semantic.effect_document()["functions"] if item["name"] == "main")
            self.assertEqual(main["effects"], ["panic"])
            self.assertEqual(main["local_facts"]["bounds_check_sites"], 1)
