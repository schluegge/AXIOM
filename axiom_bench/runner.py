from __future__ import annotations

import difflib
import json
import math
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from .bundle import (
    build_manifest,
    canonical_attempt,
    canonical_command_record,
    canonical_stream_bytes,
    canonical_trace_event,
    safe_join,
    sha256_bytes,
    sha256_file,
    write_deterministic_zip,
    write_json,
    write_jsonl,
)
from .contract import validate_document
from .executor import ExecutionResult, execute_bounded, minimal_environment

Language = Literal["axiom", "rust", "zig", "go"]
Adapter = Literal["reference", "seeded_wrong"]

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
_PLACEHOLDERS = {"python", "workspace", "task_root", "candidate", "language"}
_PHASES = (
    ("format", "formatter_command", "format_failure"),
    ("check", "check_command", "compile_failure"),
    ("public_test", "public_test_command", "public_test_failure"),
    ("acceptance_test", "acceptance_test_command", "acceptance_test_failure"),
    ("security_test", "security_test_command", "security_failure"),
)


@dataclass(frozen=True)
class RunnerFinding:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class RunnerError(RuntimeError):
    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.finding = RunnerFinding(code, path, message)


@dataclass(frozen=True)
class ConformanceResult:
    output_directory: Path
    bundle_path: Path
    bundle_sha256: str
    conformance_passed: bool
    full_success: bool
    failure_reason: str | None
    report: dict[str, Any]


class _Trace:
    def __init__(self, run_id: str, task_id: str, language: Language) -> None:
        self.run_id = run_id
        self.task_id = task_id
        self.language = language
        self.events: list[dict[str, Any]] = []

    def add(self, kind: str, payload: dict[str, Any], attempt: int = 1) -> None:
        self.events.append(
            {
                "document_kind": "axiom.bench.trace-event",
                "schema_version": "0.1.0",
                "sequence": len(self.events),
                "event_kind": kind,
                "run_id": self.run_id,
                "task_id": self.task_id,
                "language": self.language,
                "attempt_number": attempt,
                "timestamp": _utc_now(),
                "payload": payload,
                "payload_path": None,
                "payload_sha256": None,
            }
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RunnerError("AX-BENCH-RUNNER-INVALID-TASK", path.as_posix(), "JSON file does not exist") from error
    except (OSError, UnicodeError) as error:
        raise RunnerError("AX-BENCH-RUNNER-INVALID-TASK", path.as_posix(), f"cannot read JSON file: {error}") from error
    except json.JSONDecodeError as error:
        raise RunnerError(
            "AX-BENCH-RUNNER-INVALID-TASK",
            path.as_posix(),
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}",
        ) from error
    if not isinstance(value, dict):
        raise RunnerError("AX-BENCH-RUNNER-INVALID-TASK", path.as_posix(), "JSON root must be an object")
    return value


def _schema(root: Path, name: str) -> dict[str, Any]:
    return _load_json(root / "benchmarks" / "schemas" / "0.1.0" / name)


def _require_valid(document: dict[str, Any], schema: dict[str, Any], label: str) -> None:
    findings = validate_document(document, schema, label=label)
    if findings:
        first = findings[0]
        raise RunnerError("AX-BENCH-RUNNER-INVALID-TASK", first.path, first.message)


def assert_local_trust(trust_class: str) -> None:
    if trust_class not in {"trusted_reference", "trusted_seeded_wrong"}:
        raise RunnerError(
            "AX-BENCH-SANDBOX-REQUIRED",
            "trust_class",
            "local execution accepts only repository-controlled trusted conformance fixtures",
        )


