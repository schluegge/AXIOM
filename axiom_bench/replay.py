from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bundle import (
    canonical_json,
    read_bounded_zip_entry,
    safe_join,
    safe_zip_entries,
    semantic_sha256,
    sha256_file,
)
from .contract import validate_document

_PHASE_ORDER = ("format", "check", "public_test", "acceptance_test", "security_test")
_PHASE_FAILURE = {
    "format": "format_failure",
    "check": "compile_failure",
    "public_test": "public_test_failure",
    "acceptance_test": "acceptance_test_failure",
    "security_test": "security_failure",
}


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


def _schema(root: Path, name: str) -> dict[str, Any]:
    return _load_json(root / "benchmarks" / "schemas" / "0.1.0" / name)


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


def _schema_ok(
    findings: list[ReplayFinding],
    document: dict[str, Any],
    schema: dict[str, Any],
    label: str,
) -> bool:
    errors = validate_document(document, schema, label=label)
    findings.extend(ReplayFinding(item.code, item.path, item.message) for item in errors)
    return not errors


def _tampered(findings: list[ReplayFinding], path: str, message: str) -> None:
    findings.append(ReplayFinding("AX-BENCH-REPLAY-TAMPERED", path, message))


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _candidate_integrity(
    root: Path, attempt: dict[str, Any], findings: list[ReplayFinding]
) -> bool:
    raw = _bundle_path(root, attempt["raw_completion_path"], "attempt.raw_completion_path")
    extracted = _bundle_path(
        root, attempt["extracted_artifact_path"], "attempt.extracted_artifact_path"
    )
    canonical = _bundle_path(root, "candidate.bin", "canonical candidate")
    valid = True
    if raw != extracted:
        _tampered(
            findings,
            "attempt.extracted_artifact_path",
            "trusted raw and extracted candidates must identify the same file",
        )
        valid = False
    if raw != canonical:
        _tampered(
            findings,
            "attempt.raw_completion_path",
            "trusted candidate path is not canonical candidate.bin",
        )
        valid = False
    raw_sha = sha256_file(raw)
    extracted_sha = sha256_file(extracted)
    if raw_sha != attempt["raw_completion_sha256"]:
        _tampered(
            findings,
            "attempt.raw_completion_sha256",
            "raw completion hash differs from candidate bytes",
        )
        valid = False
    if extracted_sha != attempt["extracted_artifact_sha256"]:
        _tampered(
            findings,
            "attempt.extracted_artifact_sha256",
            "extracted artifact hash differs from candidate bytes",
        )
        valid = False
    if attempt["raw_completion_sha256"] != attempt["extracted_artifact_sha256"]:
        _tampered(
            findings,
            "attempt.extracted_artifact_sha256",
            "trusted raw and extracted candidate hashes differ",
        )
        valid = False
    if attempt["mutations"].get("patch_bytes") != raw.stat().st_size:
        _tampered(
            findings,
            "attempt.mutations.patch_bytes",
            "recorded patch bytes differ from candidate size",
        )
        valid = False
    return valid


def _command_failure(command: dict[str, Any], feedback: int, limit: int) -> str | None:
    if command["termination"] == "not_started" or command["return_code"] is None:
        return "runner_error"
    if command["timed_out"]:
        return "timeout"
    if command["output_limited"] or feedback > limit:
        return "resource_limit"
    if command["return_code"] != 0:
        return _PHASE_FAILURE[command["phase"]]
    return None


