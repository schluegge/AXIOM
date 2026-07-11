from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from axiom_bench import check_benchmark_contract, validate_document
from axiom_bench.contract import semantic_sha256

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "benchmarks" / "schemas" / "0.1.0"
ZERO64 = "0" * 64
ZERO40 = "0" * 40
NOW = "2026-07-11T00:00:00Z"


def load_schema(name: str) -> dict[str, object]:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def variant(language: str) -> dict[str, object]:
    return {
        "language": language,
        "language_pack_id": f"{language}.core.0.1.0",
        "starter_path": f"variants/{language}/starter.txt",
        "reference_solution_path": f"variants/{language}/reference.txt",
        "seeded_wrong_paths": [f"variants/{language}/wrong-1.txt"],
        "formatter_command": [f"{language}-format", "candidate"],
        "check_command": [f"{language}-check", "candidate"],
        "public_test_command": [f"{language}-test", "public"],
        "acceptance_test_command": [f"{language}-test", "acceptance"],
        "security_test_command": [],
        "expected_entry_point": "solve",
        "declared_dependencies": [],
        "variant_notes": [],
    }


def valid_task() -> dict[str, object]:
    return {
        "document_kind": "axiom.bench.task",
        "schema_version": "0.1.0",
        "task_id": "seed.checked-add",
        "task_version": "1.0.0",
        "family": "greenfield_function",
        "classification": "seed_public_after_freeze",
        "title": "Checked addition",
        "prompt_path": "prompt.md",
        "candidate_edit_allowlist": ["candidate.txt"],
        "visible_paths": ["README.md"],
        "variants": {language: variant(language) for language in ("axiom", "rust", "zig", "go")},
        "budgets": {
            "max_iterations": 3,
            "max_input_tokens_per_iteration": 4096,
            "max_output_tokens_per_iteration": 2048,
            "max_total_tokens": 12288,
            "max_tool_calls": 20,
            "max_compiler_invocations": 12,
            "command_timeout_seconds": 30,
            "task_timeout_seconds": 180,
            "max_output_bytes": 100000,
            "max_feedback_bytes": 20000,
            "max_candidate_files": 4,
            "max_candidate_bytes": 20000,
            "max_changed_lines": 200,
        },
        "acceptance": {
            "public_check_ids": ["public.example"],
            "acceptance_check_ids": ["hidden.boundary"],
            "security_check_ids": [],
            "required_failure_for_seeded_wrong": "acceptance_test_failure",
        },
        "provenance": {
            "authored_at": NOW,
            "first_public_at": None,
            "source_origin": "authored for AXIOM-Bench M1",
            "derived_from_known_benchmark": False,
            "source_hashes": [],
            "transformation_history": [],
            "contamination_notes": "Public seed after freeze; not an M13 holdout.",
        },
        "equivalence_review": {
            "status": "pending",
            "behavior_contract": "All variants compute the same checked result.",
            "algorithm_equivalent": True,
            "feedback_differences": [],
            "review_evidence": [],
        },
        "non_goals": ["No dynamic allocation."],
    }


def valid_suite() -> dict[str, object]:
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
        "task_paths": ["tasks/seed.checked-add/task.json"],
        "language_pack_paths": [
            "language-packs/axiom.json",
            "language-packs/rust.json",
            "language-packs/zig.json",
            "language-packs/go.json",
        ],
        "lanes": ["language_only", "compiler_assisted", "full_agent"],
        "adapters": ["reference", "seeded_wrong", "replay"],
        "hash_algorithm": "sha256",
        "semantic_sha256": None,
    }


