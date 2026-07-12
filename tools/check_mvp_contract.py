#!/usr/bin/env python3
"""Validate the frozen AXIOM Next MVP contract and repository bindings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

REQUIRED_HOSTS = {"x86_64-pc-windows-msvc", "x86_64-unknown-linux-gnu"}
REQUIRED_CAPABILITIES = {"capability.fs.read-text", "capability.fs.write-text"}
REQUIRED_PROOFS = {"legacy-provenance", "mvp-contract", "rust-workspace"}


def _safe_path(value: str) -> bool:
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in value


def validate(root: Path, contract_path: Path, schema_path: Path) -> list[str]:
    contract: dict[str, Any] = json.loads(contract_path.read_text(encoding="utf-8"))
    schema: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))
    findings = [error.message for error in sorted(Draft202012Validator(schema).iter_errors(contract), key=lambda item: list(item.path))]
    if findings:
        return findings

    if set(contract["supported_hosts"]) != REQUIRED_HOSTS:
        findings.append("supported_hosts must contain exactly the Windows and Linux MVP hosts")
    if set(contract["host_capabilities"]) != REQUIRED_CAPABILITIES:
        findings.append("host_capabilities must contain exactly read-text and write-text")

    proof_ids = [item["id"] for item in contract["proof_stages"]]
    if len(proof_ids) != len(set(proof_ids)):
        findings.append("proof stage identifiers must be unique")
    if set(proof_ids) != REQUIRED_PROOFS:
        findings.append("proof stages must contain exactly legacy-provenance, mvp-contract, and rust-workspace")

    features = set(contract["source_features"])
    non_goals = set(contract["non_goals"])
    if features & non_goals:
        findings.append("source_features and non_goals must be disjoint")

    seen_authorities: set[tuple[int, str, str]] = set()
    for authority in contract["authorities"]:
        key = (authority["rank"], authority["role"], authority["path"])
        if key in seen_authorities:
            findings.append(f"duplicate authority: {authority['path']}")
        seen_authorities.add(key)
        path = authority["path"]
        if not _safe_path(path):
            findings.append(f"unsafe authority path: {path}")
        elif not (root / path).is_file():
            findings.append(f"authority path does not exist: {path}")

    baseline = contract["legacy_baseline"]
    if baseline["commit"] != "67bc156a6afdb12654fe8cbb6837e5d449cfd063":
        findings.append("legacy baseline commit does not match the frozen main head")
    provenance = root / baseline["provenance_path"]
    if not provenance.is_file():
        findings.append("legacy provenance file is missing")
    else:
        data = json.loads(provenance.read_text(encoding="utf-8"))
        if data.get("legacy_commit") != baseline["commit"]:
            findings.append("legacy provenance and MVP contract commits differ")

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--contract", type=Path, default=Path("contracts/mvp.json"))
    parser.add_argument("--schema", type=Path, default=Path("contracts/mvp.schema.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    contract = args.contract if args.contract.is_absolute() else root / args.contract
    schema = args.schema if args.schema.is_absolute() else root / args.schema
    findings = validate(root, contract, schema)
    if findings:
        for finding in findings:
            print(f"ERROR: {finding}")
        return 1
    print("AXIOM Next MVP contract: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
