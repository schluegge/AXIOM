from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from axiom_bench import check_benchmark_contract, validate_document

from .agent_b_support import check, require

ZERO64 = "0" * 64
ZERO40 = "0" * 40
NOW = "2026-07-11T00:00:00Z"


def _schema(root: Path, name: str) -> dict[str, Any]:
    return json.loads(
        (root / "benchmarks" / "schemas" / "0.1.0" / name).read_text(encoding="utf-8")
    )


def _codes(root: Path, document: dict[str, Any], schema_name: str) -> set[str]:
    return {
        finding.code
        for finding in validate_document(document, _schema(root, schema_name), label=schema_name)
    }


def _variant(language: str) -> dict[str, Any]:
    return {
        "language": language,
        "language_pack_id": f"{language}.core.0.1.0",
        "starter_path": f"variants/{language}/starter.txt",
        "reference_solution_path": f"variants/{language}/reference.txt",
        "seeded_wrong_paths": [f"variants/{language}/wrong.txt"],
        "formatter_command": [f"{language}-format"],
        "check_command": [f"{language}-check"],
        "public_test_command": [f"{language}-public"],
        "acceptance_test_command": [f"{language}-acceptance"],
        "security_test_command": [],
        "expected_entry_point": "solve",
        "declared_dependencies": [],
        "variant_notes": [],
    }


def _task() -> dict[str, Any]:
    return {
        "document_kind": "axiom.bench.task",
        "schema_version": "0.1.0",
        "task_id": "agent-b.task",
        "task_version": "1.0.0",
        "family": "greenfield_function",
        "classification": "seed_public_after_freeze",
        "title": "Agent B fixture",
        "prompt_path": "prompt.md",
        "candidate_edit_allowlist": ["candidate.txt"],
        "visible_paths": [],
        "variants": {language: _variant(language) for language in ("axiom", "rust", "zig", "go")},
        "budgets": {
            "max_iterations": 3,
            "max_input_tokens_per_iteration": 100,
            "max_output_tokens_per_iteration": 100,
            "max_total_tokens": 300,
            "max_tool_calls": 10,
            "max_compiler_invocations": 10,
            "command_timeout_seconds": 10,
            "task_timeout_seconds": 60,
            "max_output_bytes": 10000,
            "max_feedback_bytes": 5000,
            "max_candidate_files": 2,
            "max_candidate_bytes": 10000,
            "max_changed_lines": 100,
        },
        "acceptance": {
            "public_check_ids": ["public"],
            "acceptance_check_ids": ["acceptance"],
            "security_check_ids": [],
            "required_failure_for_seeded_wrong": "acceptance_test_failure",
        },
        "provenance": {
            "authored_at": NOW,
            "first_public_at": None,
            "source_origin": "Agent B generated fixture",
            "derived_from_known_benchmark": False,
            "source_hashes": [],
            "transformation_history": [],
            "contamination_notes": "Test fixture only.",
        },
        "equivalence_review": {
            "status": "pending",
            "behavior_contract": "Equivalent fixture.",
            "algorithm_equivalent": True,
            "feedback_differences": [],
            "review_evidence": [],
        },
        "non_goals": ["Not a suite task."],
    }


def _suite() -> dict[str, Any]:
    return {
        "document_kind": "axiom.bench.suite",
        "schema_version": "0.1.0",
        "benchmark_version": "0.1.0",
        "status": "draft",
        "product_scope": "axiom-v0.7-semantic-oracle",
        "created_at": NOW,
        "frozen_at": None,
        "repository_commit": None,
        "specification_path": "AXIOM_BENCH_SPEC.md",
        "preregistration_path": "AXIOM_BENCH_PREREGISTRATION.md",
        "toolchains_path": "toolchains.json",
        "task_paths": ["tasks/task.json"],
        "language_pack_paths": ["packs/a", "packs/r", "packs/z", "packs/g"],
        "lanes": ["language_only", "compiler_assisted", "full_agent"],
        "adapters": ["reference", "seeded_wrong", "replay"],
        "hash_algorithm": "sha256",
        "semantic_sha256": None,
    }


