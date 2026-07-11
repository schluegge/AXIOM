from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bundle import (
    canonical_json,
    safe_join,
    safe_zip_entries,
    semantic_sha256,
    sha256_file,
)
from .contract import validate_document


@dataclass(frozen=True, order=True)
class ReplayFinding:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _schema(repository_root: Path, name: str) -> dict[str, Any]:
    return _load_json(repository_root / "benchmarks" / "schemas" / "0.1.0" / name)


def _bundle_path(root: Path, value: Any, label: str, *, required: bool = True) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty relative path")
    try:
        path = safe_join(root, value)
    except ValueError as error:
        raise ValueError(f"unsafe {label}: {error}") from error
    if required and not path.is_file():
        raise FileNotFoundError(f"{label} does not identify a regular bundle file: {value}")
    return path


def _add_schema_findings(
    findings: list[ReplayFinding],
    document: dict[str, Any],
    schema: dict[str, Any],
    label: str,
) -> bool:
    schema_findings = validate_document(document, schema, label=label)
    findings.extend(
        ReplayFinding(item.code, item.path, item.message) for item in schema_findings
    )
    return not schema_findings


def _tampered(findings: list[ReplayFinding], path: str, message: str) -> None:
    findings.append(ReplayFinding("AX-BENCH-REPLAY-TAMPERED", path, message))


