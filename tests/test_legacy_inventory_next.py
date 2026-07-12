from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_provenance_is_complete_and_current() -> None:
    result = subprocess.run(
        [sys.executable, "tools/legacy_inventory.py", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((ROOT / "legacy/provenance.json").read_text(encoding="utf-8"))
    assert len(data["legacy_commit"]) == 40
    assert data["preserved_specs"]
    assert data["preserved_tests"]
    assert data["preserved_benchmarks"]
    assert data["reset_candidates"]
    for category in ("preserved_specs", "preserved_tests", "preserved_benchmarks"):
        for item in data[category]:
            path = ROOT / item["path"]
            assert item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
            assert len(item["git_blob_sha1"]) == 40
