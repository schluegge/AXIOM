# AXIOM AI-First MVP Contract

Status: proposed normative release contract  
Applies to: AXIOM MVP tracked by issue #9  
Companion roadmap: `MVP_ROADMAP.md`

## 1. Purpose

This document prevents the phrase **AI-first** from becoming an unmeasured design
preference or marketing claim.

AXIOM is AI-first only when controlled experiments show that AI systems can
produce and maintain correct AXIOM programs more reliably and efficiently than
comparable languages under fair conditions.

Internal compiler tests prove implementation conformance. They do not prove
AI-first superiority.

## 2. Primary claim

The MVP claim is:

> Under equal-spec conditions and a fixed three-iteration compile/test budget,
> AI agents complete the frozen AXIOM MVP task suite at a materially higher rate
> than they complete equivalent Rust, Zig, or Go tasks, without reducing secure
> correctness or hiding additional work in language-specific tools.

The claim applies only to the MVP product domain:

```text
local deterministic CLI and structured-data tools
```

It does not claim superiority for networking, concurrent servers, GUI systems,
embedded work, kernel code, GPU programming, numerical computing, or every
software-engineering task.

## 3. Hard release gates

The release may use the phrase **measurably better for AI-driven development**
only if every hard gate passes on the frozen holdout set.

### Gate A — Highest bounded task success

Across at least two independent model families, AXIOM must have the highest
mean task-success rate within three compile/test iterations.

A task succeeds only when:

- the project builds from a clean checkout;
- all public and hidden functional tests pass;
- required static and semantic checks pass;
- no forbidden capability or dependency is used;
- security acceptance checks pass;
- output and exit behavior match the task contract.

### Gate B — Material advantage

AXIOM's aggregate success-rate advantage over the strongest comparison language
must be at least:

```text
10 percentage points absolute
```

The preregistered bootstrap 95% confidence interval for the paired difference
must exclude zero.

### Gate C — Context efficiency

Median total tokens-to-green for successful AXIOM tasks must be no worse than
the strongest comparison language under the same model and agent budget.

Tokens-to-green includes:

- task prompt;
- language pack;
- repository files read;
- compiler/test output returned to the model;
- model input and output for every iteration.

### Gate D — Secure correctness

AXIOM's secure-correct task rate must not be lower than the strongest secure
comparison language.

A task is not secure-correct when it passes functional tests but violates a
specified security property, capability boundary, resource limit, path rule,
input-validation rule, ownership rule, or dependency rule.

### Gate E — Reproducibility and disclosure

The result bundle must preserve:

- benchmark version and task hashes;
- public and encrypted/controlled holdout metadata;
- model provider, model identifier, and dated version where available;
- decoding and reasoning settings that are exposed by the provider;
- agent implementation and exact tool surface;
- system and task prompts;
- language packs;
- all completions, patches, commands, outputs, exit codes, and failures;
- token accounting method;
- wall-clock and hardware metadata;
- compiler and standard-library binaries/hashes;
- statistical analysis source and output.

A result without this bundle is exploratory only.

## 4. Benchmark result lanes

Results must remain separated. No unexplained composite score may combine these
lanes.

### 4.1 Language-only lane

Purpose: measure whether the source language and its ordinary documentation are
predictable to a model.

Allowed:

- task statement;
- equal-size task-limited language pack;
- source files required by the task;
- ordinary compiler text diagnostics;
- ordinary test output;
- up to three edit/compile/test iterations.

Not allowed:

- AXIOM-only semantic explain APIs;
- AXIOM-only repair plans;
- hidden solution templates;
- retrieval corpora larger or more task-specific than those given to comparison
  languages;
- automatic AST rewriting not available to all languages.

Primary use: the language-design claim.

### 4.2 Compiler-interaction lane

Purpose: measure the benefit of stable structured diagnostics and semantic
queries.

AXIOM receives its standard JSON protocol. Comparison languages receive the
best ordinary structured output that is part of their selected standard
compiler/toolchain configuration, documented before the run.

This lane must report:

