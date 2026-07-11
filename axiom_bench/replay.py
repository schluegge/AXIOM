from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bundle import (
    canonical_json,
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


def _add_schema_findings(
    findings: list[ReplayFinding],
    document: dict[str, Any],
    schema: dict[str, Any],
    label: str,
) -> None:
    for item in validate_document(document, schema, label=label):
        findings.append(ReplayFinding(item.code, item.path, item.message))


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
                root = Path(directory)
                for entry in entries:
                    target = root.joinpath(*Path(entry.filename).parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(entry))

                manifest_path = root / "bundle-manifest.json"
                if not manifest_path.is_file():
                    raise ValueError("bundle-manifest.json is missing")
                manifest = _load_json(manifest_path)
                _add_schema_findings(
                    findings,
                    manifest,
                    _schema(repository_root, "bundle-manifest.schema.json"),
                    "bundle-manifest",
                )
                task_id = manifest.get("task_id")
                language = manifest.get("language")
                adapter = manifest.get("adapter")

                expected_files = manifest.get("files", {})
                actual_files = {
                    path.relative_to(root).as_posix()
                    for path in root.rglob("*")
                    if path.is_file() and path != manifest_path
                }
                if set(expected_files) != actual_files:
                    findings.append(
                        ReplayFinding(
                            "AX-BENCH-REPLAY-TAMPERED",
                            "bundle-manifest.files",
                            f"manifest paths differ from archive: expected {sorted(expected_files)}, got {sorted(actual_files)}",
                        )
                    )

                for relative, expected in sorted(expected_files.items()):
                    path = root / relative
                    if not path.is_file():
                        continue
                    actual_sha = sha256_file(path)
                    actual_size = path.stat().st_size
                    if actual_sha != expected.get("sha256") or actual_size != expected.get("size_bytes"):
                        findings.append(
                            ReplayFinding(
                                "AX-BENCH-REPLAY-TAMPERED",
                                relative,
                                "file hash or size differs from manifest",
                            )
                        )
                    else:
                        files_verified += 1

                semantic_payload = {
                    "bundle_kind": manifest.get("bundle_kind"),
                    "task_id": manifest.get("task_id"),
                    "language": manifest.get("language"),
                    "adapter": manifest.get("adapter"),
                    "files": manifest.get("files"),
                }
                if semantic_sha256(semantic_payload) != manifest.get("semantic_sha256"):
                    findings.append(
                        ReplayFinding(
                            "AX-BENCH-REPLAY-TAMPERED",
                            "bundle-manifest.semantic_sha256",
                            "bundle semantic hash mismatch",
                        )
                    )

                attempt = _load_json(root / "attempt.json")
                report = _load_json(root / "conformance-report.json")
                _add_schema_findings(
                    findings,
                    attempt,
                    _schema(repository_root, "attempt.schema.json"),
                    "attempt",
                )
                _add_schema_findings(
                    findings,
                    report,
                    _schema(repository_root, "conformance-report.schema.json"),
                    "conformance-report",
                )
                recorded = report.get("conformance_passed")

                if sha256_file(root / report["attempt_path"]) != report.get("attempt_sha256"):
                    findings.append(
                        ReplayFinding(
                            "AX-BENCH-REPLAY-TAMPERED",
                            "conformance-report.attempt_sha256",
                            "attempt hash mismatch",
                        )
                    )
                if sha256_file(root / report["canonical_trace_path"]) != report.get(
                    "canonical_trace_sha256"
                ):
                    findings.append(
                        ReplayFinding(
                            "AX-BENCH-REPLAY-TAMPERED",
                            "conformance-report.canonical_trace_sha256",
                            "trace hash mismatch",
                        )
                    )

                command_schema = _schema(repository_root, "command-record.schema.json")
                for reference in attempt.get("command_records", []):
                    path = root / reference["path"]
                    if not path.is_file() or sha256_file(path) != reference.get("sha256"):
                        findings.append(
                            ReplayFinding(
                                "AX-BENCH-REPLAY-TAMPERED",
                                reference.get("path", "command"),
                                "command record is missing or has the wrong hash",
                            )
                        )
                        continue
                    command = _load_json(path)
                    _add_schema_findings(
                        findings,
                        command,
                        command_schema,
                        f"command:{reference['path']}",
                    )
                    for stream in ("stdout", "stderr"):
                        stream_path = root / command[f"{stream}_path"]
                        if not stream_path.is_file() or sha256_file(stream_path) != command.get(
                            f"{stream}_sha256"
                        ):
                            findings.append(
                                ReplayFinding(
                                    "AX-BENCH-REPLAY-TAMPERED",
                                    command[f"{stream}_path"],
                                    f"{stream} payload is missing or has the wrong hash",
                                )
                            )

                trace_path = root / report["canonical_trace_path"]
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
                            findings.append(
                                ReplayFinding(
                                    "AX-BENCH-REPLAY-TAMPERED",
                                    f"trace:{line_number}",
                                    f"expected sequence {sequence}, got {event.get('sequence')}",
                                )
                            )
                        sequence += 1

                outcomes = attempt.get("outcomes", {})
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
                expected = report.get("expected_outcome", {})
                recomputed = (
                    full_success is expected.get("full_success")
                    and attempt.get("failure_reason") == expected.get("failure_reason")
                )
                if report.get("actual_full_success") is not full_success:
                    findings.append(
                        ReplayFinding(
                            "AX-BENCH-REPLAY-TAMPERED",
                            "conformance-report.actual_full_success",
                            "recorded full-success value differs from attempt outcomes",
                        )
                    )
                if report.get("actual_failure_reason") != attempt.get("failure_reason"):
                    findings.append(
                        ReplayFinding(
                            "AX-BENCH-REPLAY-TAMPERED",
                            "conformance-report.actual_failure_reason",
                            "recorded failure reason differs from attempt",
                        )
                    )
                if recorded is not recomputed:
                    findings.append(
                        ReplayFinding(
                            "AX-BENCH-REPLAY-TAMPERED",
                            "conformance-report.conformance_passed",
                            "recorded conformance decision differs from replay",
                        )
                    )
    except (FileNotFoundError, OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        findings.append(
            ReplayFinding("AX-BENCH-REPLAY-TAMPERED", "bundle", f"cannot replay bundle: {error}")
        )

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
        "findings": [item.as_dict() for item in sorted(findings)],
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
