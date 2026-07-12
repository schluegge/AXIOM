# M1 Trusted Task and Replay Authority Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure local trusted conformance executes only repository-registered tasks and replay derives conformance expectations from repository authority rather than the replayed bundle.

**Architecture:** Add a strict repository-owned trusted-task registry and one authority module that resolves task IDs and paths, validates task bytes, and derives adapter-specific expected outcomes. The runner must resolve authority before creating output or starting a process. Replay must resolve the same authority and reject task-hash or expected-outcome disagreement before accepting conformance.

**Tech Stack:** Python 3.11, JSON Schema Draft 2020-12, `unittest`, existing AXIOM deterministic Evidence utilities.

## Global Constraints

- M1 remains active; no real benchmark tasks, model adapter, sandbox, Inspect AI integration, or M2 work.
- Local execution remains limited to `reference` and `seeded_wrong`.
- Replay executes zero subprocesses.
- All paths remain exact normalized POSIX repository-relative paths.
- Existing deterministic canonical bundle behavior must remain stable unless the new authority record intentionally changes canonical content.
- Tests are written and observed failing before production code.

---

### Task 1: Add failing authority regressions

**Files:**
- Create: `tests/test_trusted_task_authority.py`

**Interfaces:**
- Consumes: `run_conformance(repository_root, task_path, *, language, adapter, output_directory)` and `replay_conformance(repository_root, bundle_path)`.
- Produces: regression expectations for `AX-BENCH-RUNNER-UNTRUSTED-TASK` and `AX-BENCH-REPLAY-AUTHORITY`.

- [ ] **Step 1: Write a failing test that copies the fixture outside the repository and proves no process/output creation occurs before rejection.**
- [ ] **Step 2: Write a failing test that relabels a valid seeded-wrong bundle as a reference bundle, repairs all internal hashes, and expects replay to reject the bundle using repository authority.**
- [ ] **Step 3: Run `python3 -m unittest tests.test_trusted_task_authority -v`.**

Expected: both tests fail on merged `main` because external task provenance is not checked and replay trusts `expected_outcome` from the bundle.

### Task 2: Add the trusted-task registry and authority resolver

**Files:**
- Create: `benchmarks/contracts/0.1.0/trusted-tasks.json`
- Create: `benchmarks/schemas/0.1.0/trusted-task-registry.schema.json`
- Create: `axiom_bench/authority.py`
- Modify: `benchmarks/contracts/0.1.0/contract.json`
- Modify: `axiom_bench/contract.py`
- Test: `tests/test_benchmark_contract.py`

**Interfaces:**
- Produces: `resolve_trusted_task(repository_root: Path, *, task_path: Path | None = None, task_id: str | None = None) -> TrustedTaskAuthority`.
- Produces: `expected_outcome(authority: TrustedTaskAuthority, adapter: str) -> dict[str, object]`.

- [ ] **Step 1: Add a strict registry schema and one entry for `fixture.runner-conformance`.**
- [ ] **Step 2: Add contract tests for duplicate IDs, unsafe paths, missing task files, and task-ID disagreement.**
- [ ] **Step 3: Run the contract tests and verify failure.**
- [ ] **Step 4: Implement registry validation and authority resolution with `safe_join`, symlink rejection, exact path equality, task schema validation, and task SHA-256 calculation.**
- [ ] **Step 5: Run contract and authority tests until green.**

### Task 3: Enforce authority in the runner

**Files:**
- Modify: `axiom_bench/runner.py`
- Test: `tests/test_trusted_task_authority.py`
- Test: `tests/test_benchmark_runner.py`

**Interfaces:**
- Consumes: `resolve_trusted_task(..., task_path=task_path)`.
- Produces: structured `AX-BENCH-RUNNER-UNTRUSTED-TASK` before output creation or process execution.

- [ ] **Step 1: Resolve authority before loading executable commands or preparing output.**
- [ ] **Step 2: Use the authority-resolved task document, canonical task path, and task hash throughout the report and trace.**
- [ ] **Step 3: Convert mutation tests to temporary repository roots containing an explicit registry, rather than passing unregistered external task paths to the real repository root.**
- [ ] **Step 4: Run runner and authority tests until green.**

### Task 4: Enforce authority in replay

**Files:**
- Modify: `axiom_bench/replay.py`
- Test: `tests/test_trusted_task_authority.py`
- Test: `tests/test_benchmark_replay_integrity.py`

**Interfaces:**
- Consumes: `resolve_trusted_task(..., task_id=manifest["task_id"])` and `expected_outcome(...)`.
- Produces: `AX-BENCH-REPLAY-AUTHORITY` findings for unknown tasks, task-hash mismatch, unsupported language variant, trust-class mismatch, or expected-outcome mismatch.

- [ ] **Step 1: Resolve the authoritative task by manifest task ID.**
- [ ] **Step 2: Compare report task hash with repository task bytes.**
- [ ] **Step 3: Derive reference/seeded-wrong expectations from adapter and authoritative task acceptance contract.**
- [ ] **Step 4: Reject any report expectation or trust class that differs from authority.**
- [ ] **Step 5: Recompute conformance using the authoritative expectation only.**
- [ ] **Step 6: Run replay tests until green.**

### Task 5: Correct documentation and proof claims

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `PROOF_STATUS.md`
- Modify: `AXIOM_BENCH_RUNNER_CONTRACT.md`
- Modify: `M1_BENCHMARK_SOURCE_EVIDENCE.md`
- Modify: `M1_RUNNER_SOURCE_EVIDENCE.md`
- Modify: `contracts/project.json`

**Interfaces:**
- Produces: public claims that explicitly name the registry/task hash authority and distinguish replay authenticity from internal consistency.

- [ ] **Step 1: Document that trusted local execution requires registry membership and exact repository task bytes.**
- [ ] **Step 2: Document that replay derives expected outcomes from the authoritative repository task contract.**
- [ ] **Step 3: Update test/check counts only after the full proof reports the executed values.**

### Task 6: Full proof and exact-head Evidence

**Files:**
- No source file is changed solely for this task.

- [ ] **Step 1: Run `python3 tools/check_project_contract.py`.**
- [ ] **Step 2: Run `python3 tools/check_benchmark_contract.py`.**
- [ ] **Step 3: Run `python3 run_repo_proof.py`.**
- [ ] **Step 4: Verify the draft PR workflow is green and inspect the uploaded Evidence.**
- [ ] **Step 5: Run the exact head a second time and require the same normalized inner Evidence digest before marking ready.**