def _attempt() -> dict[str, Any]:
    return {
        "document_kind": "axiom.bench.attempt",
        "schema_version": "0.1.0",
        "run_id": "agent-b",
        "task_id": "agent-b.task",
        "language": "axiom",
        "lane": "language_only",
        "adapter": "reference",
        "trust_class": "trusted_reference",
        "attempt_number": 1,
        "started_at": NOW,
        "finished_at": NOW,
        "raw_completion_path": "raw.txt",
        "raw_completion_sha256": ZERO64,
        "extracted_artifact_path": "candidate.ax",
        "extracted_artifact_sha256": ZERO64,
        "trace_path": "trace.jsonl",
        "trace_sha256": ZERO64,
        "command_records": [],
        "outcomes": {
            "extraction_success": True,
            "parse_success": True,
            "compile_success": True,
            "public_test_success": True,
            "acceptance_test_success": True,
            "security_success": True,
            "full_success": True,
        },
        "failure_reason": None,
        "budgets": {},
        "usage": {
            "input_tokens": None,
            "output_tokens": None,
            "token_source": None,
            "tool_calls": 0,
            "compiler_invocations": 1,
            "wall_clock_ms": 1,
            "feedback_bytes": 0,
        },
        "mutations": {
            "files_read": [],
            "files_changed": ["candidate.ax"],
            "changed_lines": 1,
            "patch_bytes": 1,
            "forbidden_paths_attempted": [],
        },
        "evidence_complete": True,
    }


def _run() -> dict[str, Any]:
    return {
        "document_kind": "axiom.bench.run",
        "schema_version": "0.1.0",
        "run_id": "agent-b",
        "benchmark_version": "0.1.0",
        "suite_sha256": ZERO64,
        "repository_commit": ZERO40,
        "status": "passed",
        "lane": "language_only",
        "adapter": "reference",
        "trust_class": "trusted_reference",
        "sandbox": {
            "backend": "local_reliability_only",
            "isolated": False,
            "configuration_sha256": None,
            "notes": "Trusted fixture only.",
        },
        "model": None,
        "generation": {"settings_source": "not applicable"},
        "toolchains": {
            language: {
                "name": language,
                "version": None,
                "identity_status": "pending",
                "artifact_sha256": None,
                "version_output": None,
            }
            for language in ("axiom", "rust", "zig", "go")
        },
        "order_seed": 0,
        "started_at": NOW,
        "finished_at": NOW,
        "attempt_paths": [],
        "invalidated_tasks": [],
        "summary": {
            "tasks_total": 0,
            "tasks_valid": 0,
            "tasks_invalid": 0,
            "tasks_successful": 0,
            "attempts_total": 0,
            "missing_metrics": [],
        },
        "bundle_sha256": ZERO64,
    }


def register() -> None:
    from . import agent_b_support as support

    root = support.ROOT

    def valid_contract() -> dict[str, Any]:
        result = check_benchmark_contract(root)
        require(result["status"] == "passed", f"benchmark contract failed: {result}")
        require(result["schemas_checked"] == 8, "unexpected benchmark schema count")
        return result

    check("benchmark-contract-valid", valid_contract)

    def fourth_iteration() -> str:
        task = _task()
        task["budgets"]["max_iterations"] = 4
        require("AX-BENCH-CONTRACT-1003" in _codes(root, task, "task.schema.json"), "fourth iteration accepted")
        return "fourth model iteration blocked"

    check("benchmark-contract-three-iteration-limit", fourth_iteration)

    def missing_variant() -> str:
        task = _task()
        del task["variants"]["zig"]
        require("AX-BENCH-CONTRACT-1003" in _codes(root, task, "task.schema.json"), "missing Zig variant accepted")
        return "missing language variant blocked"

    check("benchmark-contract-four-language-requirement", missing_variant)

    def frozen_without_identity() -> str:
        suite = _suite()
        suite["status"] = "frozen"
        require("AX-BENCH-CONTRACT-2001" in _codes(root, suite, "suite.schema.json"), "unidentified frozen suite accepted")
        return "frozen suite identity enforced"

    check("benchmark-contract-frozen-suite-identity", frozen_without_identity)

    def false_success() -> str:
        attempt = _attempt()
        attempt["outcomes"]["acceptance_test_success"] = False
        require("AX-BENCH-CONTRACT-2008" in _codes(root, attempt, "attempt.schema.json"), "false success accepted")
        return "full success requires acceptance"

    check("benchmark-contract-full-success-law", false_success)

    def untrusted_local() -> str:
        run = _run()
        run["adapter"] = "external_model"
        run["trust_class"] = "untrusted_model_output"
        run["model"] = {
            "provider": "seeded",
            "identifier": "seeded",
            "dated_version": None,
            "adapter_version": "0.1.0",
            "cutoff_notes": "seeded",
        }
        require("AX-BENCH-SANDBOX-REQUIRED" in _codes(root, run, "run.schema.json"), "untrusted local execution accepted")
        return "untrusted local execution blocked"

    check("benchmark-contract-untrusted-sandbox-law", untrusted_local)

    def external_ref() -> str:
        schema = copy.deepcopy(_schema(root, "task.schema.json"))
        schema["properties"]["title"] = {"$ref": "https://example.invalid/title.json"}
        codes = {finding.code for finding in validate_document(_task(), schema)}
        require("AX-BENCH-CONTRACT-1001" in codes, "external schema reference accepted")
        return "external schema reference blocked"

    check("benchmark-contract-offline-schema-law", external_ref)
