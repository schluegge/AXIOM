from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_members_are_explicit_and_implemented() -> None:
    manifest = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))
    members = manifest["workspace"]["members"]
    assert members == ["crates/axiom-protocol", "crates/xtask"]
    assert all("*" not in member for member in members)
    metadata = manifest["workspace"]["metadata"]["axiom"]
    assert metadata["implemented-crates"] == ["axiom-protocol", "xtask"]
    assert "axiom-source" in metadata["planned-crates"]
    assert "axiom-cli" in metadata["planned-crates"]


def test_toolchain_and_third_party_manifest_are_pinned() -> None:
    toolchain = tomllib.loads((ROOT / "rust-toolchain.toml").read_text(encoding="utf-8"))
    assert toolchain["toolchain"]["channel"] == "1.85.1"
    third_party = tomllib.loads((ROOT / "third_party/manifest.toml").read_text(encoding="utf-8"))
    names = {item["name"] for item in third_party["components"]}
    assert {"Rust", "Python", "jsonschema"} <= names
    allowed = {"CAPABILITY_PROVIDER", "ADAPTER_TARGET", "REFERENCE_ONLY", "WATCH_ONLY", "REJECT", "RESET_CANDIDATE"}
    assert all(item["classification"] in allowed for item in third_party["components"])
