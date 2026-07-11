from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

SCHEMA_VERSION = "0.1.0"
CONTRACT_PATH = Path("benchmarks/contracts/0.1.0/contract.json")

EXIT_OK = 0
EXIT_INPUT = 10
EXIT_SCHEMA = 11
EXIT_CONSISTENCY = 12


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def semantic_sha256(value: Any, excluded_keys: frozenset[str] = frozenset()) -> str:
    def strip(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                key: strip(child)
                for key, child in sorted(item.items())
                if key not in excluded_keys
            }
        if isinstance(item, list):
            return [strip(child) for child in item]
        return item

    payload = json.dumps(strip(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(payload.encode("utf-8")).hexdigest()


def _load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, Finding | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, Finding("AX-BENCH-CONTRACT-0001", label, f"missing JSON file: {path}")
    except OSError as error:
        return None, Finding("AX-BENCH-CONTRACT-0002", label, f"cannot read {path}: {error}")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        return None, Finding(
            "AX-BENCH-CONTRACT-0003",
            label,
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}",
        )
    if not isinstance(value, dict):
        return None, Finding("AX-BENCH-CONTRACT-0004", label, "JSON root must be an object")
    return value, None


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


def _safe_path(root: Path, relative: str) -> tuple[Path | None, str | None]:
    if "\\" in relative:
        return None, "backslashes are forbidden"
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or "." in pure.parts or ".." in pure.parts:
        return None, "path must be normalized and repository-relative"
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None, "path escapes repository root"
    return candidate, None


def _schema_findings(schema: dict[str, Any], schema_label: str) -> list[Finding]:
    findings: list[Finding] = []
    for path, reference in _walk_refs(schema):
        if not reference.startswith("#"):
            findings.append(
                Finding(
                    "AX-BENCH-CONTRACT-1001",
                    f"{schema_label}:{path}",
                    f"external schema reference is forbidden: {reference}",
                )
            )
    if findings:
        return findings
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        findings.append(
            Finding(
                "AX-BENCH-CONTRACT-1002",
                schema_label,
                f"invalid Draft 2020-12 schema: {error.message}",
            )
        )
    return findings


def validate_document(
    document: dict[str, Any],
    schema: dict[str, Any],
    *,
    label: str = "document",
) -> list[Finding]:
    findings = _schema_findings(schema, f"{label}.schema")
    if findings:
        return findings
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(document),
        key=lambda item: (item.json_path, tuple(str(part) for part in item.schema_path), item.message),
    )
    for error in errors:
        findings.append(
            Finding(
                "AX-BENCH-CONTRACT-1003",
                f"{label}:{error.json_path}",
                f"schema violation ({error.validator}): {error.message}",
            )
        )
    if findings:
        return findings
    findings.extend(_semantic_document_findings(document, label))
    return sorted(findings)


