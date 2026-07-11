from __future__ import annotations

import unittest
from pathlib import Path

from axiom_contract import check_project_contract

ROOT = Path(__file__).resolve().parents[1]


class ProjectContractDependencyTests(unittest.TestCase):
    def test_report_matches_every_exact_requirement_pin(self) -> None:
        expected: dict[str, str] = {}
        for raw_line in (ROOT / "requirements-proof.txt").read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            name, version = line.split("==", 1)
            expected[name] = version

        result = check_project_contract(ROOT)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["dependencies"], dict(sorted(expected.items())))


if __name__ == "__main__":
    unittest.main()
