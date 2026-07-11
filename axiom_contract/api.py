from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Any

from .checker import check_project_contract as _check_project_contract


def _pinned_dependencies(root: Path) -> dict[str, str]:
    path = root / "requirements-proof.txt"
    dependencies: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ValueError(f"proof dependency is not exactly pinned: {line}")
        name, pinned_version = line.split("==", 1)
        if not name or not pinned_version:
            raise ValueError(f"invalid proof dependency pin: {line}")
        if name in dependencies:
            raise ValueError(f"duplicate proof dependency pin: {name}")
        dependencies[name] = pinned_version
    if not dependencies:
        raise ValueError("requirements-proof.txt contains no proof dependencies")
    return dict(sorted(dependencies.items()))


def _installed_dependency_versions(pins: dict[str, str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in pins:
        try:
            versions[name] = package_version(name)
        except PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def _append_findings(result: dict[str, Any], findings: list[dict[str, str]]) -> None:
    if not findings:
        return
    result["status"] = "failed"
    result["exit_code"] = 2
    result["findings"] = sorted(
        [*result["findings"], *findings],
        key=lambda item: (item["code"], item["path"], item["message"]),
    )
    result["counts"]["findings"] = len(result["findings"])


def check_project_contract(
    root: Path,
    contract_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    resolved_root = root.resolve()
    result = _check_project_contract(resolved_root, contract_path, schema_path)

    try:
        pins = _pinned_dependencies(resolved_root)
    except FileNotFoundError:
        result["dependency_pins"] = {}
        result["dependencies"] = {}
        _append_findings(
            result,
            [
                {
                    "code": "AX-CONTRACT-0008",
                    "path": "requirements-proof.txt",
                    "message": "missing exact proof dependency file",
                }
            ],
        )
        return result
    except (OSError, ValueError) as error:
        result["dependency_pins"] = {}
        result["dependencies"] = {}
        _append_findings(
            result,
            [
                {
                    "code": "AX-CONTRACT-0009",
                    "path": "requirements-proof.txt",
                    "message": f"invalid exact proof dependency file: {error}",
                }
            ],
        )
        return result

    installed = _installed_dependency_versions(pins)
    result["dependency_pins"] = pins
    result["dependencies"] = installed

    dependency_findings: list[dict[str, str]] = []
    for name, expected in pins.items():
        actual = installed[name]
        if actual == "not-installed":
            dependency_findings.append(
                {
                    "code": "AX-CONTRACT-0006",
                    "path": f"requirements-proof.txt:{name}",
                    "message": f"pinned proof dependency is not installed: {name}=={expected}",
                }
            )
        elif actual != expected:
            dependency_findings.append(
                {
                    "code": "AX-CONTRACT-0007",
                    "path": f"requirements-proof.txt:{name}",
                    "message": f"proof dependency version mismatch: expected {name}=={expected}, installed {actual}",
                }
            )

    _append_findings(result, dependency_findings)
    return result