def _semantic_document_findings(document: dict[str, Any], label: str) -> list[Finding]:
    findings: list[Finding] = []
    kind = document.get("document_kind")

    if kind == "axiom.bench.suite":
        if document.get("status") == "frozen":
            for field in ("frozen_at", "repository_commit", "semantic_sha256"):
                if document.get(field) is None:
                    findings.append(
                        Finding(
                            "AX-BENCH-CONTRACT-2001",
                            f"{label}:$.{field}",
                            "frozen suite requires a non-null value",
                        )
                    )
        if document.get("semantic_sha256") is not None:
            expected = semantic_sha256(document, frozenset({"semantic_sha256"}))
            if document["semantic_sha256"] != expected:
                findings.append(
                    Finding(
                        "AX-BENCH-CONTRACT-2002",
                        f"{label}:$.semantic_sha256",
                        f"semantic hash mismatch: expected {expected}",
                    )
                )

    elif kind == "axiom.bench.task":
        variants = document.get("variants", {})
        for language, variant in variants.items():
            if variant.get("language") != language:
                findings.append(
                    Finding(
                        "AX-BENCH-CONTRACT-2003",
                        f"{label}:$.variants.{language}.language",
                        "variant key and language field disagree",
                    )
                )
            declared = set(variant.get("declared_dependencies", []))
            if any(item.startswith("http://") or item.startswith("https://") for item in declared):
                findings.append(
                    Finding(
                        "AX-BENCH-CONTRACT-2004",
                        f"{label}:$.variants.{language}.declared_dependencies",
                        "remote URL dependencies are forbidden",
                    )
                )
        if document.get("classification") == "controlled_holdout" and document.get("provenance", {}).get("first_public_at") is not None:
            findings.append(
                Finding(
                    "AX-BENCH-CONTRACT-2005",
                    f"{label}:$.provenance.first_public_at",
                    "controlled holdout cannot already be public",
                )
            )

    elif kind == "axiom.bench.language-pack":
        content_path = document.get("content_path")
        hashes = document.get("source_sha256", {})
        if isinstance(content_path, str) and content_path not in hashes:
            findings.append(
                Finding(
                    "AX-BENCH-CONTRACT-2006",
                    f"{label}:$.source_sha256",
                    "content_path must have a recorded source hash",
                )
            )
        leakage = document.get("leakage_review", {})
        if leakage.get("status") == "passed" and leakage.get("task_specific_algorithms_found"):
            findings.append(
                Finding(
                    "AX-BENCH-CONTRACT-2007",
                    f"{label}:$.leakage_review",
                    "leakage review cannot pass when task-specific algorithms were found",
                )
            )

    elif kind == "axiom.bench.attempt":
        outcomes = document.get("outcomes", {})
        if outcomes.get("full_success"):
            required = [
                "extraction_success",
                "compile_success",
                "public_test_success",
                "acceptance_test_success",
                "security_success",
            ]
            if any(outcomes.get(field) is not True for field in required):
                findings.append(
                    Finding(
                        "AX-BENCH-CONTRACT-2008",
                        f"{label}:$.outcomes",
                        "full success requires every acceptance outcome to be true",
                    )
                )
            if document.get("failure_reason") is not None or not document.get("evidence_complete"):
                findings.append(
                    Finding(
                        "AX-BENCH-CONTRACT-2009",
                        label,
                        "successful attempt requires null failure reason and complete evidence",
                    )
                )
        elif document.get("failure_reason") is None:
            findings.append(
                Finding(
                    "AX-BENCH-CONTRACT-2010",
                    f"{label}:$.failure_reason",
                    "failed attempt requires a failure reason",
                )
            )

    elif kind == "axiom.bench.run":
        trust = document.get("trust_class")
        sandbox = document.get("sandbox", {})
        if trust == "untrusted_model_output":
            if not sandbox.get("isolated") or sandbox.get("backend") in {
                "local_reliability_only",
                "replay_none",
            }:
                findings.append(
                    Finding(
                        "AX-BENCH-SANDBOX-REQUIRED",
                        f"{label}:$.sandbox",
                        "untrusted model output requires an isolated non-local sandbox backend",
                    )
                )
        if trust in {"trusted_reference", "trusted_seeded_wrong"} and document.get("model") is not None:
            findings.append(
                Finding(
                    "AX-BENCH-CONTRACT-2011",
                    f"{label}:$.model",
                    "trusted conformance adapters do not use a model",
                )
            )

    return findings