def replay_conformance(repository_root: Path, bundle_path: Path) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    bundle_path = bundle_path.resolve()
    findings: list[ReplayFinding] = []
    task_id: str | None = None
    language: str | None = None
    adapter: str | None = None
    recorded: bool | None = None
    recomputed: bool | None = None
    files_verified = 0

    try:
        with zipfile.ZipFile(bundle_path, "r") as archive:
            entries = safe_zip_entries(archive)
            with tempfile.TemporaryDirectory(prefix="axiom-bench-replay-") as directory:
                root = Path(directory).resolve()
                for entry in entries:
                    target = _bundle_path(root, entry.filename, "ZIP entry", required=False)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(entry))

                manifest_path = _bundle_path(root, "bundle-manifest.json", "bundle manifest")
                manifest = _load_json(manifest_path)
                if not _add_schema_findings(
                    findings,
                    manifest,
                    _schema(repository_root, "bundle-manifest.schema.json"),
                    "bundle-manifest",
                ):
                    raise ValueError("bundle manifest failed schema validation")

                task_id = manifest["task_id"]
                language = manifest["language"]
                adapter = manifest["adapter"]
                expected_files = manifest["files"]
                actual_files = {
                    path.relative_to(root).as_posix()
                    for path in root.rglob("*")
                    if path.is_file() and path != manifest_path
                }
                if set(expected_files) != actual_files:
                    _tampered(
                        findings,
                        "bundle-manifest.files",
                        f"manifest paths differ from archive: expected {sorted(expected_files)}, got {sorted(actual_files)}",
                    )

                for relative, expected in sorted(expected_files.items()):
                    path = _bundle_path(root, relative, f"manifest file {relative}", required=False)
                    if not path.is_file():
                        _tampered(findings, relative, "manifest file is missing")
                        continue
                    actual_sha = sha256_file(path)
                    actual_size = path.stat().st_size
                    if actual_sha != expected["sha256"] or actual_size != expected["size_bytes"]:
                        _tampered(findings, relative, "file hash or size differs from manifest")
                    else:
                        files_verified += 1

                semantic_payload = {
                    "bundle_kind": manifest["bundle_kind"],
                    "task_id": manifest["task_id"],
                    "language": manifest["language"],
                    "adapter": manifest["adapter"],
                    "files": manifest["files"],
                }
                if semantic_sha256(semantic_payload) != manifest["semantic_sha256"]:
                    _tampered(
                        findings,
                        "bundle-manifest.semantic_sha256",
                        "bundle semantic hash mismatch",
                    )

                attempt_path = _bundle_path(root, "attempt.json", "canonical attempt")
                report_path = _bundle_path(
                    root, "conformance-report.json", "canonical conformance report"
                )
                attempt = _load_json(attempt_path)
                report = _load_json(report_path)
                attempt_valid = _add_schema_findings(
                    findings,
                    attempt,
                    _schema(repository_root, "attempt.schema.json"),
                    "attempt",
                )
                report_valid = _add_schema_findings(
                    findings,
                    report,
                    _schema(repository_root, "conformance-report.schema.json"),
                    "conformance-report",
                )
                if not attempt_valid or not report_valid:
                    raise ValueError("attempt or conformance report failed schema validation")

                recorded = report["conformance_passed"]
                if report["task_id"] != task_id or attempt["task_id"] != task_id:
                    _tampered(findings, "task_id", "manifest, report, and attempt task IDs differ")
                if report["language"] != language or attempt["language"] != language:
                    _tampered(findings, "language", "manifest, report, and attempt languages differ")
                if report["adapter"] != adapter or attempt["adapter"] != adapter:
                    _tampered(findings, "adapter", "manifest, report, and attempt adapters differ")

                referenced_attempt = _bundle_path(
                    root, report["attempt_path"], "conformance-report.attempt_path"
                )
                if referenced_attempt != attempt_path:
                    _tampered(
                        findings,
                        "conformance-report.attempt_path",
                        "attempt path is not the canonical attempt.json path",
                    )
                if sha256_file(referenced_attempt) != report["attempt_sha256"]:
                    _tampered(
                        findings,
                        "conformance-report.attempt_sha256",
                        "attempt hash mismatch",
                    )

                trace_path = _bundle_path(
                    root,
                    report["canonical_trace_path"],
                    "conformance-report.canonical_trace_path",
                )
                if trace_path != _bundle_path(root, "trace.jsonl", "canonical trace"):
                    _tampered(
                        findings,
                        "conformance-report.canonical_trace_path",
                        "trace path is not the canonical trace.jsonl path",
                    )
                if sha256_file(trace_path) != report["canonical_trace_sha256"]:
                    _tampered(
                        findings,
                        "conformance-report.canonical_trace_sha256",
                        "trace hash mismatch",
                    )
                if attempt["trace_path"] != report["canonical_trace_path"]:
                    _tampered(findings, "attempt.trace_path", "attempt and report trace paths differ")
                if attempt["trace_sha256"] != report["canonical_trace_sha256"]:
                    _tampered(findings, "attempt.trace_sha256", "attempt and report trace hashes differ")

                command_schema = _schema(repository_root, "command-record.schema.json")
                for index, reference in enumerate(attempt["command_records"]):
                    path = _bundle_path(
                        root,
                        reference["path"],
                        f"attempt.command_records[{index}].path",
                    )
                    if sha256_file(path) != reference["sha256"]:
                        _tampered(findings, reference["path"], "command record has the wrong hash")
                        continue
                    command = _load_json(path)
                    if not _add_schema_findings(
                        findings,
                        command,
                        command_schema,
                        f"command:{reference['path']}",
                    ):
                        continue
                    if command["phase"] != reference["phase"]:
                        _tampered(
                            findings,
                            reference["path"],
                            "command phase differs from attempt reference",
                        )
                    for stream in ("stdout", "stderr"):
                        stream_path = _bundle_path(
                            root,
                            command[f"{stream}_path"],
                            f"command.{stream}_path",
                        )
                        actual_sha = sha256_file(stream_path)
                        actual_size = stream_path.stat().st_size
                        if actual_sha != command[f"{stream}_sha256"]:
                            _tampered(
                                findings,
                                command[f"{stream}_path"],
                                f"{stream} payload has the wrong hash",
                            )
                        if actual_size != command[f"{stream}_bytes"]:
                            _tampered(
                                findings,
                                command[f"{stream}_path"],
                                f"{stream} payload has the wrong size",
                            )

                trace_schema = _schema(repository_root, "trace-event.schema.json")
                sequence = 0
                with trace_path.open("r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise ValueError("trace event must be an object")
                        _add_schema_findings(
                            findings,
                            event,
                            trace_schema,
                            f"trace:{line_number}",
                        )
                        if event.get("sequence") != sequence:
                            _tampered(
                                findings,
                                f"trace:{line_number}",
                                f"expected sequence {sequence}, got {event.get('sequence')}",
                            )
                        sequence += 1

                outcomes = attempt["outcomes"]
                full_success = all(
                    outcomes.get(field) is True
                    for field in (
                        "extraction_success",
                        "compile_success",
                        "public_test_success",
                        "acceptance_test_success",
                        "security_success",
                    )
                )
                expected = report["expected_outcome"]
                recomputed = (
                    full_success is expected["full_success"]
                    and attempt["failure_reason"] == expected["failure_reason"]
                    and attempt["evidence_complete"] is True
                )
                if report["actual_full_success"] is not full_success:
                    _tampered(
                        findings,
                        "conformance-report.actual_full_success",
                        "recorded full-success value differs from attempt outcomes",
                    )
                if report["actual_failure_reason"] != attempt["failure_reason"]:
                    _tampered(
                        findings,
                        "conformance-report.actual_failure_reason",
                        "recorded failure reason differs from attempt",
                    )
                if recorded is not recomputed:
                    _tampered(
                        findings,
                        "conformance-report.conformance_passed",
                        "recorded conformance decision differs from replay",
                    )
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
        UnicodeError,
    ) as error:
        _tampered(findings, "bundle", f"cannot replay bundle: {error}")

    report_value = {
        "document_kind": "axiom.bench.replay-report",
        "schema_version": "0.1.0",
        "status": "passed" if not findings else "failed",
        "bundle_path": bundle_path.as_posix(),
        "bundle_sha256": sha256_file(bundle_path) if bundle_path.is_file() else "0" * 64,
        "task_id": task_id,
        "language": language,
        "adapter": adapter,
        "recorded_conformance_passed": recorded,
        "recomputed_conformance_passed": recomputed,
        "subprocesses_executed": 0,
        "files_verified": files_verified,
        "findings": [item.as_dict() for item in sorted(set(findings))],
    }
    replay_schema = _schema(repository_root, "replay-report.schema.json")
    schema_findings = validate_document(report_value, replay_schema, label="replay-report")
    if schema_findings:
        report_value["status"] = "failed"
        report_value["findings"].extend(
            {"code": item.code, "path": item.path, "message": item.message}
            for item in schema_findings
        )
    return report_value


def render_replay_report(report: dict[str, Any]) -> str:
    return canonical_json(report)
