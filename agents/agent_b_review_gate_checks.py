from __future__ import annotations

import copy
import json
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any

from axiom_review.gate import (
    POLICY_PATH,
    POLICY_SCHEMA_PATH,
    check_agent_b_registrations,
    check_proof_evidence,
    check_workflow_security,
    load_gate_policy,
)

from .agent_b_support import check, require


def _codes(findings: list[dict[str, Any]]) -> set[str]:
    return {item["code"] for item in findings}


def _temporary_root() -> Path:
    directory = tempfile.mkdtemp(prefix="axiom-agent-b-gate-")
    return Path(directory)


def _workflow_root(text: str, name: str = "attack.yml") -> Path:
    root = _temporary_root()
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / name).write_text(text, encoding="utf-8")
    return root


def _workflow_attack(root_path: Path, policy: dict[str, Any], text: str, code: str) -> str:
    attack_root = _workflow_root(text)
    try:
        outcome = check_workflow_security(attack_root, policy)
        require(outcome.conclusion == "failed", f"attack workflow passed: {text!r}")
        require(code in _codes(outcome.findings), f"expected {code}, got {_codes(outcome.findings)}")
        for finding in outcome.findings:
            require(finding["authority"] == "blocking", "security finding lost blocking authority")
            require(finding["severity"] == "critical", "security finding lost critical severity")
            require(bool(finding["evidence_path"].strip()), "security finding lost evidence")
    finally:
        shutil.rmtree(attack_root, ignore_errors=True)
    return f"blocked with {code}"


