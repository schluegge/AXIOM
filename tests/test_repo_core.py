from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from axiom_proof.arithmetic import ArithmeticFault, checked_add, truncating_division, truncating_remainder
from axiom_proof.driver import compile_source
from axiom_proof.formatter import Formatter
from axiom_proof.interpreter import Interpreter


class RepoCoreTests(unittest.TestCase):
    def compile_text(self, text: str):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "case.ax"
            path.write_text(text, encoding="utf-8")
            return compile_source(path)

    def test_checked_add_overflow(self) -> None:
        with self.assertRaises(ArithmeticFault) as caught:
            checked_add(2_147_483_647, 1)
        self.assertEqual(caught.exception.exit_code, 101)

    def test_signed_division_and_remainder(self) -> None:
        self.assertEqual(truncating_division(-7, 3), -2)
        self.assertEqual(truncating_remainder(-7, 3), -1)

    def test_parse_format_interpret_loop(self) -> None:
        compilation = self.compile_text(
            "profile system;\n"
            "fn main() -> i32 {\n"
            "    var index: i32 = 1;\n"
            "    var sum: i32 = 0;\n"
            "    while index <= 10 {\n"
            "        sum = sum + index;\n"
            "        index = index + 1;\n"
            "    }\n"
            "    return sum;\n"
            "}\n"
        )
        self.assertEqual(compilation["diagnostics"], [])
        program = compilation["program"]
        self.assertIsNotNone(program)
        assert program is not None
        self.assertEqual(Interpreter(program).run_main(), 55)
        formatted = Formatter().format(program)
        self.assertIn("while", formatted)

    def test_i32_literal_range_diagnostic(self) -> None:
        compilation = self.compile_text("fn main() -> i32 { return 2147483648; }\n")
        self.assertIn("AX-INT-0001", {item.code for item in compilation["diagnostics"]})


if __name__ == "__main__":
    unittest.main()
