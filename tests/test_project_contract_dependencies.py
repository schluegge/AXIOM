from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import axiom_contract.api as contract_api
from axiom_contract import check_project_contract

ROOT = Path(__file__).resolve().parents[1]


class ProjectContractDependencyTests(unittest.TestCase):
    def expected_pins(self) -> dict[str, str]:
        expected: dict[str, str] = {}
        for raw_line in (ROOT / "requirements-proof.txt").read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            name, version = line.split("==", 1)
            expected[name] = version
        return dict(sorted(expected.items()))

    def test_report_matches_every_exact_requirement_pin(self) -> None:
        expected = self.expected_pins()
        result = check_project_contract(ROOT)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["dependency_pins"], expected)
        self.assertEqual(result["dependencies"], expected)

    def test_installed_version_drift_is_rejected(self) -> None:
        expected = self.expected_pins()
        installed = dict(expected)
        installed["jsonschema"] = "0.0.0-seeded"
        with patch.object(contract_api, "_installed_dependency_versions", return_value=installed):
            result = contract_api.check_project_contract(ROOT)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("AX-CONTRACT-0007", {item["code"] for item in result["findings"]})

    def test_missing_dependency_file_is_reported_without_traceback(self) -> None:
        with patch.object(contract_api, "_pinned_dependencies", side_effect=FileNotFoundError()):
            result = contract_api.check_project_contract(ROOT)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("AX-CONTRACT-0008", {item["code"] for item in result["findings"]})

    def test_invalid_dependency_file_is_reported_without_traceback(self) -> None:
        with patch.object(
            contract_api,
            "_pinned_dependencies",
            side_effect=ValueError("seeded unpinned dependency"),
        ):
            result = contract_api.check_project_contract(ROOT)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("AX-CONTRACT-0009", {item["code"] for item in result["findings"]})


if __name__ == "__main__":
    unittest.main()