def valid_pack() -> dict[str, object]:
    content = "language-packs/axiom.md"
    return {
        "document_kind": "axiom.bench.language-pack",
        "schema_version": "0.1.0",
        "pack_id": "axiom.core.0.1.0",
        "pack_version": "0.1.0",
        "language": "axiom",
        "compiler": {"name": "axiom semantic oracle", "version": "0.7.0", "identity_status": "frozen"},
        "standard_library": {"name": "none", "version": None, "identity_status": "unavailable"},
        "content_path": content,
        "task_families": ["greenfield_function"],
        "concepts": ["functions", "checked i32"],
        "safety_notes": ["Arithmetic is checked."],
        "source_paths": [content],
        "source_sha256": {content: ZERO64},
        "measurements": {"utf8_bytes": 100, "unicode_words": 20, "lines": 10},
        "provider_token_counts": [],
        "leakage_review": {
            "status": "pending",
            "forbidden_identifiers_checked": False,
            "task_specific_algorithms_found": False,
            "review_evidence": [],
        },
    }


def valid_attempt(success: bool = True) -> dict[str, object]:
    return {
        "document_kind": "axiom.bench.attempt",
        "schema_version": "0.1.0",
        "run_id": "conformance-1",
        "task_id": "seed.checked-add",
        "language": "axiom",
        "lane": "language_only",
        "adapter": "reference" if success else "seeded_wrong",
        "trust_class": "trusted_reference" if success else "trusted_seeded_wrong",
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
            "acceptance_test_success": True if success else False,
            "security_success": True,
            "full_success": success,
        },
        "failure_reason": None if success else "acceptance_test_failure",
        "budgets": {"max_iterations": 3},
        "usage": {
            "input_tokens": None,
            "output_tokens": None,
            "token_source": None,
            "tool_calls": 0,
            "compiler_invocations": 2,
            "wall_clock_ms": 1,
            "feedback_bytes": 0,
        },
        "mutations": {
            "files_read": [],
            "files_changed": ["candidate.ax"],
            "changed_lines": 5,
            "patch_bytes": 100,
            "forbidden_paths_attempted": [],
        },
        "evidence_complete": True,
    }


def valid_run() -> dict[str, object]:
    return {
        "document_kind": "axiom.bench.run",
        "schema_version": "0.1.0",
        "run_id": "reference-conformance",
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
            "notes": "Repository-controlled fixtures only.",
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
        "attempt_paths": ["attempts/one.json"],
        "invalidated_tasks": [],
        "summary": {
            "tasks_total": 1,
            "tasks_valid": 1,
            "tasks_invalid": 0,
            "tasks_successful": 1,
            "attempts_total": 1,
            "missing_metrics": ["tokens"],
        },
        "bundle_sha256": ZERO64,
    }


