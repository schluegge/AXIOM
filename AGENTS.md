# AGENTS.md

## Project

AXIOM is an AI-first systems language project. The active repository contains
an executed Python/LLVM semantics oracle that defines and tests the future Rust
bootstrap compiler.

The current product target is the v1 program defined in issue #9:

```text
safe deterministic local CLI and structured-data tools
```

Universal systems-language expansion remains a long-term direction, not a
license to develop unrelated domains in parallel.

## Planning authority

Current authority order:

1. normative semantic specifications;
2. `contracts/project.json` as the validated machine-readable index;
3. `MVP_ROADMAP.md` for implementation sequence and scope;
4. `AI_FIRST_MVP_CONTRACT.md` for measurable product claims;
5. milestone-specific normative contracts such as `AXIOM_BENCH_SPEC.md`;
6. roadmap amendments/ADRs for historical rationale;
7. `README.md` as a checked summary.

`contracts/project.schema.json` defines the structural project contract. The
semantic specifications remain the authority for language meaning; schema
validity alone is never semantic proof.

During M1, `AXIOM_BENCH_SPEC.md`, `AXIOM_BENCH_PREREGISTRATION.md`, and
`benchmarks/contracts/0.1.0/contract.json` define benchmark methodology. They do
not prove that a benchmark suite, runner, or AI-first result exists.

Historical amendments do not override the current canonical roadmap unless a
new amendment also updates that roadmap.

## Required reading

1. `README.md`
2. `contracts/project.json`
3. `CORE_SEMANTICS.md`
4. `MVP_ROADMAP.md`
5. `AI_FIRST_MVP_CONTRACT.md`
6. `PROOF_STATUS.md`
7. `ARITHMETIC_SEMANTICS.md`
8. `AGGREGATE_SEMANTICS.md`
9. `MUTATION_SEMANTICS.md`
10. `REFERENCE_SEMANTICS.md`
11. `AXIOM_BENCH_SPEC.md` during M1 or benchmark-affecting work
12. `AXIOM_BENCH_PREREGISTRATION.md` during M1 or benchmark-affecting work
13. `M1_BENCHMARK_SOURCE_EVIDENCE.md` before benchmark-tool or sandbox decisions
14. `CONTEXT7_SOURCE_EVIDENCE.md`
15. `CONTEXT7_MVP_DESIGN_EVIDENCE.md`
16. `M0_CONTRACT_SOURCE_EVIDENCE.md` when changing project-contract behavior
17. the relevant roadmap amendment
18. implementation and tests for the affected stage

## Mandatory rules

- Do not invent language semantics or external API signatures.
- Use authoritative source evidence before LLVM, ABI, linker, runtime, standard
  library, file-format, benchmark-tool, model-provider, sandbox, or operating-
  system integration.
- Stop with `BLOCKED_SOURCE_MISSING` when required evidence is unavailable.
- Deliver one visible, vertically complete capability per normal iteration.
- Exactly one language capability may be active at a time.
- Supporting parallel work is limited to regressions, required source evidence,
  documentation consistency, proof parity, and the benchmark slice for the
  active capability.
- Every capability must state the real program it unlocks and a falsifiable
  AI-development hypothesis or an explicit non-AI product justification.
- Preserve interpreter/native differential tests.
- Preserve Python/Rust implementation independence when the Rust bootstrap is
  introduced; a shared semantic bug must not be hidden by shared implementation
  code.
- Add deterministic valid, invalid, boundary, adversarial, generated, and
  differential tests.
- Keep Agent A implementation and Agent B release-blocking review separate.
- Never claim a phase passed without executable evidence.
- Never claim AI-first superiority from internal tests, shorter syntax, one
  model, one prompt, compiler success, or the M1 seed alone.
- Preserve all benchmark failures, invalidations, raw completions, traces, and
  historical benchmark versions.
- Do not weaken a preregistered benchmark gate after viewing results.
- The M1 benchmark has exactly three model iterations; a fourth response is
  prohibited rather than reported as an informal retry.
- Keep `language_only`, `compiler_assisted`, and `full_agent` results separate.
- Public/base checks cannot determine final task success; acceptance and security
  checks remain separate and mandatory.
- Every frozen task requires equivalent AXIOM, Rust, Zig, and Go variants, a
  passing reference solution, and at least one rejected plausible wrong solution.
- Raw model output is immutable evidence. Extraction may not repair code.
- A benchmark seed that becomes public cannot later be presented as an M13
  controlled holdout.
- Inspect AI is an adapter target, not benchmark authority. EvalPlus and
  MultiPL-E are methodological references, not canonical runners.
- A local process executor is not a security sandbox. Never apply or execute
  `untrusted_model_output` without an approved isolated non-local sandbox;
  otherwise stop with `AX-BENCH-SANDBOX-REQUIRED`.
- AI may develop and inspect AXIOM; AI is not part of runtime semantics.
- Target-specific layout or ABI facts must name the proven target.
- A green test may not be obtained by weakening a valid critic assertion.
- Safe references must remain non-null and non-forgeable.
- Borrow rules are frontend semantics; do not infer safety from LLVM pointer
  acceptance.
- Conservative rejection is preferable to unsound alias acceptance.
- Unknown symbols or imports may suggest only compiler-resolved existing names;
  never auto-install an undeclared package.
- Do not introduce a custom IDE, linker, debugger, package registry, backend, or
  orchestration framework before a current blocker proves it necessary.
- User-visible raw pointers and general-purpose `unsafe` remain post-v1 unless a
  reviewed roadmap amendment changes the canonical roadmap with new evidence.
- Every public implemented/proven claim in README and `PROOF_STATUS.md` must be
  represented by the feature IDs in `contracts/project.json`.
- A deferred feature may not be moved into the current feature list without the
  owning milestone, normative semantics, tests, proof IDs, and reviewed roadmap
  change.
- Project- and benchmark-contract checkers remain offline and may not resolve
  remote schemas, download packages, execute model code, or modify source files.

## Required feature workflow

1. Define the current real-program blocker, AI failure class, falsifiable
   hypothesis, comparison behavior, and non-goals.
2. Capture authoritative source evidence and classify external components.
3. Write or update normative grammar, typing, evaluation, effect, ownership,
   runtime, diagnostic, formatter, target, benchmark, and non-goal contracts.
4. Update `contracts/project.json` and public claim blocks when the project state
   changes.
5. Implement every affected compiler or benchmark stage vertically.
6. Run all proof categories and previous regressions.
7. Add the benchmark delta without rewriting historical results.
8. Run separate Agent B review.
9. Produce exact-PR Evidence and a known-unproven list.

## Verification

Install the exact proof dependencies, run both read-only contract gates, and then
run the canonical repository proof:

```bash
python3 -m pip install -r requirements-proof.txt
python3 tools/check_project_contract.py
python3 tools/check_benchmark_contract.py
python3 run_repo_proof.py
```

The repository proof must include passing project- and benchmark-contract
reports, unit and integration tests, Agent B report, native differential
evidence, manifest, and deterministic Evidence ZIP. Generated binaries,
benchmark raw outputs, and archives belong in Evidence or benchmark artifacts,
not source commits unless a specification explicitly requires a small fixture.
