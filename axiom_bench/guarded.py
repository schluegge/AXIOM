from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from .authority import (
    AuthorityError,
    expected_outcome,
    expected_trust_class,
    resolve_trusted_task,
)
from .bundle import read_bounded_zip_entry, safe_zip_entries
from .replay import replay_conformance as _replay_conformance
from .runner import ConformanceResult, RunnerError, run_conformance as _run_conformance


def run_conformance(
    repository_root: Path,
    task_path: Path,
    *,
    language: str,
    adapter: str,
    output_directory: Path,
    wrong_index: int = 0,
) -> ConformanceResult:
    try:
        authority = resolve_trusted_task(repository_root, task_path=task_path)
    except AuthorityError as error:
        code = (
            "AX-BENCH-RUNNER-UNTRUSTED-TASK"
            if error.code == "AX-BENCH-AUTHORITY-UNREGISTERED"
            else "AX-BENCH-RUNNER-AUTHORITY"
        )
        raise RunnerError(code, error.path, error.message) from error
    return _run_conformance(
        repository_root,
        authority.task_path,
        language=language,  # type: ignore[arg-type]
        adapter=adapter,  # type: ignore[arg-type]
        output_directory=output_directory,
        wrong_index=wrong_index,
    )


def _bundle_documents(bundle_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(bundle_path, "r") as archive:
        entries = {entry.filename: entry for entry in safe_zip_entries(archive)}
        total = 0
        values: dict[str, dict[str, Any]] = {}
        for name in ("attempt.json", "conformance-report.json"):
            entry = entries.get(name)
            if entry is None:
                raise ValueError(f"bundle authority document is missing: {name}")
            payload, total = read_bounded_zip_entry(archive, entry, total_bytes=total)
            value = json.loads(payload.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError(f"bundle authority document root must be an object: {name}")
            values[name] = value
    return values["attempt.json"], values["conformance-report.json"]


def _authority_finding(path: str, message: str) -> dict[str, str]:
    return {
        "code": "AX-BENCH-REPLAY-AUTHORITY",
        "path": path,
        "message": message,
    }


def replay_conformance(repository_root: Path, bundle_path: Path) -> dict[str, Any]:
    result = _replay_conformance(repository_root, bundle_path)
    if result.get("status") != "passed":
        return result

    findings: list[dict[str, str]] = []
    try:
        attempt, report = _bundle_documents(bundle_path.resolve())
        authority = resolve_trusted_task(repository_root, task_id=str(report["task_id"]))
        adapter = str(report["adapter"])
        language = str(report["language"])
        authoritative_outcome = expected_outcome(authority, adapter)
        authoritative_trust = expected_trust_class(adapter)

        if report.get("task_sha256") != authority.task_sha256:
            findings.append(
                _authority_finding(
                    "conformance-report.task_sha256",
                    "bundle task hash differs from the registered repository task",
                )
            )
        if language not in authority.task["variants"]:
            findings.append(
                _authority_finding(
                    "conformance-report.language",
                    f"registered task has no authoritative {language!r} variant",
                )
            )
        if report.get("expected_outcome") != authoritative_outcome:
            findings.append(
                _authority_finding(
                    "conformance-report.expected_outcome",
                    "bundle expected outcome differs from adapter and registered task authority",
                )
            )
        if report.get("trust_class") != authoritative_trust:
            findings.append(
                _authority_finding(
                    "conformance-report.trust_class",
                    "report trust class differs from adapter authority",
                )
            )
        if attempt.get("trust_class") != authoritative_trust:
            findings.append(
                _authority_finding(
                    "attempt.trust_class",
                    "attempt trust class differs from adapter authority",
                )
            )
        if attempt.get("task_id") != authority.task_id:
            findings.append(
                _authority_finding(
                    "attempt.task_id",
                    "attempt task id differs from registered task authority",
                )
            )
    except (
        AuthorityError,
        FileNotFoundError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        UnicodeError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as error:
        path = error.path if isinstance(error, AuthorityError) else "bundle"
        message = error.message if isinstance(error, AuthorityError) else str(error)
        findings.append(_authority_finding(path, message))

    if findings:
        result["status"] = "failed"
        result["recomputed_conformance_passed"] = False
        result["findings"] = sorted(
            [*result.get("findings", []), *findings],
            key=lambda item: (item["code"], item["path"], item["message"]),
        )
    return result
