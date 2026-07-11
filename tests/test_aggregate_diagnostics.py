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

class AggregateDiagnosticTests(unittest.TestCase):
    def test_aggregate_diagnostics_are_stable(self) -> None:
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
                with self.subTest(fixture=fixture):
                    result = compile_source(ROOT / "examples" / fixture)
                    self.assertIn(code, [diagnostic.code for diagnostic in result["diagnostics"]])
