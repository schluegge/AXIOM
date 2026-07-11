from __future__ import annotations

import json
import os
import stat
import unicodedata
import zipfile
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

FIXED_TIME = (2026, 7, 11, 0, 0, 0)
EPOCH_TEXT = "1970-01-01T00:00:00Z"
MAX_REPLAY_ENTRIES = 1000
MAX_REPLAY_ENTRY_BYTES = 10 * 1024 * 1024
MAX_REPLAY_TOTAL_BYTES = 50 * 1024 * 1024


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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
    return sha256_bytes(payload.encode("utf-8"))


def safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError("path must be a non-empty string")
    if "\x00" in value or "\\" in value:
        raise ValueError("path must be a non-empty POSIX path")
    path = PurePosixPath(value)
    if path.as_posix() != value:
        raise ValueError("path must use exact normalized POSIX spelling")
    if path.is_absolute() or not path.parts:
        raise ValueError("path must be normalized and repository-relative")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("path must be normalized and repository-relative")
    if any(":" in part for part in path.parts):
        raise ValueError("path may not contain a Windows drive or alternate-stream separator")
    return path


def safe_join(root: Path, value: str) -> Path:
    relative = safe_relative_path(value)
    resolved_root = root.resolve()
    candidate = resolved_root.joinpath(*relative.parts)
    try:
        candidate.resolve().relative_to(resolved_root)
    except ValueError as error:
        raise ValueError("path escapes declared root") from error
    return candidate


def reject_symlink(path: Path) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise ValueError(f"symbolic link is forbidden: {path}")
        if current == current.parent:
            break
        current = current.parent


def _root_text_replacements(workspace: Path, task_root: Path) -> list[tuple[str, str]]:
    replacements: set[tuple[str, str]] = set()
    for root, placeholder in ((workspace, "{workspace}"), (task_root, "{task_root}")):
        native = str(root)
        variants = {
            native,
            root.as_posix(),
            native.replace("\\", "/"),
            native.replace("/", "\\"),
        }
        replacements.update((variant, placeholder) for variant in variants if variant)
    return sorted(replacements, key=lambda item: len(item[0]), reverse=True)


def _replace_roots(value: str, workspace: Path, task_root: Path) -> str:
    result = value
    for source, replacement in _root_text_replacements(workspace, task_root):
        result = result.replace(source, replacement)
    return result.replace(os.sep, "/") if os.sep != "/" else result


def canonical_stream_bytes(value: bytes, workspace: Path, task_root: Path) -> bytes:
    result = value
    for source, replacement in _root_text_replacements(workspace, task_root):
        result = result.replace(source.encode("utf-8"), replacement.encode("ascii"))
    return result


def canonical_command_record(
    record: dict[str, Any],
    workspace: Path,
    task_root: Path,
    *,
    stdout: bytes | None = None,
    stderr: bytes | None = None,
) -> dict[str, Any]:
    value = json.loads(json.dumps(record))
    value["started_at"] = EPOCH_TEXT
    value["finished_at"] = EPOCH_TEXT
    value["duration_ms"] = 0
    value["cwd"] = _replace_roots(str(value["cwd"]), workspace, task_root)
    value["argv"] = [
        _replace_roots(str(argument), workspace, task_root) for argument in value["argv"]
    ]
    value["environment"] = {
        key: _replace_roots(str(item), workspace, task_root)
        for key, item in sorted(value["environment"].items())
    }
    if stdout is not None:
        value["stdout_sha256"] = sha256_bytes(stdout)
        value["stdout_bytes"] = len(stdout)
    if stderr is not None:
        value["stderr_sha256"] = sha256_bytes(stderr)
        value["stderr_bytes"] = len(stderr)
    return value


def canonical_trace_event(event: dict[str, Any], workspace: Path, task_root: Path) -> dict[str, Any]:
    value = json.loads(json.dumps(event))
    value["timestamp"] = EPOCH_TEXT

    def normalize(item: Any) -> Any:
        if isinstance(item, str):
            return _replace_roots(item, workspace, task_root)
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in sorted(item.items())}
        if isinstance(item, list):
            return [normalize(child) for child in item]
        return item

    value["payload"] = normalize(value["payload"])
    return value


