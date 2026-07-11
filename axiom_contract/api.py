from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any

from .checker import check_project_contract as _check_project_contract


def _pinned_dependency_names(root: Path) -> list[str]:
    path = root / "requirements-proof.txt"
    names: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ValueError(f"proof dependency is not exactly pinned: {line}")
        name, pinned_version = line.split("==", 1)
        if not name or not pinned_version:
            raise ValueError(f"invalid proof dependency pin: {line}")
        names.append(name)
    return sorted(names)


def _installed_dependency_versions(root: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in _pinned_dependency_names(root):
        try:
            versions[name] = package_version(name)
        except PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def check_project_contract(
    root: Path,
    contract_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    resolved_root = root.resolve()
    result = _check_project_contract(resolved_root, contract_path, schema_path)
    result["dependencies"] = _installed_dependency_versions(resolved_root)
    missing = sorted(name for name, value in result["dependencies"].items() if value == "not-installed")
    if missing and result["status"] == "passed":
        result["status"] = "failed"
        result["exit_code"] = 2
        result["findings"] = [
            {
                "code": "AX-CONTRACT-0006",
                "path": "requirements-proof.txt",
                "message": f"pinned proof dependencies are not installed: {', '.join(missing)}",
            }
        ]
        result["counts"]["findings"] = 1
    return result