def check_benchmark_contract(root: Path) -> dict[str, Any]:
    root = root.resolve()
    findings: list[Finding] = []
    contract_path = root / CONTRACT_PATH
    contract, error = _load_json(contract_path, CONTRACT_PATH.as_posix())
    if error is not None:
        return _result(findings=[error], exit_code=EXIT_INPUT, schemas=0)
    assert contract is not None

    contract_schema_relative = contract.get("$schema")
    if not isinstance(contract_schema_relative, str):
        return _result(
            findings=[Finding("AX-BENCH-CONTRACT-0005", "contract.$schema", "missing schema path")],
            exit_code=EXIT_INPUT,
            schemas=0,
        )
    contract_schema = contract_path.parent / contract_schema_relative
    contract_schema, path_error = _safe_path(root, contract_schema.resolve().relative_to(root).as_posix())
    if path_error is not None or contract_schema is None:
        return _result(
            findings=[Finding("AX-BENCH-CONTRACT-0006", "contract.$schema", path_error or "invalid path")],
            exit_code=EXIT_INPUT,
            schemas=0,
        )
    schema_value, schema_error = _load_json(contract_schema, "contract.schema")
    if schema_error is not None:
        return _result(findings=[schema_error], exit_code=EXIT_INPUT, schemas=0)
    assert schema_value is not None
    findings.extend(validate_document(contract, schema_value, label="contract"))
    if findings:
        return _result(findings=findings, exit_code=EXIT_SCHEMA, schemas=1)

    schema_paths = contract["schema_paths"]
    schema_ids: set[str] = set()
    loaded_schemas: dict[str, dict[str, Any]] = {}
    for kind, relative in sorted(schema_paths.items()):
        candidate, path_error = _safe_path(root, relative)
        if path_error is not None:
            findings.append(Finding("AX-BENCH-CONTRACT-3001", f"$.schema_paths.{kind}", path_error))
            continue
        if candidate is None or not candidate.is_file():
            findings.append(
                Finding("AX-BENCH-CONTRACT-3002", f"$.schema_paths.{kind}", f"missing schema: {relative}")
            )
            continue
        value, load_error = _load_json(candidate, relative)
        if load_error is not None:
            findings.append(load_error)
            continue
        assert value is not None
        loaded_schemas[kind] = value
        findings.extend(_schema_findings(value, relative))
        schema_id = value.get("$id")
        if not isinstance(schema_id, str):
            findings.append(Finding("AX-BENCH-CONTRACT-3003", relative, "schema requires $id"))
        elif schema_id in schema_ids:
            findings.append(Finding("AX-BENCH-CONTRACT-3004", relative, f"duplicate schema $id: {schema_id}"))
        else:
            schema_ids.add(schema_id)
        if value.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            findings.append(Finding("AX-BENCH-CONTRACT-3005", relative, "schema draft must be 2020-12"))
        if value.get("type") != "object" or value.get("additionalProperties") is not False:
            findings.append(
                Finding(
                    "AX-BENCH-CONTRACT-3006",
                    relative,
                    "top-level schema must be a strict object",
                )
            )

    for field in ("specification_path", "preregistration_path", "source_evidence_path"):
        relative = contract[field]
        candidate, path_error = _safe_path(root, relative)
        if path_error is not None or candidate is None or not candidate.is_file():
            findings.append(
                Finding(
                    "AX-BENCH-CONTRACT-3007",
                    f"$.{field}",
                    path_error or f"missing referenced document: {relative}",
                )
            )

    roadmap_path = root / "roadmap" / "v1.json"
    roadmap, roadmap_error = _load_json(roadmap_path, "roadmap/v1.json")
    if roadmap_error is not None:
        findings.append(roadmap_error)
    elif roadmap is not None and roadmap.get("active_milestone") != contract.get("active_milestone"):
        findings.append(
            Finding(
                "AX-BENCH-CONTRACT-3008",
                "$.active_milestone",
                f"benchmark contract and roadmap disagree: {contract.get('active_milestone')} != {roadmap.get('active_milestone')}",
            )
        )

    exit_code = EXIT_OK if not findings else EXIT_CONSISTENCY
    return _result(findings=sorted(findings), exit_code=exit_code, schemas=len(loaded_schemas))


def _result(*, findings: Iterable[Finding], exit_code: int, schemas: int) -> dict[str, Any]:
    ordered = sorted(findings)
    return {
        "document_kind": "axiom.bench.contract-check",
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if exit_code == EXIT_OK else "failed",
        "exit_code": exit_code,
        "schemas_checked": schemas,
        "findings": [item.as_dict() for item in ordered],
        "finding_count": len(ordered),
    }