- text-only result;
- structured-result delta;
- which diagnostic or explain documents were consumed;
- added context tokens;
- repair success by error category.

Primary use: compiler/tooling design.

### 4.3 Full-agent lane

Purpose: measure practical repository development.

Allowed tools are frozen and must expose equivalent capabilities:

- list/read/search files;
- edit/create/delete files;
- run formatter;
- build/check/test;
- inspect versioned compiler output;
- view bounded repository history when the task permits it.

No language receives a human-written repair hint not available to the others.

Primary use: product workflow.

### 4.4 Runtime lane

Purpose: measure generated program characteristics independently of AI success.

Measures:

- execution time;
- peak resident memory;
- binary size;
- startup time;
- deterministic output;
- safety-check behavior;
- target-specific build metadata.

Runtime wins do not compensate for failed AI-development gates.

### 4.5 Compiler lane

Purpose: measure compiler/product cost independently of generated program
performance.

Measures:

- cold full build;
- warm full build;
- incremental build after representative edits;
- formatter time;
- check-only time;
- peak compiler memory;
- compiler distribution size;
- diagnostic payload size.

## 5. Comparison languages

AI-development comparisons:

- Rust;
- Zig;
- Go.

C is included only when needed as:

- ABI reference;
- native layout reference;
- minimal runtime-performance reference.

C is not a primary AI-development comparison for tasks that require safe
ownership, typed errors, modules, or standard project tooling that would require
substantial external conventions.

The selected stable compiler versions are frozen before holdout execution.

## 6. Equal-spec protocol

AXIOM has less model-training exposure than established languages. The hard
claim therefore uses an equal-spec lane.

Each language pack must:

- fit the same preregistered token ceiling;
- cover only syntax, semantics, and APIs relevant to the task family;
- contain equivalent examples by concept, not copied solutions;
- include exact compiler and standard-library version;
- state important unsafe or unspecified behavior;
- avoid task-specific identifiers and algorithms;
- be generated before holdout tasks are revealed;
- be reviewed for accidental answer leakage.

A separate natural-knowledge lane may be reported, but it is descriptive and is
not the primary MVP gate.

## 7. Task families

The holdout set must cover all families below. Microtasks alone are insufficient.

### 7.1 Greenfield function tasks

Small typed functions with hidden edge cases.

Measures:

- syntax acquisition;
- type use;
- arithmetic and bounds semantics;
- variants and matching;
- string/byte correctness;
- algorithmic correctness.

### 7.2 Greenfield CLI tasks

Complete programs with arguments, files, typed errors, output, and exit codes.

Measures:

- project setup;
- standard-library API discovery;
- capability declarations;
- error propagation;
- deterministic output.

### 7.3 Compiler-error repair tasks

Programs with one or more seeded language errors.

Categories:

- unknown symbol or module;
- wrong type;
- implicit-conversion attempt;
- non-exhaustive match;
- ownership/move error;
- borrow conflict;
- effect/capability mismatch;
- invalid UTF-8 or byte/text API use;
- stale public API use.

### 7.4 Logical repair tasks

Programs compile but fail hidden tests.

Categories:

- wrong boundary condition;
- incorrect evaluation assumption;
- incomplete error handling;
- Unicode boundary bug;
- path or ordering nondeterminism;
- state mutation error;
- algorithmic mistake.

### 7.5 Security repair tasks

Programs function on ordinary tests but violate a stated security contract.

Categories relevant to the MVP:

- path traversal;
- overbroad filesystem authority;
- unchecked resource growth;
- unvalidated structured input;
- unsafe temporary-file behavior if present;
- secret/environment leakage;
- dependency or import confusion;
- incorrect error redaction;
- integer or bounds misuse.

### 7.6 Multi-module maintenance tasks

Existing repositories requiring coordinated edits.

Categories:

- public API migration;
- data-model extension;
- error-type change;
- module split or move;
- capability narrowing;
- standard-library version update;
- regression repair across several files.

### 7.7 Test-writing tasks

The agent must add tests for a requested property and implement the change.

Scoring includes mutation or seeded-bug detection so vacuous tests do not pass.

