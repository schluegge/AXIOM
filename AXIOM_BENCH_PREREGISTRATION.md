# AXIOM-Bench 0.1 Preregistration

Status: proposed; becomes immutable when benchmark version `0.1.0` is frozen  
Owning milestone: M1 / issue #12  
Companion specification: `AXIOM_BENCH_SPEC.md`

## 1. Scope of this preregistration

This document freezes the methodology used to validate AXIOM-Bench 0.1 and to
report exploratory model runs on the AXIOM v0.7 subset.

It does **not** preregister the final AXIOM v1 superiority test. M13 requires a
new preregistration written before its controlled holdout is revealed or run.

## 2. Research questions

### RQ1 — Harness validity

Can the benchmark execute every reference solution unattended and reject every
seeded plausible wrong solution for the intended acceptance reason?

### RQ2 — Current language baseline

Under equal-spec conditions, what fraction of v0.7-solvable seed tasks can each
selected model complete in AXIOM, Rust, Zig, and Go within three iterations?

### RQ3 — Repair behavior

Which compiler-error categories are repaired after ordinary text diagnostics,
and how many attempts, tokens, and compiler invocations are required?

### RQ4 — Lane effect

Where structured compiler output is available through the frozen standard
configuration, what is the within-language difference from text-only feedback?

### RQ5 — Methodological failure

Do any tasks show leakage, inequivalent variants, vacuous public tests, unstable
execution, hidden acceptance that rejects a correct equivalent solution, or a
runner/sandbox failure?

RQ5 failures invalidate the affected task. They are not converted into model
failures.

## 3. Benchmark population

Version `0.1.0` contains only tasks expressible in AXIOM v0.7:

- checked `i32` arithmetic and boundary behavior;
- boolean control flow;
- mutable locals and loops;
- structs and fixed arrays;
- checked indexing;
- structured l-value mutation;
- scoped shared/mutable references;
- compiler-error repair;
- formatter roundtrip;
- small multi-function changes within one source unit.

The seed does not include strings, dynamic allocation, modules, I/O, `Option`,
`Result`, generics, raw pointers, or concurrency.

## 4. Comparison languages

Primary comparison variants:

```text
axiom
rust
zig
go
```

C is excluded from the primary M1 AI-development comparison because the seed
contains safety/reference contracts that would require additional conventions
rather than equivalent ordinary language behavior.

Exact compiler versions and installation artifact hashes freeze before any live
model run. A toolchain update creates a new run configuration and cannot replace
historical results.

## 5. Lanes

Exploratory model runs may use:

1. `language_only`
2. `compiler_assisted`
3. `full_agent`

Each run selects exactly one lane. Results are reported separately. No weighted
or aggregate score across lanes is permitted.

Harness conformance uses:

```text
reference
seeded_wrong
replay
```

These are adapter classes, not result lanes.

## 6. Primary endpoint

For each language, model, lane, and task:

```text
task_success_within_3_iterations
```

The endpoint is binary and equals one only when the complete functional,
acceptance, security, dependency, budget, and evidence contract passes.

For M1 no inferential superiority claim is attached to this endpoint.

## 7. Required secondary endpoints

Per attempt:

- extraction success;
- parse/check success;
- compile success;
- public-test success;
- acceptance-test success;
- security-check success;
- full success;
- failure category;
- input/output tokens when known;
- tool calls;
- compiler/test invocations;
- bounded wall-clock duration;
- files read;
- files changed;
- changed lines;
- patch bytes;
- hallucinated symbol/module/dependency observations.

Per task/run:

- success after attempt 1, 2, and 3;
- tokens-to-green;
- wall-clock-to-green;
- calls-to-green;
- crash rate;
- timeout rate;
- invalid completion/patch rate;
- runner-invalidated task count.

Missing token/provider data remains `null` with a reason. It is not imputed as
zero.

## 8. Iteration budget

The model budget is exactly three responses per task.

A successful earlier attempt stops later model calls. Acceptance/security checks
still run on the successful candidate.

No manual repair, fourth response, off-record command, or post-hoc candidate
selection is allowed.

## 9. Task inclusion gates

A task enters `0.1.0` only if:

- all four language variants are reviewed as behaviorally equivalent;
- every reference solution passes public and acceptance checks;
- at least one seeded wrong solution passes enough public behavior to be
  plausible but fails acceptance/security;
- public examples do not reveal acceptance constants or algorithms;
- candidate-visible files contain no hidden solution fragments;
- setup and checks are deterministic in clean CI;
- all commands and resource budgets are explicit;
- task provenance and public dates are complete;
- no remote dependency is required;
- Agent B finds no leakage or inequivalence blocker.

## 10. Task invalidation rules

A task is invalidated for a run when:

- reference solution fails due to harness/toolchain error;
- equivalent correct implementation is rejected;
- acceptance fixture is missing or corrupted;
- candidate saw hidden acceptance content;
- language variants require materially different algorithms;
- toolchain installation/version differs from frozen record;
- execution escaped the declared workspace;
- trace/result evidence is incomplete;
- runner crash prevents a valid score.

Invalidated tasks are excluded from model success denominators for that run and
reported separately with evidence. The task itself is not silently repaired in
place; a benchmark version change is required.

## 11. Seed task count and balance

The target for `0.1.0` is at least 24 task-language contracts, representing at
least six distinct task IDs across four languages.

Task-family balance target:

- at least two greenfield function/control tasks;
- at least two compiler-error repair tasks;
- at least one logical repair task;
- at least one mutation/reference task;
- at least one formatter/canonicalization task, which may overlap another family.

No family may constitute more than half of task IDs.

## 12. Prompt and language-pack fairness

For each task family:

- prompts use the same behavioral contract across languages;
- language-specific wording is limited to filenames, commands, and syntax names;
- equal-spec packs remain below one frozen per-model token ceiling;
- examples are concept-equivalent and cannot contain task-specific identifiers;
- pack order and formatting are frozen;
- exact prompt+pack payload hashes are recorded;
- natural-knowledge runs are labeled separately.

A reviewer must sign off the equivalence record before freeze.

## 13. Model selection for exploratory runs

M1 may run one or more model families, but no specific provider is required for
harness completion.

Every live model run records:

- provider;
- exact model identifier and dated version when exposed;
- adapter version;
- generation settings exposed by the provider;
- provider token accounting source;
- reasoning/tool settings;
- run date;
- public cutoff information when known.

Results from model aliases without a stable dated identity are labeled
exploratory and cannot overwrite dated results.

## 14. Order and randomization

Harness conformance uses deterministic task-ID order.

Live model runs use a preregistered seed and balanced randomized order per model
and language. The order file is stored before execution. Retry order cannot be
selected based on observed task performance.

## 15. Statistical reporting

M1 reports descriptive results only:

- counts and proportions;
- per-task paired tables;
- attempt curves;
- medians and distributions for costs;
- exact missing/invalid counts.

Exploratory confidence intervals may be shown but cannot support the v1 hard
claim. No multiple-comparison-adjusted winner or global composite score is
created from the seed.

M13 will preregister its own paired bootstrap analysis and hard gates.

## 16. Security and execution

Reference and seeded-wrong fixtures are repository-controlled and may run in
disposable CI under the local reliability executor.

Untrusted model output cannot run under the local executor. A live-code run
requires an approved sandbox backend recorded in the run contract. Without one,
the run stops before candidate application/execution.

Sandbox availability may differ by developer environment; this cannot be
reported as a model or language failure.

## 17. Contamination reporting

Every task is classified as one of:

```text
seed_public_after_freeze
seed_derived_with_provenance
controlled_holdout
```

M1 tasks are normally `seed_public_after_freeze`. They are not used for M13 hard
claims after becoming public.

Known benchmark derivation, copied algorithms, repository issue origins, and
transformation history are mandatory fields.

## 18. Stopping and exclusion rules

A run stops when:

- frozen toolchain identity cannot be established;
- required sandbox is unavailable for untrusted code;
- suite/hash validation fails;
- evidence storage fails;
- more than 5% of tasks are invalidated by harness defects;
- model/provider terms or limits prevent the preregistered budget.

Partial results remain published as incomplete and cannot be relabeled as a
complete run.

## 19. Change control before freeze

Before `0.1.0` freeze, changes require:

- owning issue/PR;
- explicit rationale;
- updated task/schema hashes;
- reference and seeded-wrong conformance rerun;
- Agent B review;
- retained previous artifacts.

After freeze, acceptance-changing edits require `0.2.0` or later. Runner-only
corrections that provably preserve acceptance may use `0.1.x` with a migration
note.

## 20. Publication contract

A reported run publishes or retains in accessible Evidence:

- suite and all public task/language-pack files;
- controlled holdout metadata permitted by its process;
- raw model responses;
- extracted patches/source;
- complete traces;
- commands and bounded outputs;
- result and summary JSON;
- toolchain/model/adapter metadata;
- invalidation records;
- failures and timeouts;
- artifact hashes;
- analysis source.

Negative findings cannot be removed from later summaries.

## 21. M1 exit decision

M1 passes when benchmark `0.1.0` is frozen and:

- schemas and suite validate;
- reference conformance passes all variants;
- seeded-wrong conformance rejects every fixture;
- replay reproduces canonical scores;
- clean-checkout execution is unattended;
- repeated canonical hashes agree;
- lane separation and untrusted-local blocking are proven;
- Agent B passes;
- the ordinary AXIOM repository proof remains green.

M1 completion does not authorize an AI-first superiority claim. It authorizes
M2 Rust-bootstrap work against a measured v0.7 baseline.