def _apply_outcome(outcomes: dict[str, bool | None], phase: str, success: bool) -> None:
    if phase == "check":
        outcomes["parse_success"] = success
        outcomes["compile_success"] = success
    elif phase == "public_test":
        outcomes["public_test_success"] = success
    elif phase == "acceptance_test":
        outcomes["acceptance_test_success"] = success
    elif phase == "security_test":
        outcomes["security_success"] = success


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
                extracted_total = 0
                for entry in entries:
                    payload, extracted_total = read_bounded_zip_entry(
                        archive, entry, total_bytes=extracted_total
                    )
                    target = _bundle_path(root, entry.filename, "ZIP entry", required=False)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)

                manifest_path = _bundle_path(root, "bundle-manifest.json", "bundle manifest")
                manifest = _load_json(manifest_path)
                if not _schema_ok(
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
                    if (
                        sha256_file(path) != expected["sha256"]
                        or path.stat().st_size != expected["size_bytes"]
                    ):
                        _tampered(findings, relative, "file hash or size differs from manifest")
                    else:
                        files_verified += 1

                semantic_payload = {
                    "bundle_kind": manifest["bundle_kind"],
                    "task_id": task_id,
                    "language": language,
                    "adapter": adapter,
                    "files": expected_files,
                }
                if semantic_sha256(semantic_payload) != manifest["semantic_sha256"]:
                    _tampered(
                        findings,
                        "bundle-manifest.semantic_sha256",
                        "bundle semantic hash mismatch",
                    )

                canonical_attempt_path = _bundle_path(root, "attempt.json", "canonical attempt")
                canonical_report_path = _bundle_path(
                    root, "conformance-report.json", "canonical conformance report"
                )
                attempt = _load_json(canonical_attempt_path)
                report = _load_json(canonical_report_path)
                if not _schema_ok(
                    findings,
                    attempt,
                    _schema(repository_root, "attempt.schema.json"),
                    "attempt",
                ) or not _schema_ok(
                    findings,
                    report,
                    _schema(repository_root, "conformance-report.schema.json"),
                    "conformance-report",
                ):
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
                if referenced_attempt != canonical_attempt_path:
                    _tampered(
                        findings,
                        "conformance-report.attempt_path",
                        "attempt path is not canonical attempt.json",
                    )
                if sha256_file(referenced_attempt) != report["attempt_sha256"]:
                    _tampered(
                        findings,
                        "conformance-report.attempt_sha256",
                        "attempt hash mismatch",
                    )

                candidate_valid = _candidate_integrity(root, attempt, findings)
                trace_path = _bundle_path(
                    root,
                    report["canonical_trace_path"],
                    "conformance-report.canonical_trace_path",
                )
                if trace_path != _bundle_path(root, "trace.jsonl", "canonical trace"):
                    _tampered(
                        findings,
                        "conformance-report.canonical_trace_path",
                        "trace path is not canonical trace.jsonl",
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

                budgets = attempt["budgets"]
                max_feedback = _positive_int(
                    budgets.get("max_feedback_bytes"), "attempt.budgets.max_feedback_bytes"
                )
                max_invocations = _positive_int(
                    budgets.get("max_compiler_invocations"),
                    "attempt.budgets.max_compiler_invocations",
                )
                command_schema = _schema(repository_root, "command-record.schema.json")
                commands: list[dict[str, Any]] = []
                cumulative_feedback = 0
                derived_failure: str | None = None
                phase_results: dict[str, tuple[bool, str | None]] = {}

                for index, reference in enumerate(attempt["command_records"]):
                    if index >= len(_PHASE_ORDER):
                        _tampered(findings, "attempt.command_records", "too many command records")
                        break
                    expected_phase = _PHASE_ORDER[index]
                    if reference["phase"] != expected_phase:
                        _tampered(
                            findings,
                            f"attempt.command_records[{index}].phase",
                            f"expected phase {expected_phase}, got {reference['phase']}",
                        )
                    path = _bundle_path(
                        root,
                        reference["path"],
                        f"attempt.command_records[{index}].path",
                    )
                    if sha256_file(path) != reference["sha256"]:
                        _tampered(findings, reference["path"], "command record has the wrong hash")
                        continue
                    command = _load_json(path)
                    if not _schema_ok(
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
                    if derived_failure is not None:
                        _tampered(
                            findings,
                            reference["path"],
                            "command record appears after the first derived failure",
                        )

                    stream_bytes = 0
                    for stream in ("stdout", "stderr"):
                        stream_path = _bundle_path(
                            root,
                            command[f"{stream}_path"],
                            f"command.{stream}_path",
                        )
                        actual_size = stream_path.stat().st_size
                        stream_bytes += actual_size
                        if sha256_file(stream_path) != command[f"{stream}_sha256"]:
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
                    cumulative_feedback += stream_bytes
                    failure = _command_failure(command, cumulative_feedback, max_feedback)
                    success = failure is None
                    phase_results[command["phase"]] = (success, failure)
                    if failure is not None and derived_failure is None:
                        derived_failure = failure
                    commands.append(command)

                if len(commands) > max_invocations:
                    _tampered(
                        findings,
                        "attempt.usage.compiler_invocations",
                        "retained command count exceeds invocation budget",
                    )
                if attempt["usage"]["compiler_invocations"] != len(commands):
                    _tampered(
                        findings,
                        "attempt.usage.compiler_invocations",
                        "recorded invocation usage differs from command records",
                    )
                if attempt["usage"]["feedback_bytes"] != cumulative_feedback:
                    _tampered(
                        findings,
                        "attempt.usage.feedback_bytes",
                        "recorded feedback differs from retained stream bytes",
                    )

                trace_schema = _schema(repository_root, "trace-event.schema.json")
                trace_events: list[dict[str, Any]] = []
                with trace_path.open("r", encoding="utf-8") as handle:
                    for sequence, line in enumerate(handle):
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise ValueError("trace event must be an object")
                        _schema_ok(findings, event, trace_schema, f"trace:{sequence + 1}")
                        if event.get("sequence") != sequence:
                            _tampered(
                                findings,
                                f"trace:{sequence + 1}",
                                f"expected sequence {sequence}, got {event.get('sequence')}",
                            )
                        trace_events.append(event)

                terminal_reasons = [
                    "timeout" if event.get("event_kind") == "timeout" else "resource_limit"
                    for event in trace_events
                    if event.get("event_kind") in {"timeout", "budget_exhausted"}
                ]
                if derived_failure is None and len(commands) < 4:
                    if terminal_reasons:
                        derived_failure = terminal_reasons[-1]
                    elif len(commands) >= max_invocations:
                        derived_failure = "resource_limit"
                    else:
                        _tampered(
                            findings,
                            "attempt.command_records",
                            "successful command prefix ends before acceptance without terminal reason",
                        )

                derived_outcomes: dict[str, bool | None] = {
                    "extraction_success": candidate_valid,
                    "parse_success": None,
                    "compile_success": None,
                    "public_test_success": None,
                    "acceptance_test_success": None,
                    "security_success": None,
                    "full_success": False,
                }
                for command in commands:
                    success, _ = phase_results[command["phase"]]
                    _apply_outcome(derived_outcomes, command["phase"], success)
                if (
                    derived_failure is None
                    and derived_outcomes["acceptance_test_success"] is True
                    and "security_test" not in phase_results
                ):
                    derived_outcomes["security_success"] = True
                derived_outcomes["full_success"] = all(
                    derived_outcomes[field] is True
                    for field in (
                        "extraction_success",
                        "compile_success",
                        "public_test_success",
                        "acceptance_test_success",
                        "security_success",
                    )
                )

                for field, derived in derived_outcomes.items():
                    if attempt["outcomes"].get(field) is not derived:
                        _tampered(
                            findings,
                            f"attempt.outcomes.{field}",
                            f"recorded outcome {attempt['outcomes'].get(field)!r} differs from replay-derived {derived!r}",
                        )
                if attempt["failure_reason"] != derived_failure:
                    _tampered(
                        findings,
                        "attempt.failure_reason",
                        f"recorded failure {attempt['failure_reason']!r} differs from replay-derived {derived_failure!r}",
                    )

                check_events = [
                    event for event in trace_events if event.get("event_kind") == "check_result"
                ]
                if len(check_events) != len(commands):
                    _tampered(
                        findings,
                        "trace.check_result",
                        "trace check-result count differs from command count",
                    )
                for event, command in zip(check_events, commands):
                    success, failure = phase_results[command["phase"]]
                    payload = event.get("payload", {})
                    if (
                        payload.get("phase") != command["phase"]
                        or payload.get("success") is not success
                        or payload.get("failure_reason") != failure
                    ):
                        _tampered(
                            findings,
                            f"trace.check_result.{command['phase']}",
                            "trace check result differs from replay-derived result",
                        )

                expected = report["expected_outcome"]
                recomputed = (
                    derived_outcomes["full_success"] is expected["full_success"]
                    and derived_failure == expected["failure_reason"]
                    and attempt["evidence_complete"] is True
                )
                if report["actual_full_success"] is not derived_outcomes["full_success"]:
                    _tampered(
                        findings,
                        "conformance-report.actual_full_success",
                        "recorded full success differs from replay-derived outcomes",
                    )
                if report["actual_failure_reason"] != derived_failure:
                    _tampered(
                        findings,
                        "conformance-report.actual_failure_reason",
                        "recorded failure differs from replay-derived failure",
                    )
                if recorded is not recomputed:
                    _tampered(
                        findings,
                        "conformance-report.conformance_passed",
                        "recorded conformance decision differs from replay",
                    )

                score_events = [
                    event for event in trace_events if event.get("event_kind") == "score_decision"
                ]
                if len(score_events) != 1:
                    _tampered(
                        findings,
                        "trace.score_decision",
                        "trace must contain exactly one score decision",
                    )
                else:
                    score = score_events[0].get("payload", {})
                    if (
                        score.get("full_success") is not derived_outcomes["full_success"]
                        or score.get("failure_reason") != derived_failure
                        or score.get("conformance_passed") is not recomputed
                    ):
                        _tampered(
                            findings,
                            "trace.score_decision",
                            "trace score decision differs from replay-derived decision",
                        )
    except (
        FileNotFoundError,
        KeyError,
        MemoryError,
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