### 7.8 Documentation-to-code tasks

The agent receives the normative API/behavior contract and must implement or
update code without an example solution.

Measures whether the language and standard-library contracts are sufficiently
precise for model use.

## 8. Primary and secondary metrics

### Primary metric

```text
task_success_within_3_iterations
```

This is a binary per-task outcome under the full acceptance contract.

### Required secondary metrics

- compile success on first attempt;
- functional success on first attempt;
- secure-functional success on first attempt;
- success after each iteration;
- tokens-to-green;
- wall-clock-to-green;
- tool calls-to-green;
- compiler invocations-to-green;
- files read;
- files changed;
- patch line count;
- unnecessary patch rate;
- regression rate;
- hallucinated symbol count;
- hallucinated module/package count;
- undeclared dependency attempts;
- diagnostic categories encountered;
- repair success by diagnostic category;
- crash, timeout, and invalid-tool-call rates.

### Language complexity observations

These are reported but are not direct optimization targets:

- source token count;
- AST node count;
- number of explicit type annotations;
- number of explicit error branches;
- number of capability declarations;
- formatted line count.

Shorter is not automatically better.

## 9. What counts as an iteration

One iteration consists of:

1. model receives current permitted context;
2. model emits edits and optional tool commands;
3. edits are applied;
4. formatter/check/build/test commands run according to the frozen agent policy;
5. bounded output is returned.

Automatic formatting does not consume a model iteration. A new model response
after feedback does.

A task that exhausts the command, time, token, or iteration budget fails even if
a later uncounted repair could succeed.

## 10. Fairness controls

The benchmark must freeze:

- task repository state;
- hidden tests;
- language versions;
- standard libraries;
- compiler flags and profiles;
- model versions;
- system prompts;
- agent code;
- tool permissions;
- timeout and resource limits;
- maximum iterations;
- token ceiling;
- output truncation policy;
- hardware or normalized execution environment;
- retry policy for provider failures.

Language-specific adaptation is allowed only when it represents ordinary
required project configuration. It must be documented and included in cost and
context measurements.

## 11. Contamination controls

Each task records:

- source or author;
- creation date;
- public exposure date;
- repository commit hash;
- whether an equivalent solution has appeared publicly;
- similarity search result against public seed tasks where available;
- whether the task is public, validation, or holdout.

Holdout tasks should be newly authored or derived after the cutoff of tested
model versions where practical.

Public seed tasks and holdouts must test the same capability distribution but
must not share solution structure or identifiers.

## 12. Security acceptance

Functional tests are not sufficient.

Each security-relevant task declares machine-checkable properties, such as:

- access remains inside an allowed root;
- undeclared capabilities are absent;
- malformed input returns a typed error;
- secret values do not appear in stdout/stderr;
- resource limits trigger the specified failure;
- no dependency outside the lockfile is resolved;
- checked arithmetic and bounds behavior is preserved;
- output encoding remains valid.

Security scanners may supplement these properties but cannot replace direct
acceptance tests.

## 13. Statistical analysis

The preregistration defines:

- sample size by task family;
- paired comparison method;
- bootstrap procedure and seed policy;
- confidence interval;
- aggregation across model families;
- handling of provider/tool outages;
- timeout classification;
- multiple-comparison treatment for secondary analyses.

The primary comparison is paired by equivalent task and model family.

Exploratory metrics must be labeled exploratory. No secondary metric may be
promoted to the primary claim after results are known.

## 14. Benchmark anti-gaming rules

The following are prohibited:

- changing holdout tests after viewing AXIOM failures unless the task is proven
  invalid, in which case the invalidation and all prior results remain recorded;
- adding task-specific compiler hints;
- measuring only tasks designed around AXIOM's strongest feature;
- excluding failed model outputs from token or time accounting;
- reporting best-of-many private prompts as one standard run;
- using a larger or more specific AXIOM language pack;
- counting compiler success as functional success;
- counting functional success that violates security properties;
- changing comparison-language idioms to deliberately unnatural forms;
- collapsing language, compiler, agent, and runtime results into one score;
- hiding negative task families or model families.

