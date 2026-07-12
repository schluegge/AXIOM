from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

SCHEMA_VERSION = "0.1.0"
SCHEMA_PATH = Path("review/contracts/0.1.0/report.schema.json")
_RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def semantic_sha256(report: dict[str, Any]) -> str:
    normalized = {key: value for key, value in report.items() if key != "semantic_sha256"}
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(payload.encode("utf-8")).hexdigest()


def _walk_refs(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key == "$ref" and isinstance(child, str):
                yield child_path, child
            yield from _walk_refs(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_refs(child, f"{path}[{index}]")


def _is_rfc3339_datetime(value: str) -> bool:
    if _RFC3339_DATETIME.fullmatch(value) is None:
        return False
    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_report(report: dict[str, Any], schema: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for path, reference in _walk_refs(schema):
        if not reference.startswith("#"):
            findings.append(Finding("AX-REV-CONTRACT-1001", path, f"external schema reference is forbidden: {reference}"))
    if findings:
        return sorted(findings)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        return [Finding("AX-REV-CONTRACT-1002", "schema", f"invalid Draft 2020-12 schema: {error.message}")]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(report), key=lambda item: (item.json_path, item.message)):
        findings.append(
            Finding(
                "AX-REV-CONTRACT-1003",
                error.json_path,
                f"schema violation ({error.validator}): {error.message}",
            )
        )
    if findings:
        return sorted(findings)

    if not _is_rfc3339_datetime(report["generated_at"]):
        findings.append(
            Finding(
                "AX-REV-CONTRACT-1003",
                "$.generated_at",
                "schema violation (format): generated_at must be an RFC 3339 date-time with an explicit offset",
            )
        )

    reviewer_class = report["reviewer_class"]
    status = report["status"]
    report_findings = report["findings"]

    for index, item in enumerate(report_findings):
        if reviewer_class == "advisory_ai" and item["authority"] != "advisory":
            findings.append(
                Finding(
                    "AX-REV-CONTRACT-2001",
                    f"$.findings[{index}].authority",
                    "AI-originated findings must be advisory",
                )
            )
        if item["authority"] == "blocking" and reviewer_class != "deterministic":
            findings.append(
                Finding(
                    "AX-REV-CONTRACT-2002",
                    f"$.findings[{index}].authority",
                    "only deterministic findings may be blocking",
                )
            )
        if item["authority"] == "blocking" and not item["evidence_path"].strip():
            findings.append(
                Finding(
                    "AX-REV-CONTRACT-2003",
                    f"$.findings[{index}].evidence_path",
                    "blocking finding requires non-empty evidence_path",
                )
            )

    has_blocker = any(item["authority"] == "blocking" for item in report_findings)
    has_nonpassing_check = any(item["conclusion"] != "passed" for item in report["checks"])
    if status == "passed" and (has_blocker or has_nonpassing_check or report["unavailable"]):
        findings.append(
            Finding(
                "AX-REV-CONTRACT-2004",
                "$.status",
                "passed report cannot contain blocking findings, non-passing checks, or unavailable sections",
            )
        )
    if status == "passed" and len(report["reviewed_head_sha"]) != 40:
        findings.append(
            Finding(
                "AX-REV-CONTRACT-2006",
                "$.reviewed_head_sha",
                "passed report requires an exact 40-character reviewed head SHA",
            )
        )

    expected_digest = semantic_sha256(report)
    if report["semantic_sha256"] != expected_digest:
        findings.append(
            Finding(
                "AX-REV-CONTRACT-2005",
                "$.semantic_sha256",
                f"semantic digest mismatch: expected {expected_digest}",
            )
        )
    return sorted(findings)


def load_and_validate_report(root: Path, report_path: Path) -> tuple[dict[str, Any] | None, list[Finding]]:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        schema = json.loads((root / SCHEMA_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        return None, [Finding("AX-REV-CONTRACT-0001", str(error.filename), "required JSON file is missing")]
    except json.JSONDecodeError as error:
        return None, [Finding("AX-REV-CONTRACT-0002", str(report_path), f"invalid JSON: {error.msg}")]
    if not isinstance(report, dict) or not isinstance(schema, dict):
        return None, [Finding("AX-REV-CONTRACT-0003", str(report_path), "JSON root must be an object")]
    return report, validate_report(report, schema)


def render_markdown(report: dict[str, Any]) -> str:
    status = report["status"]
    lines = [
        "## AXIOM automated review",
        "",
        f"- Status: **{status.upper()}**",
        f"- Reviewer class: `{report['reviewer_class']}`",
        f"- Repository: `{report['repository']}`",
        f"- Pull request: `#{report['pull_request_number']}`",
        f"- Base SHA: `{report['base_sha']}`",
        f"- Reviewed head SHA: `{report['reviewed_head_sha']}`",
        f"- Semantic digest: `{report['semantic_sha256']}`",
        "",
        "### Findings",
    ]
    if not report["findings"]:
        lines.append("No findings.")
    else:
        for item in sorted(report["findings"], key=lambda value: (value["authority"], value["severity"], value["code"], value["title"])):
            lines.extend(
                [
                    f"- **{item['code']}** [{item['authority']}/{item['severity']}] {item['title']}",
                    f"  - {item['explanation']}",
                    f"  - Evidence: `{item['evidence_path'] or 'none'}`",
                    f"  - Remediation: {item['remediation']}",
                ]
            )
    for heading, key in (("Known unreviewed", "known_unreviewed"), ("Unavailable", "unavailable")):
        lines.extend(["", f"### {heading}"])
        sections = report[key]
        if not sections:
            lines.append("None.")
        else:
            for item in sorted(sections, key=lambda value: value["code"]):
                lines.append(f"- **{item['code']}** {item['title']}: {item['explanation']}")
    return "\n".join(lines) + "\n"
