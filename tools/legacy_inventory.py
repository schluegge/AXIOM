#!/usr/bin/env python3
"""Generate or verify the deterministic AXIOM legacy provenance document."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

BASE_COMMIT = "67bc156a6afdb12654fe8cbb6837e5d449cfd063"
APPROVED = {
    "preserved_specs": {
        "CORE_SEMANTICS.md": {
            "sha256": "aef3cd3910e5ba927c77e1ac4f9511bdbd14e7cbbfadfd884d5c6c6e611565fa",
            "git_blob_sha1": "5874806cba74ab0fef6a16692ac98188f07b1650",
        }
    },
    "preserved_tests": {
        "tests/test_project_contract.py": {
            "sha256": "9c09ec2a9755c817c70be6f32c013791df9ecc467f664bb1b720b61b202c05cd",
            "git_blob_sha1": "d93d838d1ce3d22b6288133c727a61c91c878750",
        }
    },
    "preserved_benchmarks": {
        "benchmarks/contracts/0.1.0/contract.json": {
            "sha256": "64a1c0dbf927f10ec5e95e0f39d54ee423f6e7142d1767c67edbb044a3b6458f",
            "git_blob_sha1": "e38e6cc44f03d92eba15ae19bf022b77a783db0c",
        }
    },
}
RESET_CANDIDATES = [
    {"path": "axiom_proof/", "reason": "legacy Python compiler implementation"},
    {"path": "runtime/", "reason": "legacy custom native runtime"},
    {"path": "axiom_review/", "reason": "review subsystem is not the AXIOM Next product"},
    {"path": ".github/workflows/", "reason": "routine proof must remain local-first"},
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_relative(path: str) -> None:
    value = PurePosixPath(path)
    if value.is_absolute() or ".." in value.parts or "\\" in path:
        raise ValueError(f"unsafe inventory path: {path}")


def build_inventory(root: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "document_kind": "axiom.legacy-provenance",
        "schema_version": "0.1.0",
        "legacy_commit": BASE_COMMIT,
        "source_repository": "schluegge/AXIOM",
        "preserved_specs": [],
        "preserved_tests": [],
        "preserved_benchmarks": [],
        "reset_candidates": RESET_CANDIDATES,
    }
    for category, paths in APPROVED.items():
        entries = []
        for relative, expected in sorted(paths.items()):
            _validate_relative(relative)
            source = root / relative
            if not source.is_file():
                raise FileNotFoundError(f"approved legacy file is missing: {relative}")
            actual = _sha256(source)
            if actual != expected["sha256"]:
                raise ValueError(
                    f"legacy baseline drift for {relative}: expected {expected['sha256']}, got {actual}"
                )
            entries.append(
                {
                    "path": relative,
                    "sha256": actual,
                    "git_blob_sha1": expected["git_blob_sha1"],
                }
            )
        result[category] = entries
    return result


def canonical_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("legacy/provenance.json"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    expected = canonical_json(build_inventory(root))
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != expected:
            print(f"legacy provenance mismatch: {output}")
            return 1
        print(f"legacy provenance verified: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"legacy provenance written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
