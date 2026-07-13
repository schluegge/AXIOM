from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from pathlib import PurePosixPath
from typing import Any

from .publisher_core import (
    ArtifactLimits,
    PublicationBundle,
    PublicationIdentity,
    PublicationRejected,
    _SHA256,
    _SHA40,
    _REPOSITORY,
    _read_json_object,
    _reject,
    _require_int,
    _require_str,
)

_ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_REQUIRED_ARCHIVE_PATHS = {
    "publication-envelope.json",
    "review-report.json",
    "review-summary.md",
}

def _is_safe_archive_path(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name:
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts:
        return False
    return all(part not in {"", ".", ".."} for part in path.parts)

def _validate_limits(limits: ArtifactLimits) -> None:
    for name in (
        "max_archive_bytes",
        "max_entries",
        "max_file_bytes",
        "max_total_uncompressed_bytes",
        "max_report_bytes",
        "max_summary_bytes",
        "max_comment_bytes",
    ):
        _reject(getattr(limits, name) < 1, f"{name} must be positive")
    _reject(limits.max_compression_ratio < 1, "max_compression_ratio must be >= 1")
    _reject(limits.max_report_bytes > limits.max_file_bytes, "report limit exceeds file limit")
    _reject(limits.max_summary_bytes > limits.max_file_bytes, "summary limit exceeds file limit")


def _read_archive_entries(archive_bytes: bytes, limits: ArtifactLimits) -> dict[str, bytes]:
    _validate_limits(limits)
    _reject(len(archive_bytes) > limits.max_archive_bytes, "archive exceeds byte limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes), "r")
    except (zipfile.BadZipFile, OSError) as error:
        raise PublicationRejected("artifact is not a valid ZIP archive") from error

    entries: dict[str, bytes] = {}
    total_uncompressed = 0
    try:
        infos = archive.infolist()
        _reject(len(infos) > limits.max_entries, "archive entry count exceeds limit")
        for info in infos:
            name = info.filename
            _reject(not _is_safe_archive_path(name), f"unsafe archive path: {name!r}")
            _reject(name in entries, f"duplicate archive entry: {name}")
            _reject(info.is_dir(), f"directory archive entry is not allowed: {name}")
            _reject(bool(info.flag_bits & 0x1), f"encrypted archive entry is not allowed: {name}")
            _reject(info.compress_type not in _ALLOWED_COMPRESSION, f"unsupported compression method: {name}")

            mode = (info.external_attr >> 16) & 0xFFFF
            _reject(mode != 0 and stat.S_ISLNK(mode), f"symbolic-link archive entry is not allowed: {name}")
            if name == "review-report.json":
                _reject(info.file_size > limits.max_report_bytes, "report exceeds byte limit")
            elif name == "review-summary.md":
                _reject(info.file_size > limits.max_summary_bytes, "summary exceeds byte limit")
            else:
                _reject(info.file_size > limits.max_file_bytes, f"archive file exceeds byte limit: {name}")
            total_uncompressed += info.file_size
            _reject(
                total_uncompressed > limits.max_total_uncompressed_bytes,
                "archive uncompressed size exceeds limit",
            )
            compressed_size = max(info.compress_size, 1)
            ratio = info.file_size / compressed_size
            _reject(
                ratio > limits.max_compression_ratio,
                f"archive compression ratio exceeds limit: {name}",
            )
            try:
                payload = archive.read(info)
            except (RuntimeError, OSError, zipfile.BadZipFile) as error:
                raise PublicationRejected(f"archive entry could not be read: {name}") from error
            _reject(len(payload) != info.file_size, f"archive entry size mismatch: {name}")
            entries[name] = payload
    finally:
        archive.close()

    missing = sorted(_REQUIRED_ARCHIVE_PATHS - entries.keys())
    _reject(bool(missing), f"archive is missing required entries: {', '.join(missing)}")
    return entries


def _validate_envelope(
    envelope: dict[str, Any], expected: PublicationIdentity
) -> tuple[str, str, int, int, str, str]:
    allowed = {
        "document_kind",
        "schema_version",
        "repository",
        "pull_request_number",
        "base_sha",
        "reviewed_head_sha",
        "workflow_run_id",
        "workflow_run_attempt",
        "workflow_name",
        "artifact_name",
        "report_path",
        "report_bytes",
        "report_sha256",
        "summary_path",
        "summary_bytes",
        "summary_sha256",
    }
    unknown = sorted(set(envelope) - allowed)
    missing = sorted(allowed - set(envelope))
    _reject(bool(unknown), f"publication envelope contains unknown fields: {', '.join(unknown)}")
    _reject(bool(missing), f"publication envelope is missing fields: {', '.join(missing)}")
    _reject(
        envelope["document_kind"] != "axiom.automated-review.publication-envelope",
        "publication envelope document kind mismatch",
    )
    _reject(envelope["schema_version"] != "0.1.0", "publication envelope schema version mismatch")

    repository = _require_str(envelope["repository"], "envelope repository", pattern=_REPOSITORY)
    pull_request_number = _require_int(envelope["pull_request_number"], "envelope pull request number")
    base_sha = _require_str(envelope["base_sha"], "envelope base SHA", pattern=_SHA40)
    reviewed_head_sha = _require_str(
        envelope["reviewed_head_sha"], "envelope reviewed head SHA", pattern=_SHA40
    )
    workflow_run_id = _require_int(envelope["workflow_run_id"], "envelope workflow run id")
    workflow_run_attempt = _require_int(
        envelope["workflow_run_attempt"], "envelope workflow run attempt"
    )
    workflow_name = _require_str(envelope["workflow_name"], "envelope workflow name")
    artifact_name = _require_str(envelope["artifact_name"], "envelope artifact name")

    actual_identity = (
        repository,
        pull_request_number,
        base_sha,
        reviewed_head_sha,
        workflow_run_id,
        workflow_run_attempt,
        workflow_name,
        artifact_name,
    )
    expected_identity = (
        expected.repository,
        expected.pull_request_number,
        expected.base_sha,
        expected.reviewed_head_sha,
        expected.workflow_run_id,
        expected.workflow_run_attempt,
        expected.workflow_name,
        expected.artifact_name,
    )
    _reject(actual_identity != expected_identity, "envelope identity mismatch")

    report_path = _require_str(envelope["report_path"], "envelope report path")
    summary_path = _require_str(envelope["summary_path"], "envelope summary path")
    _reject(report_path != "review-report.json", "unexpected report path")
    _reject(summary_path != "review-summary.md", "unexpected summary path")
    report_bytes = _require_int(envelope["report_bytes"], "envelope report bytes", minimum=0)
    summary_bytes = _require_int(envelope["summary_bytes"], "envelope summary bytes", minimum=0)
    report_sha256 = _require_str(
        envelope["report_sha256"], "envelope report digest", pattern=_SHA256
    )
    summary_sha256 = _require_str(
        envelope["summary_sha256"], "envelope summary digest", pattern=_SHA256
    )
    return report_path, summary_path, report_bytes, summary_bytes, report_sha256, summary_sha256


def inspect_publication_archive(
    archive_bytes: bytes,
    expected_identity: PublicationIdentity,
    limits: ArtifactLimits,
) -> PublicationBundle:
    """Inspect a raw artifact ZIP in memory without extracting untrusted paths."""

    entries = _read_archive_entries(archive_bytes, limits)
    envelope = _read_json_object(entries["publication-envelope.json"], "publication envelope")
    (
        report_path,
        summary_path,
        declared_report_bytes,
        declared_summary_bytes,
        report_sha256,
        summary_sha256,
    ) = _validate_envelope(envelope, expected_identity)

    report_payload = entries[report_path]
    summary_payload = entries[summary_path]
    _reject(len(report_payload) > limits.max_report_bytes, "report exceeds byte limit")
    _reject(len(summary_payload) > limits.max_summary_bytes, "summary exceeds byte limit")
    _reject(len(report_payload) != declared_report_bytes, "report byte count mismatch")
    _reject(len(summary_payload) != declared_summary_bytes, "summary byte count mismatch")
    _reject(
        hashlib.sha256(report_payload).hexdigest() != report_sha256,
        "report digest mismatch",
    )
    _reject(
        hashlib.sha256(summary_payload).hexdigest() != summary_sha256,
        "summary digest mismatch",
    )

    report = _read_json_object(report_payload, "review report")
    report_identity = (
        report.get("repository"),
        report.get("pull_request_number"),
        report.get("base_sha"),
        report.get("reviewed_head_sha"),
    )
    expected_report_identity = (
        expected_identity.repository,
        expected_identity.pull_request_number,
        expected_identity.base_sha,
        expected_identity.reviewed_head_sha,
    )
    _reject(report_identity != expected_report_identity, "review report identity mismatch")
    try:
        summary = summary_payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PublicationRejected("review summary is not UTF-8") from error

    return PublicationBundle(
        identity=expected_identity,
        envelope=envelope,
        report=report,
        report_bytes=report_payload,
        summary=summary,
        summary_bytes=summary_payload,
    )
