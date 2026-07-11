from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError as error:  # pragma: no cover - exercised by CLI dependency failure
    Draft202012Validator = None  # type: ignore[assignment]
    SchemaError = Exception  # type: ignore[assignment,misc]
    JSONSCHEMA_IMPORT_ERROR: Exception | None = error
else:
    JSONSCHEMA_IMPORT_ERROR = None

DIAGNOSTIC_RE = re.compile(r"AX-[A-Z]+-[0-9]{4}")
FEATURE_LINE_RE = re.compile(r"^- `([^`]+)`(?:\s+—.*)?$")
VERSION_RE = re.compile(r"(?<![0-9])([0-9]+)\.([0-9]+)\.([0-9]+)(?![0-9])")

EXIT_OK = 0
EXIT_INPUT = 2
EXIT_SCHEMA = 3
EXIT_CONSISTENCY = 4


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _dependency_versions() -> dict[str, str]:
    names = ["jsonschema", "attrs", "jsonschema-specifications", "referencing", "rpds-py"]
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = package_version(name)
        except PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def _load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, Finding | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, Finding("AX-CONTRACT-0001", label, f"missing JSON file: {path}")
    except OSError as error:
        return None, Finding("AX-CONTRACT-0002", label, f"could not read {path}: {error}")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        return None, Finding(
            "AX-CONTRACT-0003",
            label,
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}",
        )
    if not isinstance(value, dict):
        return None, Finding("AX-CONTRACT-0004", label, "JSON root must be an object")
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


def _schema_findings(schema: dict[str, Any], contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for path, reference in _walk_refs(schema):
        if not reference.startswith("#"):
            findings.append(
                Finding(
                    "AX-CONTRACT-1001",
                    path,
                    f"external schema reference is forbidden in offline mode: {reference}",
                )
            )
    if findings:
        return findings
    assert Draft202012Validator is not None
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        findings.append(
            Finding(
                "AX-CONTRACT-1002",
                getattr(error, "json_path", "$.schema"),
                f"invalid Draft 2020-12 schema: {error.message}",
            )
        )
        return findings
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(contract),
        key=lambda item: (item.json_path, tuple(str(part) for part in item.schema_path), item.message),
    )
    for error in errors:
        findings.append(
            Finding(
                "AX-CONTRACT-1003",
                error.json_path,
                f"schema violation ({error.validator}): {error.message}",
            )
        )
    return findings


