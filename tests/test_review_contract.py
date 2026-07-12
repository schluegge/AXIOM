from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from axiom_review import (
    canonical_json,
    load_and_validate_report,
    render_markdown,
    semantic_sha256,
    validate_report,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_RELATIVE_PATH = Path("review/contracts/0.1.0/report.schema.json")
SCHEMA = json.loads((ROOT / SCHEMA_RELATIVE_PATH).read_text(encoding="utf-8"))


def valid_report(reviewer_class: str = "deterministic") -> dict[str, object]:
    report: dict[str, object] = {
        "document_kind": "axiom.automated-review.report",
        "schema_version": "0.1.0",
        "report_id": "fixture-report",
        "repository": "schluegge/AXIOM",
        "pull_request_number": 33,
        "base_sha": "1" * 40,
        "reviewed_head_sha": "2" * 40,
        "generated_at": "2026-07-12T02:00:00Z",
        "reviewer_class": reviewer_class,
        "status": "passed",
        "findings": [],
        "checks": [
            {
                "check_id": "fixture.schema",
                "title": "Fixture schema validation",
                "input_sha256": "3" * 64,
                "conclusion": "passed",
                "evidence_path": "evidence/review/schema.json",
            }
        ],
        "known_unreviewed": [],
        "unavailable": [],
        "semantic_sha256": "0" * 64,
    }
    report["semantic_sha256"] = semantic_sha256(report)
    return report


class ReviewContractTests(unittest.TestCase):
    def assert_code(self, report: dict[str, object], code: str) -> None:
        self.assertIn(code, {finding.code for finding in validate_report(report, SCHEMA)})

    def test_valid_deterministic_and_advisory_reports_pass(self) -> None:
        self.assertEqual(validate_report(valid_report("deterministic"), SCHEMA), [])
        self.assertEqual(validate_report(valid_report("advisory_ai"), SCHEMA), [])

    def test_canonical_json_and_markdown_are_deterministic(self) -> None:
        report = valid_report()
        self.assertEqual(canonical_json(report), canonical_json(json.loads(canonical_json(report))))
        self.assertEqual(render_markdown(report), render_markdown(copy.deepcopy(report)))
        self.assertIn("Status: **PASSED**", render_markdown(report))

    def test_markdown_rendering_neutralizes_untrusted_structure(self) -> None:
        report = valid_report()
        report["status"] = "failed"
        report["findings"] = [
            {
                "code": "AX-REV-FIXTURE-MARKDOWN",
                "title": "Injected\n## Fake status",
                "explanation": "line one\n- Status: **PASSED**",
                "severity": "medium",
                "authority": "advisory",
                "evidence_path": "evidence/review/model.md`\n## Forged section",
                "affected_location": None,
                "remediation": "Do not trust [links](https://example.invalid).",
            }
        ]
        report["semantic_sha256"] = semantic_sha256(report)
        rendered = render_markdown(report)
        self.assertNotIn("\n## Fake status", rendered)
        self.assertNotIn("\n## Forged section", rendered)
        self.assertNotIn("\n- Status: **PASSED**", rendered)
        self.assertNotIn("](https://example.invalid)", rendered)

    def test_external_dynamic_schema_reference_fails(self) -> None:
        schema = copy.deepcopy(SCHEMA)
        schema["properties"]["repository"] = {"$dynamicRef": "https://example.invalid/review.schema.json"}
        findings = validate_report(valid_report(), schema)
        self.assertIn("AX-REV-CONTRACT-1001", {finding.code for finding in findings})

    def test_unresolved_local_schema_reference_returns_stable_finding(self) -> None:
        schema = copy.deepcopy(SCHEMA)
        schema["properties"]["repository"] = {"$ref": "#/definitions/missing"}
        findings = validate_report(valid_report(), schema)
        self.assertEqual([finding.code for finding in findings], ["AX-REV-CONTRACT-1002"])

    def test_invalid_schema_json_is_attributed_to_schema_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="axiom-review-contract-") as directory:
            root = Path(directory)
            schema_path = root / SCHEMA_RELATIVE_PATH
            schema_path.parent.mkdir(parents=True)
            schema_path.write_text("{invalid", encoding="utf-8")
            report_path = root / "report.json"
            report_path.write_text(canonical_json(valid_report()), encoding="utf-8")
            report, findings = load_and_validate_report(root, report_path)
        self.assertIsNone(report)
        self.assertEqual([finding.code for finding in findings], ["AX-REV-CONTRACT-0002"])
        self.assertEqual(findings[0].path, str(schema_path))

    def test_advisory_blocking_escalation_fails(self) -> None:
        report = valid_report("advisory_ai")
        report["status"] = "failed"
        report["findings"] = [
            {
                "code": "AX-REV-FIXTURE-BLOCK",
                "title": "Attempted escalation",
                "explanation": "Model output requested blocking authority.",
                "severity": "critical",
                "authority": "blocking",
                "evidence_path": "evidence/review/model.json",
                "affected_location": None,
                "remediation": "Keep AI output advisory.",
            }
        ]
        report["semantic_sha256"] = semantic_sha256(report)
        self.assert_code(report, "AX-REV-CONTRACT-2001")

    def test_missing_sha_fails(self) -> None:
        report = valid_report()
        report["reviewed_head_sha"] = ""
        report["semantic_sha256"] = semantic_sha256(report)
        self.assert_code(report, "AX-REV-CONTRACT-1003")

    def test_unknown_field_fails(self) -> None:
        report = valid_report()
        report["unexpected"] = True
        report["semantic_sha256"] = semantic_sha256(report)
        self.assert_code(report, "AX-REV-CONTRACT-1003")

    def test_invalid_severity_fails(self) -> None:
        report = valid_report()
        report["status"] = "failed"
        report["findings"] = [
            {
                "code": "AX-REV-FIXTURE-SEVERITY",
                "title": "Invalid severity",
                "explanation": "Fixture.",
                "severity": "urgent",
                "authority": "advisory",
                "evidence_path": "",
                "affected_location": None,
                "remediation": "Use a contract severity.",
            }
        ]
        report["semantic_sha256"] = semantic_sha256(report)
        self.assert_code(report, "AX-REV-CONTRACT-1003")

    def test_invalid_generated_at_fails_without_optional_format_dependencies(self) -> None:
        report = valid_report()
        report["generated_at"] = "not-a-time"
        report["semantic_sha256"] = semantic_sha256(report)
        self.assert_code(report, "AX-REV-CONTRACT-1003")

    def test_empty_blocking_evidence_fails(self) -> None:
        report = valid_report()
        report["status"] = "failed"
        report["findings"] = [
            {
                "code": "AX-REV-FIXTURE-EVIDENCE",
                "title": "Missing evidence",
                "explanation": "Fixture.",
                "severity": "high",
                "authority": "blocking",
                "evidence_path": "",
                "affected_location": None,
                "remediation": "Attach evidence.",
            }
        ]
        report["semantic_sha256"] = semantic_sha256(report)
        self.assert_code(report, "AX-REV-CONTRACT-2003")

    def test_false_pass_fails_and_cannot_render_as_clean(self) -> None:
        report = valid_report()
        report["unavailable"] = [
            {"code": "provider", "title": "Provider unavailable", "explanation": "No result was produced."}
        ]
        report["semantic_sha256"] = semantic_sha256(report)
        self.assert_code(report, "AX-REV-CONTRACT-2004")
        with self.assertRaisesRegex(ValueError, "AX-REV-CONTRACT-2004"):
            render_markdown(report)

    def test_passed_report_requires_at_least_one_check(self) -> None:
        report = valid_report()
        report["checks"] = []
        report["semantic_sha256"] = semantic_sha256(report)
        self.assert_code(report, "AX-REV-CONTRACT-2004")

    def test_passed_report_rejects_every_nonpassing_check_conclusion(self) -> None:
        for conclusion in ("failed", "missing", "cancelled", "skipped", "unavailable", "stale"):
            with self.subTest(conclusion=conclusion):
                report = valid_report()
                report["checks"][0]["conclusion"] = conclusion
                report["semantic_sha256"] = semantic_sha256(report)
                self.assert_code(report, "AX-REV-CONTRACT-2004")

    def test_semantic_digest_detects_meaning_change(self) -> None:
        report = valid_report()
        report["repository"] = "foreign/repository"
        self.assert_code(report, "AX-REV-CONTRACT-2005")


if __name__ == "__main__":
    unittest.main()