def _proof_fixture(root: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    evidence = root / "proof-evidence"
    evidence.mkdir()
    project = {"status": "passed", "counts": {"current_features": 3}}
    benchmark = {"status": "passed", "schemas_checked": 2}
    payload = evidence / "project-contract.json"
    payload.write_text('{"status": "passed"}\n', encoding="utf-8")
    manifest = {
        "document_kind": "axiom.repo-proof",
        "schema_version": "0.7.0",
        "status": "passed",
        "project_contract": {"status": "passed", "current_features": 3},
        "benchmark_contract": {"status": "passed", "schemas_checked": 2},
        "unit_test_exit_code": 0,
        "agent_b": {"exit_code": 0},
        "files": {"project-contract.json": sha256(payload.read_bytes()).hexdigest()},
    }
    (evidence / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evidence, project, benchmark


def _rewrite_manifest(evidence: Path, mutate) -> None:
    manifest_path = evidence / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _valid_gate_policy(root: Path) -> dict[str, Any]:
    policy, findings = load_gate_policy(root)
    require(policy is not None, f"repository gate policy failed: {_codes(findings)}")
    assert policy is not None
    protected = set(policy["protected_paths"])
    for required in (
        ".github/workflows/proof.yml",
        ".github/workflows/v1-roadmap-contract.yml",
        ".github/workflows/deterministic-review.yml",
        "run_repo_proof.py",
        "tools/run_deterministic_review.py",
        POLICY_PATH.as_posix(),
        POLICY_SCHEMA_PATH.as_posix(),
    ):
        require(required in protected, f"gate policy does not protect {required}")
    require(
        "agents.agent_b_review_gate_checks" in policy["agent_b_registration_modules"],
        "gate policy does not protect its own Agent B registration",
    )
    return policy


def register() -> None:
    from . import agent_b_support as support

    root = support.ROOT
    policy = None

    def valid_policy() -> dict[str, Any]:
        nonlocal policy
        policy = _valid_gate_policy(root)
        return {"protected_paths": len(policy["protected_paths"])}

    check("review-gate-policy-valid-and-self-protecting", valid_policy)
    if policy is None:
        return

    clean_workflow = (
        "name: clean\n"
        "on: [push]\n"
        "permissions:\n  contents: read\n"
        "jobs:\n  noop:\n    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10\n"
        "      - run: 'true'\n"
    )

    def clean_workflow_accepted() -> str:
        attack_root = _workflow_root(clean_workflow)
        try:
            outcome = check_workflow_security(attack_root, policy)
            require(outcome.conclusion == "passed", f"clean workflow blocked: {outcome.findings}")
        finally:
            shutil.rmtree(attack_root, ignore_errors=True)
        return "pinned read-only workflow accepted"

    check("review-gate-clean-workflow-accepted", clean_workflow_accepted)
    check(
        "review-gate-flow-mapping-permission-widening-blocked",
        lambda: _workflow_attack(
            root,
            policy,
            clean_workflow.replace(
                "permissions:\n  contents: read", "permissions: {contents: write}"
            ),
            "AX-REV-GATE-0503",
        ),
    )
    check(
        "review-gate-anchor-aliased-permission-widening-blocked",
        lambda: _workflow_attack(
            root,
            policy,
            "name: anchored\n"
            "on: [push]\n"
            "permissions: &grant\n  contents: write\n"
            "jobs:\n  noop:\n    runs-on: ubuntu-latest\n"
            "    permissions: *grant\n"
            "    steps:\n      - run: 'true'\n",
            "AX-REV-GATE-0503",
        ),
    )
    check(
        "review-gate-write-all-shorthand-blocked",
        lambda: _workflow_attack(
            root,
            policy,
            clean_workflow.replace("permissions:\n  contents: read", "permissions: write-all"),
            "AX-REV-GATE-0503",
        ),
    )
    check(
        "review-gate-hidden-pull-request-target-blocked",
        lambda: _workflow_attack(
            root,
            policy,
            clean_workflow.replace("on: [push]", "on: [push, pull_request_target]"),
            "AX-REV-GATE-0502",
        ),
    )
    check(
        "review-gate-tag-pinned-action-blocked",
        lambda: _workflow_attack(
            root,
            policy,
            clean_workflow.replace(
                "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10",
                "actions/checkout@v6",
            ),
            "AX-REV-GATE-0501",
        ),
    )
    check(
        "review-gate-short-sha-pin-blocked",
        lambda: _workflow_attack(
            root,
            policy,
            clean_workflow.replace(
                "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10",
                "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e1",
            ),
            "AX-REV-GATE-0501",
        ),
    )
    check(
        "review-gate-unparseable-workflow-fails-closed",
        lambda: _workflow_attack(root, policy, "{{{ not yaml ::::\n", "AX-REV-GATE-0504"),
    )

    def proof_attack(mutate, code: str, corrupt_payload: bool = False) -> str:
        attack_root = _temporary_root()
        try:
            evidence, project, benchmark = _proof_fixture(attack_root)
            if corrupt_payload:
                target = evidence / "project-contract.json"
                target.write_text('{"status": "rewritten"}\n', encoding="utf-8")
            if mutate is not None:
                _rewrite_manifest(evidence, mutate)
            outcome = check_proof_evidence(evidence, project, benchmark)
            require(outcome.conclusion != "passed", "tampered proof evidence passed")
            require(code in _codes(outcome.findings), f"expected {code}, got {_codes(outcome.findings)}")
        finally:
            shutil.rmtree(attack_root, ignore_errors=True)
        return f"blocked with {code}"

    def clean_proof_accepted() -> str:
        attack_root = _temporary_root()
        try:
            evidence, project, benchmark = _proof_fixture(attack_root)
            outcome = check_proof_evidence(evidence, project, benchmark)
            require(outcome.conclusion == "passed", f"clean proof blocked: {outcome.findings}")
        finally:
            shutil.rmtree(attack_root, ignore_errors=True)
        return "consistent proof evidence accepted"

    check("review-gate-clean-proof-evidence-accepted", clean_proof_accepted)
    check(
        "review-gate-proof-byte-rewrite-blocked",
        lambda: proof_attack(None, "AX-REV-GATE-0303", corrupt_payload=True),
    )
    check(
        "review-gate-proof-coherent-relabel-blocked",
        lambda: proof_attack(
            lambda manifest: (
                manifest["project_contract"].update(current_features=4),
                manifest["files"].update(
                    {
                        "project-contract.json": sha256(
                            b'{"status": "rewritten"}\n'
                        ).hexdigest()
                    }
                ),
            ),
            "AX-REV-GATE-0304",
            corrupt_payload=True,
        ),
    )
    check(
        "review-gate-proof-failed-status-relabel-blocked",
        lambda: proof_attack(
            lambda manifest: manifest.update(unit_test_exit_code=1),
            "AX-REV-GATE-0302",
        ),
    )

    def dead_code_registration_blocked() -> str:
        attack_root = _temporary_root()
        try:
            agents_dir = attack_root / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "agent_b_review.py").write_text(
                "from agents.agent_b_contract_checks import register as register_contract\n"
                "\n"
                "\n"
                "def _never_executed() -> None:\n"
                "    register_contract()\n"
                "\n"
                "\n"
                "def main() -> int:\n"
                "    return 0\n",
                encoding="utf-8",
            )
            outcome = check_agent_b_registrations(
                attack_root,
                {"agent_b_registration_modules": ["agents.agent_b_contract_checks"]},
            )
            require(outcome.conclusion == "failed", "dead-code registration was accepted")
            require(
                "AX-REV-GATE-0402" in _codes(outcome.findings),
                f"expected AX-REV-GATE-0402, got {_codes(outcome.findings)}",
            )
        finally:
            shutil.rmtree(attack_root, ignore_errors=True)
        return "blocked with AX-REV-GATE-0402"

    check("review-gate-dead-code-registration-blocked", dead_code_registration_blocked)

    def policy_traversal_blocked() -> str:
        attack_root = _temporary_root()
        try:
            for relative in (POLICY_PATH, POLICY_SCHEMA_PATH):
                target = attack_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / relative, target)
            policy_path = attack_root / POLICY_PATH
            mutated = json.loads(policy_path.read_text(encoding="utf-8"))
            mutated = copy.deepcopy(mutated)
            mutated["protected_paths"].append("../outside-the-repository")
            policy_path.write_text(
                json.dumps(mutated, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            loaded, findings = load_gate_policy(attack_root)
            require(loaded is None, "path-traversal policy was accepted")
            require(
                "AX-REV-GATE-0403" in _codes(findings),
                f"expected AX-REV-GATE-0403, got {_codes(findings)}",
            )
        finally:
            shutil.rmtree(attack_root, ignore_errors=True)
        return "blocked with AX-REV-GATE-0403"

    check("review-gate-policy-traversal-blocked", policy_traversal_blocked)