## 15. AI-first design hypotheses

Every language feature issue must select at least one hypothesis below and define
its expected benchmark effect.

### H1 — Closed-world APIs reduce hallucination

Declared modules, exact standard-library versions, and compiler-known symbol
suggestions reduce invented APIs and package names.

### H2 — Explicit failure reduces omitted error paths

`Result`, `Option`, exhaustive `match`, and explicit propagation reduce silent
failure and incomplete branching.

### H3 — Explicit ownership reduces resource and aliasing defects

Moves, borrows, deterministic destruction, and no hidden clones reduce leaks,
double release, stale views, and conflicting mutation.

### H4 — Capability declarations reduce hidden authority

Pure defaults and explicit external effects reduce accidental filesystem,
environment, and process access.

### H5 — Canonical syntax reduces repair entropy

One formatter form, no overloads, no implicit conversions, and no accidental
shadowing reduce irrelevant patch variation and ambiguous compiler errors.

### H6 — Structured semantic feedback improves bounded repair

Stable diagnostics and explain documents improve repair success per returned
token, especially for type, ownership, effect, and module errors.

### H7 — Compact module interfaces reduce context demand

Explicit visibility and machine-readable interface summaries reduce repository
files read and total context needed for multi-module changes.

### H8 — Safe text/byte separation reduces encoding defects

Distinct bytes and UTF-8 text types with safe iteration and slicing reduce
Unicode and accidental binary/text bugs.

A feature that cannot name a testable product or AI hypothesis requires a
separate justification and cannot claim AI-first value.

## 16. Research lessons incorporated

The MVP contract adopts these established lessons rather than inventing a new
development mythology:

- small code-generation benchmarks do not represent repository maintenance;
- repeated sampling and iterative feedback can improve results, so fixed budgets
  and first-attempt metrics must both be reported;
- compiler and test feedback repairs syntax/runtime failures more readily than
  deep logical failures, so those categories remain separate;
- agent-computer interface design materially changes repository-task success,
  so language-only and full-agent lanes remain separate;
- AI-assisted users can produce insecure code while becoming more confident in
  it, so secure correctness is a hard gate rather than an optional scan;
- benchmark contamination and overfitting require timestamped, versioned,
  holdout evaluation;
- real tasks require coordinated changes across functions and files, so the MVP
  must include repository-scale maintenance cases.

Research identifiers used during roadmap creation include:

- arXiv:2107.03374 — *Evaluating Large Language Models Trained on Code*;
- arXiv:2211.03622 — *Do Users Write More Insecure Code with AI Assistants?*;
- arXiv:2310.06770 — *SWE-bench: Can Language Models Resolve Real-World GitHub Issues?*;
- arXiv:2403.07974 — *LiveCodeBench*;
- arXiv:2405.15793 — *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*;
- arXiv:2506.23034 — *Guiding AI to Fix Its Own Flaws*;
- arXiv:2606.17514 — *Unlocking LLM Code Correction with Iterative Feedback Loops*.

These sources inform the measurement design. They do not prove AXIOM's claim.

## 17. Release outcomes

### `MVP_PASS`

All language correctness, product, reproducibility, security, and AI-first hard
gates pass.

Permitted claim:

> AXIOM MVP is measurably better for AI-driven development in its defined local
> CLI and structured-data domain under the published benchmark contract.

### `MVP_TECHNICALLY_USABLE_AI_FIRST_NOT_PROVEN`

The compiler and golden applications pass, but one or more AI-first gates fail.

Permitted claim:

> AXIOM MVP is a usable experimental safe language; AI-first superiority is not
> yet proven.

### `MVP_BLOCKED`

Correctness, security, cross-platform, or reproducibility gates fail.

No MVP release is permitted.

## 18. Change control

This contract may be changed before holdout preregistration through a reviewed
roadmap amendment.

After preregistration:

- hard gates cannot be weakened for the current benchmark version;
- task families cannot be removed because AXIOM performs poorly;
- corrections to invalid tasks must be recorded publicly;
- a changed contract creates a new benchmark version;
- historical results remain available.
