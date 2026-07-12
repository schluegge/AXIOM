from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .contract import Finding, InvalidReviewReport, semantic_sha256
from .freshness import SourceResult, validate_freshness

FRESHNESS_SCHEMA_VERSION = "0.2.0"
FRESHNESS_SCHEMA_PATH = Path("review/contracts/0.2.0/freshness.schema.json")
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_MARKDOWN_SPECIAL = re.compile(r"([\`*_{}\[\]()#+!|>])")


def _markdown_text(value: Any) -> str:
    flattened = " ".join(str(value).split())
    return _MARKDOWN_SPECIAL.sub(r"\\\1", flattened)


def _source_dict(source: SourceResult) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "conclusion": source.conclusion,
        "reviewed_head_sha": source.reviewed_head_sha,
        "run_id": source.run_id,
        "run_attempt": source.run_attempt,
        "artifact_name": source.artifact_name,
        "artifact_digest": source.artifact_digest,
    }


def build_freshness_envelope(
    *,
    repository: str,
    pull_request_number: int,
    base_sha: str,
    current_head_sha: str,
    publisher_run_id: int,
    publisher_run_attempt: int,
    sources: Iterable[SourceResult],
) -> dict[str, Any]:
    """Build deterministic JSON data for exact-head review publication."""

    envelope: dict[str, Any] = {
        "document_kind": "axiom.automated-review.freshness",
        "schema_version": FRESHNESS_SCHEMA_VERSION,
        "repository": repository,
        "pull_request_number": pull_request_number,
        "base_sha": base_sha,
        "current_head_sha": current_head_sha,
        "publisher_run_id": publisher_run_id,
        "publisher_run_attempt": publisher_run_attempt,
        "sources": sorted(
            (_source_dict(source) for source in sources),
            key=lambda item: (item["source_id"], item["run_id"], item["run_attempt"]),
        ),
        "semantic_sha256": "0" * 64,
    }
    envelope["semantic_sha256"] = semantic_sha256(envelope)
    return envelope


def _schema() -> dict[str, Any]:
    value = json.loads((_PACKAGE_ROOT / FRESHNESS_SCHEMA_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("freshness schema root must be an object")
    return value


def validate_freshness_envelope(envelope: dict[str, Any]) -> list[Finding]:
    """Validate envelope structure, semantic digest, and exact-head freshness offline."""

    try:
        schema = _schema()
        Draft202012Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, ValueError, SchemaError) as error:
        return [Finding("AX-REV-FRESH-CONTRACT-1001", "schema", f"freshness schema unavailable: {error}")]

    errors = sorted(
        Draft202012Validator(schema).iter_errors(envelope),
        key=lambda item: (item.json_path, item.message),
    )
    findings = [
        Finding(
            "AX-REV-FRESH-CONTRACT-1002",
            error.json_path,
            f"schema violation ({error.validator}): {error.message}",
        )
        for error in errors
    ]
    if findings:
        return sorted(findings)

    expected_digest = semantic_sha256(envelope)
    if envelope["semantic_sha256"] != expected_digest:
        findings.append(
            Finding(
                "AX-REV-FRESH-CONTRACT-2001",
                "$.semantic_sha256",
                f"semantic digest mismatch: expected {expected_digest}",
            )
        )

    sources = [
        SourceResult(
            source_id=item["source_id"],
            conclusion=item["conclusion"],
            reviewed_head_sha=item["reviewed_head_sha"],
            run_id=item["run_id"],
            run_attempt=item["run_attempt"],
            artifact_name=item["artifact_name"],
            artifact_digest=item["artifact_digest"],
        )
        for item in envelope["sources"]
    ]
    for item in validate_freshness(envelope["current_head_sha"], sources):
        findings.append(Finding(item["code"], "$.sources", item["explanation"]))
    return sorted(findings)


def render_freshness_markdown(envelope: dict[str, Any]) -> str:
    """Render exact-head execution identity only after full offline validation."""

    findings = validate_freshness_envelope(envelope)
    if findings:
        raise InvalidReviewReport(findings)

    lines = [
        "### Exact-head Evidence",
        "",
        f"- Repository: `{_markdown_text(envelope['repository'])}`",
        f"- Pull request: `#{envelope['pull_request_number']}`",
        f"- Base SHA: `{_markdown_text(envelope['base_sha'])}`",
        f"- Current head SHA: `{_markdown_text(envelope['current_head_sha'])}`",
        f"- Publisher execution: `{envelope['publisher_run_id']}/{envelope['publisher_run_attempt']}`",
        f"- Semantic digest: `{_markdown_text(envelope['semantic_sha256'])}`",
        "",
        "#### Bound sources",
    ]
    for source in envelope["sources"]:
        lines.append(
            "- "
            f"**{_markdown_text(source['source_id'])}**: "
            f"{_markdown_text(source['conclusion'])}; "
            f"head `{_markdown_text(source['reviewed_head_sha'])}`; "
            f"execution `{source['run_id']}/{source['run_attempt']}`; "
            f"artifact `{_markdown_text(source['artifact_name'])}`; "
            f"digest `{_markdown_text(source['artifact_digest'])}`"
        )
    return "\n".join(lines) + "\n"