class BenchmarkContractTests(unittest.TestCase):
    def assert_valid(self, document: dict[str, object], schema_name: str) -> None:
        findings = validate_document(document, load_schema(schema_name), label=schema_name)
        self.assertEqual(findings, [], findings)

    def finding_codes(self, document: dict[str, object], schema_name: str) -> set[str]:
        return {
            item.code
            for item in validate_document(document, load_schema(schema_name), label=schema_name)
        }

    def test_repository_benchmark_contract_passes(self) -> None:
        result = check_benchmark_contract(ROOT)
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["schemas_checked"], 8)
        self.assertEqual(result["finding_count"], 0)

    def test_valid_draft_documents_pass(self) -> None:
        self.assert_valid(valid_suite(), "suite.schema.json")
        self.assert_valid(valid_task(), "task.schema.json")
        self.assert_valid(valid_pack(), "language-pack.schema.json")
        self.assert_valid(valid_attempt(True), "attempt.schema.json")
        self.assert_valid(valid_attempt(False), "attempt.schema.json")
        self.assert_valid(valid_run(), "run.schema.json")

    def test_frozen_suite_requires_identity_fields(self) -> None:
        document = valid_suite()
        document["status"] = "frozen"
        self.assertIn("AX-BENCH-CONTRACT-2001", self.finding_codes(document, "suite.schema.json"))

    def test_suite_semantic_hash_is_verified(self) -> None:
        document = valid_suite()
        document["semantic_sha256"] = ZERO64
        self.assertIn("AX-BENCH-CONTRACT-2002", self.finding_codes(document, "suite.schema.json"))
        document["semantic_sha256"] = semantic_sha256(document, frozenset({"semantic_sha256"}))
        self.assert_valid(document, "suite.schema.json")

    def test_task_requires_exactly_three_iterations(self) -> None:
        document = valid_task()
        document["budgets"]["max_iterations"] = 4  # type: ignore[index]
        self.assertIn("AX-BENCH-CONTRACT-1003", self.finding_codes(document, "task.schema.json"))

    def test_task_requires_all_four_language_variants(self) -> None:
        document = valid_task()
        del document["variants"]["zig"]  # type: ignore[index]
        self.assertIn("AX-BENCH-CONTRACT-1003", self.finding_codes(document, "task.schema.json"))

    def test_remote_dependency_is_rejected(self) -> None:
        document = valid_task()
        document["variants"]["rust"]["declared_dependencies"] = ["https://example.invalid/crate"]  # type: ignore[index]
        self.assertIn("AX-BENCH-CONTRACT-2004", self.finding_codes(document, "task.schema.json"))

    def test_public_controlled_holdout_is_rejected(self) -> None:
        document = valid_task()
        document["classification"] = "controlled_holdout"
        document["provenance"]["first_public_at"] = NOW  # type: ignore[index]
        self.assertIn("AX-BENCH-CONTRACT-2005", self.finding_codes(document, "task.schema.json"))

    def test_language_pack_content_hash_is_required(self) -> None:
        document = valid_pack()
        document["source_sha256"] = {}
        self.assertIn("AX-BENCH-CONTRACT-2006", self.finding_codes(document, "language-pack.schema.json"))

    def test_leakage_review_cannot_pass_with_found_algorithm(self) -> None:
        document = valid_pack()
        document["leakage_review"]["status"] = "passed"  # type: ignore[index]
        document["leakage_review"]["task_specific_algorithms_found"] = True  # type: ignore[index]
        self.assertIn("AX-BENCH-CONTRACT-2007", self.finding_codes(document, "language-pack.schema.json"))

    def test_full_success_requires_all_acceptance_and_evidence(self) -> None:
        document = valid_attempt(True)
        document["outcomes"]["acceptance_test_success"] = False  # type: ignore[index]
        document["evidence_complete"] = False
        codes = self.finding_codes(document, "attempt.schema.json")
        self.assertIn("AX-BENCH-CONTRACT-2008", codes)
        self.assertIn("AX-BENCH-CONTRACT-2009", codes)

    def test_failed_attempt_requires_reason(self) -> None:
        document = valid_attempt(False)
        document["failure_reason"] = None
        self.assertIn("AX-BENCH-CONTRACT-2010", self.finding_codes(document, "attempt.schema.json"))

    def test_untrusted_output_requires_isolated_nonlocal_sandbox(self) -> None:
        document = valid_run()
        document["adapter"] = "external_model"
        document["trust_class"] = "untrusted_model_output"
        document["model"] = {
            "provider": "example",
            "identifier": "model",
            "dated_version": None,
            "adapter_version": "0.1.0",
            "cutoff_notes": "unknown",
        }
        self.assertIn("AX-BENCH-SANDBOX-REQUIRED", self.finding_codes(document, "run.schema.json"))

    def test_reference_adapter_cannot_claim_model_usage(self) -> None:
        document = valid_run()
        document["model"] = {
            "provider": "example",
            "identifier": "model",
            "dated_version": None,
            "adapter_version": "0.1.0",
            "cutoff_notes": "not applicable",
        }
        self.assertIn("AX-BENCH-CONTRACT-2011", self.finding_codes(document, "run.schema.json"))

    def test_external_schema_reference_is_rejected(self) -> None:
        schema = copy.deepcopy(load_schema("task.schema.json"))
        schema["properties"]["title"] = {"$ref": "https://example.invalid/title.json"}  # type: ignore[index]
        self.assertIn("AX-BENCH-CONTRACT-1001", self.finding_codes(valid_task(), "task.schema.json") | {item.code for item in validate_document(valid_task(), schema)})


if __name__ == "__main__":
    unittest.main()