def _safe_file(root: Path, relative: str, label: str) -> Path:
    try:
        path = safe_join(root, relative)
    except ValueError as error:
        raise RunnerError("AX-BENCH-RUNNER-INVALID-PATH", label, str(error)) from error
    current = path
    while True:
        if current.is_symlink():
            raise RunnerError("AX-BENCH-RUNNER-SYMLINK", label, f"symbolic link is forbidden: {relative}")
        if current == root or current == current.parent:
            break
        current = current.parent
    if not path.is_file():
        raise RunnerError("AX-BENCH-RUNNER-INVALID-PATH", label, f"required regular file is missing: {relative}")
    return path


def _workspace_file(root: Path, relative: str, label: str) -> Path:
    try:
        return safe_join(root, relative)
    except ValueError as error:
        raise RunnerError("AX-BENCH-RUNNER-INVALID-PATH", label, str(error)) from error


def _prepare_output(path: Path, repository_root: Path, task_root: Path) -> Path:
    output = path.resolve()
    if output.exists():
        raise RunnerError("AX-BENCH-RUNNER-INVALID-PATH", "output_directory", "output directory must not already exist")
    for protected, label in ((repository_root, "repository"), (task_root, "task root")):
        try:
            output.relative_to(protected)
        except ValueError:
            continue
        raise RunnerError("AX-BENCH-RUNNER-INVALID-PATH", "output_directory", f"output directory may not be inside the {label}")
    try:
        output.mkdir(parents=True)
    except OSError as error:
        raise RunnerError("AX-BENCH-RUNNER-INVALID-PATH", "output_directory", f"cannot create output directory: {error}") from error
    return output


def expand_command(
    command: list[str],
    *,
    workspace: Path,
    task_root: Path,
    candidate: Path,
    language: Language,
) -> list[str]:
    replacements = {
        "python": sys.executable,
        "workspace": str(workspace),
        "task_root": str(task_root),
        "candidate": str(candidate),
        "language": language,
    }
    expanded: list[str] = []
    for index, argument in enumerate(command):
        names = _PLACEHOLDER.findall(argument)
        if set(names) - _PLACEHOLDERS or (("{" in argument or "}" in argument) and not names):
            raise RunnerError("AX-BENCH-RUNNER-UNKNOWN-PLACEHOLDER", f"command[{index}]", f"unknown or malformed command placeholder: {argument}")
        value = argument
        for name in names:
            value = value.replace("{" + name + "}", replacements[name])
        if "{" in value or "}" in value:
            raise RunnerError("AX-BENCH-RUNNER-UNKNOWN-PLACEHOLDER", f"command[{index}]", f"unresolved command placeholder: {argument}")
        expanded.append(value)
    if not expanded:
        raise RunnerError("AX-BENCH-RUNNER-INVALID-TASK", "command", "command is empty")
    return expanded


def _changed_lines(before: bytes, after: bytes) -> int:
    left = before.decode("utf-8", errors="replace").splitlines()
    right = after.decode("utf-8", errors="replace").splitlines()
    return sum(1 for line in difflib.ndiff(left, right) if line.startswith(("+ ", "- ")))


def _command_record(
    command_id: str,
    phase: str,
    execution: ExecutionResult,
    stdout_path: str,
    stderr_path: str,
) -> dict[str, Any]:
    return {
        "document_kind": "axiom.bench.command-record",
        "schema_version": "0.1.0",
        "command_id": command_id,
        "phase": phase,
        "argv": list(execution.argv),
        "cwd": execution.cwd,
        "environment": execution.environment,
        "started_at": execution.started_at,
        "finished_at": execution.finished_at,
        "duration_ms": execution.duration_ms,
        "return_code": execution.return_code,
        "timed_out": execution.timed_out,
        "output_limited": execution.output_limited,
        "termination": execution.termination,
        "stdout_path": stdout_path,
        "stdout_sha256": sha256_bytes(execution.stdout),
        "stdout_bytes": len(execution.stdout),
        "stderr_path": stderr_path,
        "stderr_sha256": sha256_bytes(execution.stderr),
        "stderr_bytes": len(execution.stderr),
    }


