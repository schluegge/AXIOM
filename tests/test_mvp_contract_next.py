from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/mvp.json"


def run_contract(contract: dict, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "mvp.json"
    path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return subprocess.run(
        [sys.executable, "tools/check_mvp_contract.py", "--contract", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_canonical_mvp_contract_is_valid() -> None:
    result = subprocess.run([sys.executable, "tools/check_mvp_contract.py"], cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unknown_property_is_rejected(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["unexpected"] = True
    result = run_contract(value, tmp_path)
    assert result.returncode == 1
    assert "Additional properties are not allowed" in result.stdout


def test_duplicate_proof_id_is_rejected(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["proof_stages"][1]["id"] = value["proof_stages"][0]["id"]
    result = run_contract(value, tmp_path)
    assert result.returncode == 1
    assert "proof stage identifiers must be unique" in result.stdout


def test_capability_widening_is_rejected(tmp_path: Path) -> None:
    value = json.loads(CONTRACT.read_text(encoding="utf-8"))
    value["host_capabilities"].append("capability.net.connect")
    result = run_contract(value, tmp_path)
    assert result.returncode == 1
