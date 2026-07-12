from __future__ import annotations

import shutil
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_RELATIVE = Path("tests/fixtures/benchmark_runner")
SCHEMAS_RELATIVE = Path("benchmarks/schemas/0.1.0")
CONTRACT_RELATIVE = Path("benchmarks/contracts/0.1.0/contract.json")
REGISTRY_RELATIVE = Path("benchmarks/contracts/0.1.0/trusted-tasks.json")


def create_trusted_test_repository(base: Path) -> tuple[Path, Path]:
    repository_root = base / "repository"
    fixture_root = repository_root / FIXTURE_RELATIVE
    schema_root = repository_root / SCHEMAS_RELATIVE
    contract_path = repository_root / CONTRACT_RELATIVE
    registry_path = repository_root / REGISTRY_RELATIVE

    fixture_root.parent.mkdir(parents=True, exist_ok=True)
    schema_root.parent.mkdir(parents=True, exist_ok=True)
    contract_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copytree(SOURCE_ROOT / FIXTURE_RELATIVE, fixture_root)
    shutil.copytree(SOURCE_ROOT / SCHEMAS_RELATIVE, schema_root)
    shutil.copy2(SOURCE_ROOT / CONTRACT_RELATIVE, contract_path)
    shutil.copy2(SOURCE_ROOT / REGISTRY_RELATIVE, registry_path)
    return repository_root, fixture_root / "task.json"
