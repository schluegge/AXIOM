# AGENTS.md

## Project

AXIOM is an AI-first systems-language research project. The repository contains
an executed Python/LLVM semantic oracle and an active M1 benchmark foundation.
The focused v1 target is safe deterministic local CLI and structured-data tools.
Universal systems-language expansion is a later direction, not parallel scope.

## Authority order

1. normative semantic or benchmark contracts;
2. `contracts/project.json` as validated current-state index;
3. `MVP_ROADMAP.md` for sequence and scope;
4. `AI_FIRST_MVP_CONTRACT.md` for measurable claims;
5. roadmap amendments for historical rationale;
6. `README.md` and `PROOF_STATUS.md` as checked summaries.

Schema validity is never semantic or executable proof.

## Current M1 boundary

Implemented:

- `benchmark.contract-0.1` — methodology, preregistration, schemas, offline
  validation, contamination/fairness/trust laws;
- `benchmark.trusted-conformance-0.1` — trusted reference and seeded-wrong
  execution, bounded commands, deterministic bundles, and subprocess-free
  replay;
- `review.report-contract-0.1` — versioned automated-review report contract
  with offline validation and neutralized rendering;
- `review.deterministic-gate-0.1` — deterministic pull-request review gate
  with exact-head proof verification, protected baseline, and workflow
  security laws.

Not implemented or proven:

- frozen suite, equal-spec language packs, real comparison tasks, or frozen
  toolchains;
- sandbox or live-model adapter for model-generated output;
- model results or AI-first superiority;
- M1 completion.

The synthetic conformance fixture proves runner mechanics only.

## Required reading

1. `README.md`
2. `contracts/project.json`
3. relevant normative semantic specification
4. `MVP_ROADMAP.md`
5. `AI_FIRST_MVP_CONTRACT.md`
6. `PROOF_STATUS.md`
7. relevant source-evidence document
8. relevant implementation and tests

For M1 runner or replay work also read:

- `AXIOM_BENCH_SPEC.md`
- `AXIOM_BENCH_PREREGISTRATION.md`
- `AXIOM_BENCH_RUNNER_CONTRACT.md`
- `M1_BENCHMARK_SOURCE_EVIDENCE.md`
- `M1_RUNNER_SOURCE_EVIDENCE.md`

For review automation work also read:

- `AUTOMATED_REVIEW_CONTRACT.md`
- `REV2_REVIEW_GATE_SOURCE_EVIDENCE.md`
- `review/policy/0.1.0/gate-policy.json`

## Mandatory laws

- Do not invent language semantics or external API signatures.
- Capture authoritative source evidence before external compiler, ABI, runtime,
  file-format, benchmark-tool, provider, sandbox, or operating-system work.
- Stop with `BLOCKED_SOURCE_MISSING` when required evidence is unavailable.
- Deliver one vertically complete capability per normal iteration.
- Exactly one language milestone may be active at a time.
- Preserve interpreter/native differential tests.
- Preserve Python/Rust implementation independence once Rust bootstrap begins.
- Add deterministic valid, invalid, boundary, adversarial, generated,
  differential, and regression tests as applicable.
- Keep implementation and separate Agent B release-blocking checks distinct.
- Never claim a phase passed without executable exact-head Evidence.
- Never claim AI-first superiority from internal tests, syntax, one model, one
  prompt, compiler success, trusted conformance, or the M1 seed.
- Preserve raw completions, failures, invalidations, traces, and historical
  benchmark versions.
- Do not weaken a preregistered benchmark gate after observing results.
- Keep language-only, compiler-assisted, and full-agent results separate.
- Public checks do not determine final acceptance or security success.
- Frozen tasks require equivalent AXIOM, Rust, Zig, and Go variants, a passing
  reference, and at least one rejected plausible wrong solution.
- Extraction may not repair or synthesize a better candidate.
- A public seed cannot later be represented as a controlled holdout.
- Inspect AI is an adapter target, not benchmark authority.
- A local process runner is not a sandbox.
- Never execute `untrusted_model_output` locally; stop with
  `AX-BENCH-SANDBOX-REQUIRED` without an approved isolated backend.
- Target-specific layout and ABI claims must name the proven target.
- Safe references remain non-null and non-forgeable.
- Borrow rules are frontend semantics; LLVM pointer acceptance proves nothing.
- Conservative rejection is preferable to unsound alias acceptance.
- Unknown symbols may suggest only compiler-resolved existing names; never
  install undeclared packages automatically.
- Do not introduce a custom IDE, linker, debugger, registry, backend, or
  orchestration framework without a current proven blocker.
- Raw pointers and general-purpose `unsafe` remain post-v1 unless the canonical
  roadmap is amended with evidence.
- Public implemented/proven claims must be indexed in `contracts/project.json`.
- Contract checkers remain offline and may not download packages, execute model
  code, modify source, or resolve remote schemas.

## Trusted conformance laws

- Only repository-controlled `trusted_reference` and `trusted_seeded_wrong`
  candidates may execute locally.
- Commands are argument arrays with no shell interpretation.
- Existing output directories are never recursively replaced by the runner.
- Every bundle and internal reference path must be exact normalized POSIX,
  relative, and confined to its declared root.
- Command and total-task timeouts plus output, feedback, invocation, candidate,
  file, and changed-line limits are release-blocking.
- Process-start failure must produce structured failed Evidence.
- Replay executes zero subprocesses and recomputes the conformance decision.
- Raw volatile Evidence and deterministic canonical Evidence remain separate.

## Automated review laws

- Deterministic review findings are the only blocking review findings; AI
  review remains advisory and cannot set the merge verdict.
- The deterministic gate fails closed on malformed input, internal error,
  invalid policy, unparseable workflows, or report-validation failure.
- Review workflows use `pull_request` with read-only permissions;
  `pull_request_target` checkout or execution is forbidden.
- Third-party Actions remain pinned by immutable full-length commit SHA.
- Protected tests, Agent B registrations, proof stages, schemas, and
  workflows may change only through an explicit gate-policy edit.
- Review automation may not weaken tests, proof, contracts, permissions, or
  branch policy to obtain a green result.
- The gate never replaces an existing output directory and never publishes
  comments.

## Required feature workflow

1. State the concrete program blocker, failure class, falsifiable hypothesis,
   comparison behavior, and non-goals.
2. Capture authoritative source evidence and classify reused components.
3. Write or update normative grammar, typing, evaluation, effect, ownership,
   runtime, diagnostic, formatter, target, benchmark, and non-goal contracts.
4. Update `contracts/project.json` and checked public claims when state changes.
5. Implement all affected stages vertically.
6. Run prior regressions and every relevant proof category.
7. Add the benchmark delta without rewriting historical results.
8. Run separate Agent B checks.
9. Produce exact-PR Evidence and an explicit known-unproven list.

## Verification

```bash
python3 -m pip install -r requirements-proof.txt
python3 tools/check_project_contract.py
python3 tools/check_benchmark_contract.py
python3 run_repo_proof.py
```

The canonical proof must contain passing contract reports, unit/integration
results, Agent B results, trusted conformance and replay bundles, native
differential Evidence, a manifest, and a deterministic Evidence ZIP. Generated
binaries, raw benchmark outputs, and archives do not belong in source commits
unless a specification explicitly requires a small fixture.