def _safe_repository_path(root: Path, relative: str) -> tuple[Path | None, str | None]:
    if "\\" in relative:
        return None, "backslashes are forbidden; repository paths use POSIX separators"
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts or "." in pure.parts:
        return None, "path must be a normalized relative repository path without '.' or '..'"
    candidate = root.joinpath(*pure.parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None, "path escapes the repository root"
    return candidate, None


def _collect_repository_paths(contract: dict[str, Any]) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    project = contract["project"]
    paths.append(("$.project.roadmap_contract", project["roadmap_contract"]))
    for index, authority in enumerate(contract["authorities"]):
        paths.append((f"$.authorities[{index}].path", authority["path"]))
    for index, target in enumerate(contract["proven_targets"]):
        for evidence_index, path in enumerate(target["evidence_paths"]):
            paths.append((f"$.proven_targets[{index}].evidence_paths[{evidence_index}]", path))
    for index, feature in enumerate(contract["features"]):
        paths.append((f"$.features[{index}].normative_spec", feature["normative_spec"]))
        for field in ("implementation_paths", "test_paths"):
            for path_index, path in enumerate(feature[field]):
                paths.append((f"$.features[{index}].{field}[{path_index}]", path))
    for index, claim in enumerate(contract["claim_documents"]):
        paths.append((f"$.claim_documents[{index}].path", claim["path"]))
    return paths


def _parse_version(text: str) -> tuple[int, int, int] | None:
    match = VERSION_RE.search(text)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _patterns_overlap(left: str, right: str) -> bool:
    left_wild = left.endswith("*")
    right_wild = right.endswith("*")
    left_prefix = left[:-1] if left_wild else left
    right_prefix = right[:-1] if right_wild else right
    if left_wild and right_wild:
        return left_prefix.startswith(right_prefix) or right_prefix.startswith(left_prefix)
    if left_wild:
        return right.startswith(left_prefix)
    if right_wild:
        return left.startswith(right_prefix)
    return left == right


def _matches_owner(code: str, pattern: str) -> bool:
    return code.startswith(pattern[:-1]) if pattern.endswith("*") else code == pattern


def _extract_claim_ids(text: str, start: str, end: str) -> tuple[list[str] | None, str | None]:
    start_count = text.count(start)
    end_count = text.count(end)
    if start_count != 1 or end_count != 1:
        return None, f"expected exactly one start and end marker; found {start_count}/{end_count}"
    start_index = text.index(start) + len(start)
    end_index = text.index(end)
    if end_index <= start_index:
        return None, "end marker appears before start marker"
    ids: list[str] = []
    for line in text[start_index:end_index].splitlines():
        match = FEATURE_LINE_RE.match(line.strip())
        if match is not None:
            ids.append(match.group(1))
    return ids, None


def _consistency_findings(root: Path, contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    for json_path, relative in _collect_repository_paths(contract):
        candidate, error = _safe_repository_path(root, relative)
        if error is not None:
            findings.append(Finding("AX-CONTRACT-2001", json_path, error))
        elif candidate is None or not candidate.is_file():
            findings.append(Finding("AX-CONTRACT-2002", json_path, f"referenced file does not exist: {relative}"))

    features = contract["features"]
    feature_ids = [feature["id"] for feature in features]
    duplicate_feature_ids = sorted({item for item in feature_ids if feature_ids.count(item) > 1})
    for feature_id in duplicate_feature_ids:
        findings.append(Finding("AX-CONTRACT-2003", "$.features", f"duplicate feature id: {feature_id}"))

    deferred_ids = [feature["id"] for feature in contract["deferred_features"]]
    duplicate_deferred_ids = sorted({item for item in deferred_ids if deferred_ids.count(item) > 1})
    for feature_id in duplicate_deferred_ids:
        findings.append(Finding("AX-CONTRACT-2004", "$.deferred_features", f"duplicate deferred feature id: {feature_id}"))
    for feature_id in sorted(set(feature_ids) & set(deferred_ids)):
        findings.append(Finding("AX-CONTRACT-2005", "$.deferred_features", f"feature is both current and deferred: {feature_id}"))

    language_version_text = contract["language"]["version"]
    language_version = _parse_version(language_version_text)
    if language_version is None:
        findings.append(Finding("AX-CONTRACT-2006", "$.language.version", "invalid semantic version"))
    else:
        for index, feature in enumerate(features):
            introduced = _parse_version(feature["introduced_version"])
            if introduced is None or introduced > language_version:
                findings.append(
                    Finding(
                        "AX-CONTRACT-2007",
                        f"$.features[{index}].introduced_version",
                        f"introduced version {feature['introduced_version']} exceeds language version {language_version_text}",
                    )
                )

    for document in ("README.md", "PROOF_STATUS.md"):
        path = root / document
        if path.is_file():
            first_lines = "\n".join(path.read_text(encoding="utf-8").splitlines()[:5])
            if f"v{language_version_text}" not in first_lines:
                findings.append(
                    Finding(
                        "AX-CONTRACT-2008",
                        document,
                        f"document header does not identify language version v{language_version_text}",
                    )
                )

    declared_targets = {target["triple"] for target in contract["proven_targets"]}
    if len(declared_targets) != len(contract["proven_targets"]):
        findings.append(Finding("AX-CONTRACT-2009", "$.proven_targets", "target triples must be unique"))
    for index, feature in enumerate(features):
        if feature["status"] == "proven":
            if not feature["test_paths"] or not feature["proof_ids"] or not feature["normative_spec"]:
                findings.append(
                    Finding(
                        "AX-CONTRACT-2010",
                        f"$.features[{index}]",
                        "proven feature requires a normative specification, executable tests, and proof ids",
                    )
                )
            if not feature["proven_targets"]:
                findings.append(
                    Finding("AX-CONTRACT-2011", f"$.features[{index}].proven_targets", "proven feature has no target")
                )
        for target in feature["proven_targets"]:
            if target not in declared_targets:
                findings.append(
                    Finding(
                        "AX-CONTRACT-2012",
                        f"$.features[{index}].proven_targets",
                        f"feature claims undeclared target: {target}",
                    )
                )

    proof_status = (root / "PROOF_STATUS.md").read_text(encoding="utf-8") if (root / "PROOF_STATUS.md").is_file() else ""
    for target in sorted(declared_targets):
        if target not in proof_status:
            findings.append(
                Finding(
                    "AX-CONTRACT-2013",
                    "PROOF_STATUS.md",
                    f"proven target is absent from the proof boundary: {target}",
                )
            )

    owners: list[tuple[str, str, str]] = []
    for feature in features:
        for pattern in feature["diagnostic_owners"]:
            owners.append((feature["id"], pattern, f"$.features[{feature_ids.index(feature['id'])}].diagnostic_owners"))
    for left_index, (left_feature, left_pattern, left_path) in enumerate(owners):
        for right_feature, right_pattern, right_path in owners[left_index + 1 :]:
            if _patterns_overlap(left_pattern, right_pattern):
                findings.append(
                    Finding(
                        "AX-CONTRACT-2014",
                        f"{left_path} | {right_path}",
                        f"diagnostic ownership overlaps: {left_feature}:{left_pattern} and {right_feature}:{right_pattern}",
                    )
                )

    source_codes: set[str] = set()
    source_root = root / "axiom_proof"
    if source_root.is_dir():
        for path in sorted(source_root.rglob("*.py")):
            source_codes.update(DIAGNOSTIC_RE.findall(path.read_text(encoding="utf-8")))
    for code in sorted(source_codes):
        matches = [(feature, pattern) for feature, pattern, _ in owners if _matches_owner(code, pattern)]
        if not matches:
            findings.append(Finding("AX-CONTRACT-2015", "$.features[*].diagnostic_owners", f"unowned source diagnostic: {code}"))
        elif len(matches) > 1:
            findings.append(
                Finding(
                    "AX-CONTRACT-2016",
                    "$.features[*].diagnostic_owners",
                    f"source diagnostic has multiple owners: {code} -> {matches}",
                )
            )

    current_ids = set(feature_ids)
    deferred_id_set = set(deferred_ids)
    for index, claim in enumerate(contract["claim_documents"]):
        claim_path = root / claim["path"]
        if not claim_path.is_file():
            continue
        ids, error = _extract_claim_ids(
            claim_path.read_text(encoding="utf-8"), claim["start_marker"], claim["end_marker"]
        )
        if error is not None:
            findings.append(Finding("AX-CONTRACT-2017", claim["path"], error))
            continue
        assert ids is not None
        if ids != claim["feature_ids"]:
            findings.append(
                Finding(
                    "AX-CONTRACT-2018",
                    f"$.claim_documents[{index}].feature_ids",
                    f"claim block ids differ: expected {claim['feature_ids']}, got {ids}",
                )
            )
        for feature_id in ids:
            if feature_id not in current_ids:
                code = "AX-CONTRACT-2019" if feature_id in deferred_id_set else "AX-CONTRACT-2020"
                message = (
                    f"deferred feature is presented as implemented: {feature_id}"
                    if feature_id in deferred_id_set
                    else f"unknown feature is presented as implemented: {feature_id}"
                )
                findings.append(Finding(code, claim["path"], message))

    roadmap_path = root / contract["project"]["roadmap_contract"]
    if roadmap_path.is_file():
        roadmap, error = _load_json(roadmap_path, "roadmap")
        if error is not None:
            findings.append(Finding("AX-CONTRACT-2021", "$.project.roadmap_contract", error.message))
        elif roadmap is not None and roadmap.get("active_milestone") != contract["project"]["active_milestone"]:
            findings.append(
                Finding(
                    "AX-CONTRACT-2022",
                    "$.project.active_milestone",
                    f"project contract and roadmap disagree: {contract['project']['active_milestone']} != {roadmap.get('active_milestone')}",
                )
            )

    expected_ranks = {
        "normative-semantics": 1,
        "machine-readable-index": 2,
        "roadmap": 3,
        "release-contract": 4,
        "historical-rationale": 5,
        "summary": 6,
    }
    seen_roles = {authority["role"] for authority in contract["authorities"]}
    if seen_roles != set(expected_ranks):
        findings.append(
            Finding(
                "AX-CONTRACT-2023",
                "$.authorities",
                f"authority roles differ: expected {sorted(expected_ranks)}, got {sorted(seen_roles)}",
            )
        )
    for index, authority in enumerate(contract["authorities"]):
        expected = expected_ranks.get(authority["role"])
        if expected is not None and authority["rank"] != expected:
            findings.append(
                Finding(
                    "AX-CONTRACT-2024",
                    f"$.authorities[{index}].rank",
                    f"{authority['role']} must have rank {expected}",
                )
            )

    return findings


def check_project_contract(
    root: Path,
    contract_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    contract_path = (contract_path or root / "contracts" / "project.json").resolve()
    schema_path = (schema_path or root / "contracts" / "project.schema.json").resolve()
    dependencies = _dependency_versions()

    if JSONSCHEMA_IMPORT_ERROR is not None or Draft202012Validator is None:
        finding = Finding(
            "AX-CONTRACT-0005",
            "dependency.jsonschema",
            f"jsonschema is required: {JSONSCHEMA_IMPORT_ERROR}",
        )
        return _result(root, contract_path, schema_path, dependencies, [finding], EXIT_INPUT, 0, 0)

    contract, contract_error = _load_json(contract_path, "contract")
    schema, schema_error = _load_json(schema_path, "schema")
    input_findings = [item for item in (contract_error, schema_error) if item is not None]
    if input_findings:
        return _result(root, contract_path, schema_path, dependencies, input_findings, EXIT_INPUT, 0, 0)
    assert contract is not None and schema is not None

    schema_findings = _schema_findings(schema, contract)
    if schema_findings:
        return _result(root, contract_path, schema_path, dependencies, schema_findings, EXIT_SCHEMA, 0, 0)

    consistency_findings = sorted(_consistency_findings(root, contract))
    exit_code = EXIT_OK if not consistency_findings else EXIT_CONSISTENCY
    return _result(
        root,
        contract_path,
        schema_path,
        dependencies,
        consistency_findings,
        exit_code,
        len(contract["features"]),
        len(contract["deferred_features"]),
    )


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _result(
    root: Path,
    contract_path: Path,
    schema_path: Path,
    dependencies: dict[str, str],
    findings: Iterable[Finding],
    exit_code: int,
    current_features: int,
    deferred_features: int,
) -> dict[str, Any]:
    ordered = sorted(findings)
    return {
        "document_kind": "axiom.project-contract-check",
        "schema_version": "1.0.0",
        "status": "passed" if exit_code == EXIT_OK else "failed",
        "exit_code": exit_code,
        "contract": _display_path(root, contract_path),
        "schema": _display_path(root, schema_path),
        "validator": "jsonschema.Draft202012Validator",
        "dependencies": dependencies,
        "counts": {
            "current_features": current_features,
            "deferred_features": deferred_features,
            "findings": len(ordered),
        },
        "findings": [finding.to_dict() for finding in ordered],
    }


def render_text(result: dict[str, Any]) -> str:
    header = (
        f"AXIOM project contract: {result['status'].upper()} "
        f"(exit={result['exit_code']}, findings={result['counts']['findings']})"
    )
    lines = [header]
    for finding in result["findings"]:
        lines.append(f"[{finding['code']}] {finding['path']}: {finding['message']}")
    if result["status"] == "passed":
        lines.append(
            f"features={result['counts']['current_features']} "
            f"deferred={result['counts']['deferred_features']} "
            f"validator={result['validator']}"
        )
    return "\n".join(lines) + "\n"
