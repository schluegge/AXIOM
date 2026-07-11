from __future__ import annotations

import hashlib
import json
import tempfile
import traceback
from pathlib import Path
from typing import Any, Callable

from axiom_proof.driver import compile_source

ROOT = Path.cwd()
OUTPUT = Path.cwd()
CHECKS: list[dict[str, Any]] = []
TEMP_SOURCES: list[tempfile.TemporaryDirectory[str]] = []

def configure(root: Path, output: Path) -> None:
    global ROOT, OUTPUT, CHECKS, TEMP_SOURCES
    ROOT = root.resolve()
    OUTPUT = output.resolve()
    CHECKS = []
    TEMP_SOURCES = []

def fixture(name: str) -> Path:
    return Path("examples") / name

def check(name: str, action: Callable[[], str | dict[str, Any] | None]) -> None:
    try:
        detail = action()
        CHECKS.append({"name": name, "status": "passed", "detail": detail or "passed"})
    except Exception as error:
        CHECKS.append({"name": name, "status": "failed", "detail": str(error), "traceback": traceback.format_exc()})

def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

def exact_diagnostic(fixture_name: str, code: str) -> str:
    result = compile_source(Path("examples") / fixture_name)
    codes = [diagnostic.code for diagnostic in result["diagnostics"]]
    require(code in codes, f"{fixture_name}: expected {code}, got {codes}")
    return f"{fixture_name} emitted {code}"

def write_temp_source(text: str) -> Path:
    directory = tempfile.TemporaryDirectory()
    TEMP_SOURCES.append(directory)
    path = Path(directory.name) / "formatted.ax"
    path.write_text(text, encoding="utf-8")
    return path

def cleanup() -> None:
    for temporary in TEMP_SOURCES:
        temporary.cleanup()

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
