from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

from axiom_contract import check_project_contract, render_text

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "project.json"
SCHEMA = ROOT / "contracts" / "project.schema.json"


class ProjectContractTests(unittest.TestCase):
    def load_contract(self) -> dict[str, Any]:
        return json.loads(CONTRACT.read_text(encoding="utf-8"))

    def check_mutation(self, mutate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        value = copy.deepcopy(self.load_contract())
        mutate(value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return check_project_contract(ROOT, path, SCHEMA)

    def finding_codes(self, result: dict[str, Any]) -> set[str]:
        return {finding["code"] for finding in result["findings"]}

    def test_valid_repository_contract_passes(self) -> None:
        result = check_project_contract(ROOT, CONTRACT, SCHEMA)
        self.assertEqual(result["status"], "passed", render_text(result))
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["counts"]["current_features"], 10)
        self.assertEqual(result["counts"]["findings"], 0)
        features = {item["id"]: item for item in self.load_contract()["features"]}
        self.assertEqual(features["review.report-contract-0.1"]["status"], "implemented")
        self.assertEqual(features["review.report-contract-0.1"]["proven_targets"], [])
        self.assertEqual(features["review.deterministic-gate-0.1"]["status"], "implemented")
        self.assertEqual(features["review.deterministic-gate-0.1"]["proven_targets"], [])
        self.assertEqual(features["benchmark.trusted-conformance-0.1"]["status"], "implemented")
        self.assertEqual(features["benchmark.trusted-conformance-0.1"]["proven_targets"], [])

    def test_report_is_deterministic(self) -> None:
        first = check_project_contract(ROOT, CONTRACT, SCHEMA)
        second = check_project_contract(ROOT, CONTRACT, SCHEMA)
        self.assertEqual(first, second)
        self.assertEqual(render_text(first), render_text(second))

    def test_broken_repository_path_is_rejected(self) -> None:
        result = self.check_mutation(
            lambda value: value["features"][0]["implementation_paths"].append(
                "axiom_proof/does_not_exist.py"
            )
        )
        self.assertEqual(result["exit_code"], 4)
        self.assertIn("AX-CONTRACT-2002", self.finding_codes(result))

    def test_duplicate_diagnostic_ownership_is_rejected(self) -> None:
        result = self.check_mutation(
            lambda value: value["features"][1]["diagnostic_owners"].append("AX-TYPE-0007")
        )
        self.assertEqual(result["exit_code"], 4)
        self.assertIn("AX-CONTRACT-2014", self.finding_codes(result))

    def test_language_version_mismatch_is_rejected(self) -> None:
        result = self.check_mutation(lambda value: value["language"].update(version="0.8.0"))
        self.assertEqual(result["exit_code"], 3)
        self.assertIn("AX-CONTRACT-1003", self.finding_codes(result))

    def test_unsupported_target_claim_is_rejected(self) -> None:
        result = self.check_mutation(
            lambda value: value["features"][0]["proven_targets"].append(
                "aarch64-unknown-linux-gnu"
            )
        )
        self.assertEqual(result["exit_code"], 4)
        self.assertIn("AX-CONTRACT-2012", self.finding_codes(result))

    def test_proven_feature_without_test_mapping_is_rejected(self) -> None:
        result = self.check_mutation(lambda value: value["features"][0].update(test_paths=[]))
        self.assertEqual(result["exit_code"], 3)
        self.assertIn("AX-CONTRACT-1003", self.finding_codes(result))

    def test_deferred_feature_presented_as_current_is_rejected(self) -> None:
        def mutate(value: dict[str, Any]) -> None:
            deferred_id = value["deferred_features"][0]["id"]
            duplicate = copy.deepcopy(value["features"][0])
            duplicate["id"] = deferred_id
            duplicate["summary"] = "invalid seeded contradiction"
            value["features"].append(duplicate)

        result = self.check_mutation(mutate)
        self.assertEqual(result["exit_code"], 4)
        self.assertIn("AX-CONTRACT-2005", self.finding_codes(result))

    def test_external_schema_reference_is_rejected_without_network(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        schema["properties"]["project"] = {"$ref": "https://example.invalid/project.json"}
        with tempfile.TemporaryDirectory() as directory:
            schema_path = Path(directory) / "schema.json"
            schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = check_project_contract(ROOT, CONTRACT, schema_path)
        self.assertEqual(result["exit_code"], 3)
        self.assertIn("AX-CONTRACT-1001", self.finding_codes(result))

    def test_claim_document_mismatch_is_rejected(self) -> None:
        result = self.check_mutation(
            lambda value: value["claim_documents"][0]["feature_ids"].reverse()
        )
        self.assertEqual(result["exit_code"], 4)
        self.assertIn("AX-CONTRACT-2018", self.finding_codes(result))


if __name__ == "__main__":
    unittest.main()
