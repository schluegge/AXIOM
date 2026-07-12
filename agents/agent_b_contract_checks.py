from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from axiom_contract import check_project_contract

from .agent_b_support import check, require


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_mutation(
    root: Path,
    mutate: Callable[[dict[str, Any]], None],
    *,
    schema_mutation: bool = False,
) -> dict[str, Any]:
    contract_path = root / "contracts" / "project.json"
    schema_path = root / "contracts" / "project.schema.json"
    value = copy.deepcopy(_load(schema_path if schema_mutation else contract_path))
    mutate(value)
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory) / ("schema.json" if schema_mutation else "project.json")
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return check_project_contract(
            root,
            contract_path if schema_mutation else temporary,
            temporary if schema_mutation else schema_path,
        )


def _require_code(result: dict[str, Any], code: str) -> str:
    codes = {item["code"] for item in result["findings"]}
    require(result["status"] == "failed", f"seeded contradiction unexpectedly passed: {result}")
    require(code in codes, f"expected {code}, got {sorted(codes)}")
    return f"blocked with {code}"


def _valid_contract(root: Path) -> dict[str, Any]:
    result = check_project_contract(root)
    require(result["status"] == "passed", f"valid repository contract failed: {result}")
    require(result["counts"]["current_features"] == 10, "unexpected current feature count")
    require(result["counts"]["findings"] == 0, "valid contract contains findings")
    features = {item["id"]: item for item in _load(root / "contracts" / "project.json")["features"]}
    review_contract = features.get("review.report-contract-0.1")
    require(review_contract is not None, "review report contract capability is missing")
    require(review_contract["status"] == "implemented", "review report contract status is overstated")
    require(review_contract["proven_targets"] == [], "review report contract claims a language target")
    review_gate = features.get("review.deterministic-gate-0.1")
    require(review_gate is not None, "deterministic review gate capability is missing")
    require(review_gate["status"] == "implemented", "deterministic review gate status is overstated")
    require(review_gate["proven_targets"] == [], "deterministic review gate claims a language target")
    trusted = features.get("benchmark.trusted-conformance-0.1")
    require(trusted is not None, "trusted conformance capability is missing")
    require(trusted["status"] == "implemented", "trusted conformance status is overstated")
    require(trusted["proven_targets"] == [], "trusted conformance claims a language target")
    return {
        "features": result["counts"]["current_features"],
        "deferred": result["counts"]["deferred_features"],
        "validator": result["validator"],
        "review_contract_status": review_contract["status"],
        "review_gate_status": review_gate["status"],
        "trusted_conformance_status": trusted["status"],
    }


def register() -> None:
    from . import agent_b_support as support

    root = support.ROOT
    check("project-contract-valid", lambda: _valid_contract(root))
    check(
        "project-contract-broken-path-blocked",
        lambda: _require_code(
            _run_mutation(
                root,
                lambda value: value["features"][0]["implementation_paths"].append(
                    "axiom_proof/agent_b_missing.py"
                ),
            ),
            "AX-CONTRACT-2002",
        ),
    )
    check(
        "project-contract-duplicate-diagnostic-owner-blocked",
        lambda: _require_code(
            _run_mutation(
                root,
                lambda value: value["features"][1]["diagnostic_owners"].append(
                    "AX-TYPE-0007"
                ),
            ),
            "AX-CONTRACT-2014",
        ),
    )
    check(
        "project-contract-version-contradiction-blocked",
        lambda: _require_code(
            _run_mutation(root, lambda value: value["language"].update(version="0.8.0")),
            "AX-CONTRACT-1003",
        ),
    )
    check(
        "project-contract-unsupported-target-blocked",
        lambda: _require_code(
            _run_mutation(
                root,
                lambda value: value["features"][0]["proven_targets"].append(
                    "aarch64-unknown-linux-gnu"
                ),
            ),
            "AX-CONTRACT-2012",
        ),
    )
    check(
        "project-contract-deferred-as-current-blocked",
        lambda: _require_code(
            _run_mutation(
                root,
                lambda value: value["features"].append(
                    {
                        **copy.deepcopy(value["features"][0]),
                        "id": value["deferred_features"][0]["id"],
                        "summary": "Agent B seeded contradiction",
                    }
                ),
            ),
            "AX-CONTRACT-2005",
        ),
    )
    check(
        "project-contract-claim-drift-blocked",
        lambda: _require_code(
            _run_mutation(
                root,
                lambda value: value["claim_documents"][1]["feature_ids"].reverse(),
            ),
            "AX-CONTRACT-2018",
        ),
    )
    check(
        "project-contract-remote-schema-blocked",
        lambda: _require_code(
            _run_mutation(
                root,
                lambda value: value["properties"].update(
                    project={"$ref": "https://example.invalid/project.json"}
                ),
                schema_mutation=True,
            ),
            "AX-CONTRACT-1001",
        ),
    )