def canonical_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(attempt))
    value["started_at"] = EPOCH_TEXT
    value["finished_at"] = EPOCH_TEXT
    value["usage"]["wall_clock_ms"] = 0
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def build_manifest(
    canonical_root: Path,
    *,
    task_id: str,
    language: str,
    adapter: str,
) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in canonical_root.rglob("*") if item.is_file()):
        relative = path.relative_to(canonical_root).as_posix()
        if relative == "bundle-manifest.json":
            continue
        safe_relative_path(relative)
        files[relative] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    semantic_payload = {
        "bundle_kind": "trusted-conformance",
        "task_id": task_id,
        "language": language,
        "adapter": adapter,
        "files": files,
    }
    manifest = {
        "document_kind": "axiom.bench.bundle-manifest",
        "schema_version": "0.1.0",
        **semantic_payload,
        "semantic_sha256": semantic_sha256(semantic_payload),
    }
    write_json(canonical_root / "bundle-manifest.json", manifest)
    return manifest


def write_deterministic_zip(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            relative = path.relative_to(source).as_posix()
            safe_relative_path(relative)
            info = zipfile.ZipInfo(relative, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(destination, "r") as archive:
        if archive.testzip() is not None:
            raise ValueError("deterministic ZIP CRC verification failed")
    return sha256_file(destination)


def safe_zip_entries(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    entries = archive.infolist()
    if len(entries) > MAX_REPLAY_ENTRIES:
        raise ValueError("ZIP entry count exceeds replay limit")
    names: set[str] = set()
    portable_names: set[str] = set()
    declared_total = 0
    for entry in entries:
        if entry.is_dir():
            raise ValueError(f"ZIP directory entry is forbidden: {entry.filename}")
        path = safe_relative_path(entry.filename)
        if entry.filename in names:
            raise ValueError(f"duplicate ZIP path: {entry.filename}")
        names.add(entry.filename)
        portable = unicodedata.normalize("NFC", entry.filename).casefold()
        if portable in portable_names:
            raise ValueError(f"portable ZIP path collision: {entry.filename}")
        portable_names.add(portable)
        if entry.flag_bits & 0x1:
            raise ValueError(f"encrypted ZIP entry is forbidden: {entry.filename}")
        if entry.file_size > MAX_REPLAY_ENTRY_BYTES:
            raise ValueError(f"ZIP entry exceeds replay limit: {entry.filename}")
        declared_total += entry.file_size
        if declared_total > MAX_REPLAY_TOTAL_BYTES:
            raise ValueError("ZIP declared total size exceeds replay limit")
        mode = entry.external_attr >> 16
        if mode and stat.S_ISLNK(mode):
            raise ValueError(f"ZIP symbolic link is forbidden: {path}")
    return entries


def read_bounded_zip_entry(
    archive: zipfile.ZipFile,
    entry: zipfile.ZipInfo,
    *,
    total_bytes: int,
    max_entry_bytes: int = MAX_REPLAY_ENTRY_BYTES,
    max_total_bytes: int = MAX_REPLAY_TOTAL_BYTES,
    chunk_size: int = 64 * 1024,
) -> tuple[bytes, int]:
    if total_bytes < 0:
        raise ValueError("ZIP extracted byte count cannot be negative")
    if max_entry_bytes < 1 or max_total_bytes < 1 or chunk_size < 1:
        raise ValueError("ZIP extraction limits must be positive")
    payload = bytearray()
    with archive.open(entry, "r") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            next_entry_size = len(payload) + len(chunk)
            next_total = total_bytes + next_entry_size
            if next_entry_size > max_entry_bytes:
                raise ValueError(f"ZIP entry exceeds actual replay limit: {entry.filename}")
            if next_total > max_total_bytes:
                raise ValueError("ZIP actual total size exceeds replay limit")
            payload.extend(chunk)
    actual_size = len(payload)
    if actual_size != entry.file_size:
        raise ValueError(
            f"ZIP entry decompressed size differs from metadata: {entry.filename} "
            f"({actual_size} != {entry.file_size})"
        )
    return bytes(payload), total_bytes + actual_size