def _not_started(argv: list[str], workspace: Path, environment: dict[str, str], error: Exception) -> ExecutionResult:
    now = _utc_now()
    return ExecutionResult(
        argv=tuple(argv),
        cwd=str(workspace),
        environment=dict(sorted(environment.items())),
        started_at=now,
        finished_at=now,
        duration_ms=0,
        return_code=None,
        timed_out=False,
        output_limited=False,
        termination="not_started",
        stdout=b"",
        stderr=(f"{type(error).__name__}: {error}\n").encode("utf-8", errors="replace"),
    )


def _write_payload(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_trace(
    raw_path: Path,
    canonical_path: Path,
    events: Iterable[dict[str, Any]],
    workspace: Path,
    task_root: Path,
    schema: dict[str, Any],
) -> str:
    values = list(events)
    for index, event in enumerate(values):
        _require_valid(event, schema, f"trace[{index}]")
    write_jsonl(raw_path, values)
    canonical = [canonical_trace_event(event, workspace, task_root) for event in values]
    for index, event in enumerate(canonical):
        _require_valid(event, schema, f"canonical-trace[{index}]")
    write_jsonl(canonical_path, canonical)
    return sha256_file(canonical_path)


def _update_outcome(outcomes: dict[str, bool | None], phase: str, success: bool) -> None:
    if phase == "check":
        outcomes["parse_success"] = success
        outcomes["compile_success"] = success
    elif phase == "public_test":
        outcomes["public_test_success"] = success
    elif phase == "acceptance_test":
        outcomes["acceptance_test_success"] = success
    elif phase == "security_test":
        outcomes["security_success"] = success


def run_conformance(
    repository_root: Path,
    task_path: Path,
    *,
    language: Language,
    adapter: Adapter,
    output_directory: Path,
    wrong_index: int = 0,
) -> ConformanceResult:
    repository_root = repository_root.resolve()
    task_path = task_path.resolve()
    task_root = task_path.parent
    task = _load_json(task_path)
    _require_valid(task, _schema(repository_root, "task.schema.json"), "task")
    if language not in task["variants"]:
        raise RunnerError("AX-BENCH-RUNNER-INVALID-TASK", "language", f"task has no {language} variant")
    if adapter not in {"reference", "seeded_wrong"}:
        raise RunnerError("AX-BENCH-SANDBOX-REQUIRED", "adapter", "local runner implements only trusted reference and seeded-wrong adapters")

    trust_class = "trusted_reference" if adapter == "reference" else "trusted_seeded_wrong"
    assert_local_trust(trust_class)
    variant = task["variants"][language]
    candidate_relative = variant.get("candidate_path")
    if not isinstance(candidate_relative, str) or not candidate_relative:
        raise RunnerError("AX-BENCH-RUNNER-INVALID-TASK", "candidate_path", "runner task variant must declare candidate_path")
    if candidate_relative not in task["candidate_edit_allowlist"]:
        raise RunnerError("AX-BENCH-RUNNER-FORBIDDEN-FILE", "candidate_path", "candidate path is not present in the edit allowlist")

    starter = _safe_file(task_root, variant["starter_path"], "starter_path").read_bytes()
    if adapter == "reference":
        selected = variant["reference_solution_path"]
    else:
        wrong = variant["seeded_wrong_paths"]
        if wrong_index < 0 or wrong_index >= len(wrong):
            raise RunnerError("AX-BENCH-RUNNER-INVALID-TASK", "wrong_index", f"seeded-wrong index {wrong_index} is outside 0..{len(wrong) - 1}")
        selected = wrong[wrong_index]
    candidate = _safe_file(task_root, selected, "selected_candidate").read_bytes()
    budgets = task["budgets"]
    changed_lines = _changed_lines(starter, candidate)
    if len(candidate) > budgets["max_candidate_bytes"]:
        raise RunnerError("AX-BENCH-RUNNER-BUDGET", "candidate", "candidate byte budget exceeded")
    if changed_lines > budgets["max_changed_lines"]:
        raise RunnerError("AX-BENCH-RUNNER-BUDGET", "candidate", "changed-line budget exceeded")
    if budgets["max_candidate_files"] < 1:
        raise RunnerError("AX-BENCH-RUNNER-BUDGET", "candidate", "candidate file budget is zero")

    output_directory = _prepare_output(output_directory, repository_root, task_root)
    raw_root = output_directory / "raw"
    canonical_root = output_directory / "canonical"
    try:
        raw_root.mkdir()
        canonical_root.mkdir()
        _write_payload(raw_root / "candidate.bin", candidate)
        _write_payload(canonical_root / "candidate.bin", candidate)
    except OSError as error:
        raise RunnerError("AX-BENCH-RUNNER-INVALID-PATH", "output_directory", f"cannot initialize output Evidence: {error}") from error

    run_id = f"conformance-{task['task_id']}-{language}-{adapter}-{wrong_index}"
    trace = _Trace(run_id, task["task_id"], language)
    trace.add("run_start", {"adapter": adapter, "trust_class": trust_class})
    trace.add("task_start", {"task_path": str(task_path), "task_sha256": sha256_file(task_path)})
    trace.add("attempt_start", {"attempt": 1})
    trace.add("raw_completion_stored", {"path": "candidate.bin", "sha256": sha256_bytes(candidate)})

    started_at = _utc_now()
    started = time.monotonic()
    command_refs: list[dict[str, str]] = []
    outcomes: dict[str, bool | None] = {
        "extraction_success": True,
        "parse_success": None,
        "compile_success": None,
        "public_test_success": None,
        "acceptance_test_success": None,
        "security_success": None,
        "full_success": False,
    }
    failure: str | None = None
    feedback_bytes = 0
    command_schema = _schema(repository_root, "command-record.schema.json")
    trace_schema = _schema(repository_root, "trace-event.schema.json")
    attempt_schema = _schema(repository_root, "attempt.schema.json")
    report_schema = _schema(repository_root, "conformance-report.schema.json")
    manifest_schema = _schema(repository_root, "bundle-manifest.schema.json")

    with tempfile.TemporaryDirectory(prefix="axiom-bench-") as directory:
        workspace = Path(directory).resolve()
        candidate_path = _workspace_file(workspace, candidate_relative, "candidate_path")
        try:
            candidate_path.parent.mkdir(parents=True, exist_ok=True)
            candidate_path.write_bytes(starter)
            candidate_path.write_bytes(candidate)
        except OSError as error:
            raise RunnerError("AX-BENCH-RUNNER-INVALID-PATH", "candidate_path", f"cannot initialize candidate workspace: {error}") from error
        trace.add("file_mutation", {"path": str(candidate_path), "bytes": len(candidate), "changed_lines": changed_lines})
        environment = minimal_environment(workspace)

        for index, (phase, command_field, phase_failure) in enumerate(_PHASES, start=1):
            command = variant[command_field]
            if phase == "security_test" and not command:
                outcomes["security_success"] = True
                continue
            remaining = budgets["task_timeout_seconds"] - (time.monotonic() - started)
            if remaining <= 0:
                failure = "timeout"
                trace.add("timeout", {"scope": "task", "phase": phase})
                break
            if len(command_refs) >= budgets["max_compiler_invocations"]:
                failure = "resource_limit"
                trace.add("budget_exhausted", {"budget": "max_compiler_invocations", "phase": phase})
                break

            argv = expand_command(command, workspace=workspace, task_root=task_root, candidate=candidate_path, language=language)
            command_id = f"c{index:02d}.{phase.replace('_', '-')}"
            trace.add("command_start", {"command_id": command_id, "phase": phase, "argv": argv})
            start_failed = False
            try:
                execution = execute_bounded(
                    argv,
                    cwd=workspace,
                    environment=environment,
                    timeout_seconds=min(budgets["command_timeout_seconds"], max(1, math.ceil(remaining))),
                    max_output_bytes=budgets["max_output_bytes"],
                )
            except (OSError, ValueError) as error:
                execution = _not_started(argv, workspace, environment, error)
                start_failed = True

            canonical_stdout = canonical_stream_bytes(execution.stdout, workspace, task_root)
            canonical_stderr = canonical_stream_bytes(execution.stderr, workspace, task_root)
            stdout_path = f"stdout/{command_id}.bin"
            stderr_path = f"stderr/{command_id}.bin"
            try:
                _write_payload(raw_root / stdout_path, execution.stdout)
                _write_payload(raw_root / stderr_path, execution.stderr)
                _write_payload(canonical_root / stdout_path, canonical_stdout)
                _write_payload(canonical_root / stderr_path, canonical_stderr)
            except OSError as error:
                raise RunnerError("AX-BENCH-RUNNER-INVALID-PATH", "output_directory", f"cannot retain command Evidence: {error}") from error
            feedback_bytes += len(canonical_stdout) + len(canonical_stderr)

            raw_record = _command_record(command_id, phase, execution, stdout_path, stderr_path)
            canonical_record = canonical_command_record(
                raw_record,
                workspace,
                task_root,
                stdout=canonical_stdout,
                stderr=canonical_stderr,
            )
            _require_valid(raw_record, command_schema, f"command.{command_id}.raw")
            _require_valid(canonical_record, command_schema, f"command.{command_id}.canonical")
            raw_record_path = raw_root / "commands" / f"{command_id}.json"
            canonical_record_path = canonical_root / "commands" / f"{command_id}.json"
            write_json(raw_record_path, raw_record)
            write_json(canonical_record_path, canonical_record)
            command_refs.append({"phase": phase, "path": f"commands/{command_id}.json", "sha256": sha256_file(canonical_record_path)})
            trace.add(
                "command_finish",
                {
                    "command_id": command_id,
                    "return_code": execution.return_code,
                    "timed_out": execution.timed_out,
                    "output_limited": execution.output_limited,
                    "termination": execution.termination,
                },
            )

            if start_failed:
                failure = "runner_error"
            elif execution.timed_out or time.monotonic() - started > budgets["task_timeout_seconds"]:
                failure = "timeout"
            elif execution.output_limited:
                failure = "resource_limit"
            elif feedback_bytes > budgets["max_feedback_bytes"]:
                failure = "resource_limit"
                trace.add("budget_exhausted", {"budget": "max_feedback_bytes", "actual": feedback_bytes, "limit": budgets["max_feedback_bytes"]})
            elif execution.return_code != 0:
                failure = phase_failure
            success = failure is None
            _update_outcome(outcomes, phase, success)
            trace.add("check_result", {"phase": phase, "success": success, "failure_reason": failure})
            if failure is not None:
                break

        if outcomes["security_success"] is None and failure is None:
            outcomes["security_success"] = True
        outcomes["full_success"] = all(
            outcomes[field] is True
            for field in ("extraction_success", "compile_success", "public_test_success", "acceptance_test_success", "security_success")
        )
        expected_failure = None if adapter == "reference" else task["acceptance"]["required_failure_for_seeded_wrong"]
        expected_success = adapter == "reference"
        conformance_passed = outcomes["full_success"] is expected_success and failure == expected_failure
        findings = [] if conformance_passed else [
            RunnerFinding(
                "AX-BENCH-RUNNER-CONFORMANCE",
                "conformance",
                f"expected success={expected_success}, failure={expected_failure!r}; got success={outcomes['full_success']}, failure={failure!r}",
            )
        ]
        trace.add("score_decision", {"full_success": outcomes["full_success"], "failure_reason": failure, "conformance_passed": conformance_passed})
        trace.add("attempt_finish", {"attempt": 1})
        trace.add("task_finish", {"conformance_passed": conformance_passed})
        trace.add("run_finish", {"conformance_passed": conformance_passed})
        trace_sha = _write_trace(raw_root / "trace.jsonl", canonical_root / "trace.jsonl", trace.events, workspace, task_root, trace_schema)

        finished_at = _utc_now()
        attempt = {
            "document_kind": "axiom.bench.attempt",
            "schema_version": "0.1.0",
            "run_id": run_id,
            "task_id": task["task_id"],
            "language": language,
            "lane": "language_only",
            "adapter": adapter,
            "trust_class": trust_class,
            "attempt_number": 1,
            "started_at": started_at,
            "finished_at": finished_at,
            "raw_completion_path": "candidate.bin",
            "raw_completion_sha256": sha256_bytes(candidate),
            "extracted_artifact_path": "candidate.bin",
            "extracted_artifact_sha256": sha256_bytes(candidate),
            "trace_path": "trace.jsonl",
            "trace_sha256": trace_sha,
            "command_records": command_refs,
            "outcomes": outcomes,
            "failure_reason": failure,
            "budgets": budgets,
            "usage": {
                "input_tokens": None,
                "output_tokens": None,
                "token_source": None,
                "tool_calls": 0,
                "compiler_invocations": len(command_refs),
                "wall_clock_ms": max(0, int(round((time.monotonic() - started) * 1000))),
                "feedback_bytes": feedback_bytes,
            },
            "mutations": {
                "files_read": [],
                "files_changed": [candidate_relative],
                "changed_lines": changed_lines,
                "patch_bytes": len(candidate),
                "forbidden_paths_attempted": [],
            },
            "evidence_complete": True,
        }
        canonical_attempt_value = canonical_attempt(attempt)
        _require_valid(attempt, attempt_schema, "attempt.raw")
        _require_valid(canonical_attempt_value, attempt_schema, "attempt.canonical")
        write_json(raw_root / "attempt.json", attempt)
        write_json(canonical_root / "attempt.json", canonical_attempt_value)
        attempt_sha = sha256_file(canonical_root / "attempt.json")

        report = {
            "document_kind": "axiom.bench.conformance-report",
            "schema_version": "0.1.0",
            "task_id": task["task_id"],
            "task_sha256": sha256_file(task_path),
            "language": language,
            "adapter": adapter,
            "trust_class": trust_class,
            "expected_outcome": {"full_success": expected_success, "failure_reason": expected_failure},
            "actual_full_success": outcomes["full_success"],
            "actual_failure_reason": failure,
            "conformance_passed": conformance_passed,
            "attempt_path": "attempt.json",
            "attempt_sha256": attempt_sha,
            "canonical_trace_path": "trace.jsonl",
            "canonical_trace_sha256": trace_sha,
            "canonical_bundle_sha256": None,
            "findings": [item.as_dict() for item in findings],
        }
        _require_valid(report, report_schema, "conformance-report")
        write_json(canonical_root / "conformance-report.json", report)
        write_json(raw_root / "conformance-report.json", report)
        manifest = build_manifest(canonical_root, task_id=task["task_id"], language=language, adapter=adapter)
        _require_valid(manifest, manifest_schema, "bundle-manifest")

    bundle_path = output_directory / "AXIOM_BENCH_CONFORMANCE.zip"
    bundle_sha = write_deterministic_zip(canonical_root, bundle_path)
    external_report = json.loads(json.dumps(report))
    external_report["canonical_bundle_sha256"] = bundle_sha
    _require_valid(external_report, report_schema, "external-conformance-report")
    write_json(output_directory / "conformance-report.json", external_report)
    return ConformanceResult(
        output_directory=output_directory,
        bundle_path=bundle_path,
        bundle_sha256=bundle_sha,
        conformance_passed=conformance_passed,
        full_success=bool(outcomes["full_success"]),
        failure_reason=failure,
        report=external_report,
    )
