from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .bundle import safe_join, sha256_file
from .contract import validate_document

BENCHMARK_CONTRACT_PATH = Path("benchmarks/contracts/0.1.0/contract.json")
REGISTRY_PATH = Path("benchmarks/contracts/0.1.0/trusted-tasks.json")
REGISTRY_SCHEMA_PATH = Path("benchmarks/schemas/0.1.0/trusted-task-registry.schema.json")
TASK_SCHEMA_PATH = Path("benchmarks/schemas/0.1.0/task.schema.json")


class AuthorityError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


@dataclass(frozen=True)
class TrustedTaskAuthority:
    task_id: str
    task_path: Path
    task_sha256: str
    task: dict[str, Any]


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-MISSING",
            label,
            f"missing authority JSON: {path}",
        ) from error
    except (OSError, UnicodeError) as error:
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-INVALID",
            label,
            f"cannot read authority JSON: {error}",
        ) from error
    except json.JSONDecodeError as error:
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-INVALID",
            label,
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}",
        ) from error
    if not isinstance(value, dict):
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-INVALID",
            label,
            "authority JSON root must be an object",
        )
    return value


def _reject_symlinks(root: Path, path: Path, label: str) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise AuthorityError(
                "AX-BENCH-AUTHORITY-SYMLINK",
                label,
                f"symbolic links are forbidden in trusted task authority: {path}",
            )
        if current == root or current == current.parent:
            break
        current = current.parent


def _schema(root: Path, relative: Path, label: str) -> dict[str, Any]:
    path = root / relative
    _reject_symlinks(root, path, label)
    return _load_json(path, label)


def _registry_path_from_contract(root: Path) -> tuple[Path, str]:
    contract_path = root / BENCHMARK_CONTRACT_PATH
    _reject_symlinks(root, contract_path, BENCHMARK_CONTRACT_PATH.as_posix())
    contract = _load_json(contract_path, BENCHMARK_CONTRACT_PATH.as_posix())
    declared = contract.get("trusted_task_registry_path")
    if declared != REGISTRY_PATH.as_posix():
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-CONTRACT",
            f"{BENCHMARK_CONTRACT_PATH.as_posix()}:$.trusted_task_registry_path",
            f"benchmark contract must declare {REGISTRY_PATH.as_posix()!r}; got {declared!r}",
        )
    try:
        registry_path = safe_join(root, declared)
    except (TypeError, ValueError) as error:
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-INVALID-PATH",
            f"{BENCHMARK_CONTRACT_PATH.as_posix()}:$.trusted_task_registry_path",
            str(error),
        ) from error
    _reject_symlinks(root, registry_path, BENCHMARK_CONTRACT_PATH.as_posix())
    return registry_path, declared


def _registered_tasks(repository_root: Path) -> tuple[TrustedTaskAuthority, ...]:
    root = repository_root.resolve()
    registry_path, registry_label = _registry_path_from_contract(root)
    registry = _load_json(registry_path, registry_label)
    registry_schema = _schema(root, REGISTRY_SCHEMA_PATH, REGISTRY_SCHEMA_PATH.as_posix())
    findings = validate_document(registry, registry_schema, label=registry_label)
    if findings:
        first = findings[0]
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-INVALID",
            first.path,
            first.message,
        )
    if registry.get("$schema") != "../../schemas/0.1.0/trusted-task-registry.schema.json":
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-INVALID",
            f"{registry_label}:$.$schema",
            "trusted task registry must reference the canonical local schema",
        )

    task_schema = _schema(root, TASK_SCHEMA_PATH, TASK_SCHEMA_PATH.as_posix())
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    authorities: list[TrustedTaskAuthority] = []
    for index, entry in enumerate(registry["tasks"]):
        task_id = entry["task_id"]
        relative = entry["task_path"]
        label = f"{registry_label}:$.tasks[{index}].task_path"
        if task_id in seen_ids:
            raise AuthorityError(
                "AX-BENCH-AUTHORITY-DUPLICATE",
                f"{registry_label}:$.tasks[{index}].task_id",
                f"duplicate trusted task id: {task_id}",
            )
        if relative in seen_paths:
            raise AuthorityError(
                "AX-BENCH-AUTHORITY-DUPLICATE",
                label,
                f"duplicate trusted task path: {relative}",
            )
        seen_ids.add(task_id)
        seen_paths.add(relative)
        try:
            task_path = safe_join(root, relative)
        except ValueError as error:
            raise AuthorityError(
                "AX-BENCH-AUTHORITY-INVALID-PATH",
                label,
                str(error),
            ) from error
        _reject_symlinks(root, task_path, label)
        if not task_path.is_file():
            raise AuthorityError(
                "AX-BENCH-AUTHORITY-MISSING",
                label,
                f"registered trusted task is missing: {relative}",
            )
        task = _load_json(task_path, relative)
        task_findings = validate_document(task, task_schema, label=relative)
        if task_findings:
            first = task_findings[0]
            raise AuthorityError(
                "AX-BENCH-AUTHORITY-INVALID-TASK",
                first.path,
                first.message,
            )
        if task.get("task_id") != task_id:
            raise AuthorityError(
                "AX-BENCH-AUTHORITY-TASK-ID",
                label,
                f"registry task id {task_id!r} disagrees with task document {task.get('task_id')!r}",
            )
        authorities.append(
            TrustedTaskAuthority(
                task_id=task_id,
                task_path=task_path,
                task_sha256=sha256_file(task_path),
                task=task,
            )
        )
    return tuple(authorities)


def resolve_trusted_task(
    repository_root: Path,
    *,
    task_path: Path | None = None,
    task_id: str | None = None,
) -> TrustedTaskAuthority:
    if (task_path is None) == (task_id is None):
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-LOOKUP",
            "trusted-task",
            "exactly one of task_path or task_id is required",
        )
    authorities = _registered_tasks(repository_root)
    if task_path is not None:
        requested = task_path.resolve()
        for authority in authorities:
            if authority.task_path.resolve() == requested:
                return authority
        raise AuthorityError(
            "AX-BENCH-AUTHORITY-UNREGISTERED",
            task_path.as_posix(),
            "task is not registered for trusted local execution",
        )
    assert task_id is not None
    for authority in authorities:
        if authority.task_id == task_id:
            return authority
    raise AuthorityError(
        "AX-BENCH-AUTHORITY-UNREGISTERED",
        task_id,
        "task id is not registered in repository authority",
    )


def expected_trust_class(adapter: str) -> str:
    if adapter == "reference":
        return "trusted_reference"
    if adapter == "seeded_wrong":
        return "trusted_seeded_wrong"
    raise AuthorityError(
        "AX-BENCH-AUTHORITY-ADAPTER",
        "adapter",
        f"unsupported trusted conformance adapter: {adapter!r}",
    )


def expected_outcome(authority: TrustedTaskAuthority, adapter: str) -> dict[str, object]:
    if adapter == "reference":
        return {"full_success": True, "failure_reason": None}
    if adapter == "seeded_wrong":
        return {
            "full_success": False,
            "failure_reason": authority.task["acceptance"]["required_failure_for_seeded_wrong"],
        }
    raise AuthorityError(
        "AX-BENCH-AUTHORITY-ADAPTER",
        "adapter",
        f"unsupported trusted conformance adapter: {adapter!r}",
    )
