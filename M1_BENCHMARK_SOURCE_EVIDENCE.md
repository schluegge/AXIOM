# M1 Benchmark Source Evidence

Status: source evidence for AXIOM-Bench 0.1 methodology  
Applies to: issue #12  
Decision date: 2026-07-11

## Purpose

M1 needs a provider-neutral, contamination-aware, execution-based benchmark for
AXIOM, Rust, Zig, and Go. AXIOM must define its task equivalence, fairness,
iteration, acceptance, trace, and release-claim contracts. It must not rebuild
established model-evaluation, test-amplification, or process-measurement systems
when they can be adapted without becoming semantic authority.

## Inspect AI

Resolved Context7 source:

```text
/ukgovernmentbeis/inspect_ai
```

Official repository source inspected at commit:

```text
397753d0749b92d21cd751e7c3f2582a8d88e2ef
```

Relevant public concepts observed:

- `Task` combines a dataset, solver plan, sandbox, and scorer;
- `Sample` can carry input, target, files, setup logic, sandbox configuration,
  and metadata;
- custom scorers use the public `@scorer` decorator and return `Score` values;
- `eval()` and `eval_set()` produce persisted `EvalLog` objects;
- evaluation logs preserve metadata and support reading and controlled edits;
- `eval_set()` supports multiple tasks/models and retry attempts;
- `inspect eval-retry` can resume a failed or interrupted evaluation;
- multiple hosted and local model providers are supported.

Security boundary from the official sandbox documentation:

- model tool calls execute in the evaluation process by default;
- arbitrary shell/code tools therefore require a dedicated execution
  environment;
- built-in Docker sandboxes and extension sandboxes provide per-sample
  environments;
- the built-in `local` environment is explicitly described as **local file
  system (no sandbox)**;
- Docker configuration can set CPU, memory, and `network_mode: none` limits;
- file-read and execution-output caps are boundary controls, not a replacement
  for process isolation.

Decision:

```text
ADAPTER_TARGET
```

AXIOM-Bench keeps its canonical task, language-pack, attempt, trace, and result
schemas independent of Inspect AI. A later adapter may map the frozen AXIOM
contracts into Inspect `Task`, `Sample`, solver, scorer, sandbox, and `EvalLog`
objects. This avoids coupling the benchmark's meaning to one framework or model
provider.

Inspect's `local` backend is never represented as secure isolation. Untrusted
model-generated code may run only through an explicitly approved isolated
sandbox backend. M1's local CI executes only repository-controlled reference and
seeded-wrong fixtures.

## EvalPlus

Resolved Context7 source:

```text
/evalplus/evalplus
```

Observed contracts and patterns:

- versioned HumanEval+ and MBPP+ datasets expose dataset hashes;
- each task separates base inputs from a much larger augmented `plus_input`
  acceptance set;
- canonical solutions and entry points are represented explicitly;
- generated samples are stored in JSON Lines form;
- evaluation supports parallel execution;
- sanitization utilities extract candidate Python functions;
- the project supports local execution and Docker-based sandboxed evaluation.

Decision:

```text
REFERENCE_ONLY
```

AXIOM-Bench adopts these methodological lessons:

- preserve a cryptographic suite hash;
- distinguish public/base checks from stronger acceptance checks;
- require every seeded wrong implementation to be rejected by acceptance tests;
- preserve raw candidate output separately from any extracted source;
- never equate passing the public examples with task success.

EvalPlus is Python- and HumanEval/MBPP-oriented. It is not used as the canonical
multi-language runner, task format, sanitizer, or security boundary. AXIOM must
not silently transform model output into a more correct program; extraction is
recorded as a separate trace event and the raw completion is retained.

## MultiPL-E

Context7 did not return an authoritative library match for MultiPL-E. The
project is therefore not vendored or treated as an API source in M1.

Decision:

```text
REFERENCE_ONLY
```

The general lesson retained is that equivalent test-driven tasks can be
represented across several languages. AXIOM-Bench does not assume automatic
translation proves semantic equivalence. Every language variant requires human-
reviewable interface, test-vector, compiler-command, and behavior contracts.

## Official comparison toolchains

M1 records exact compiler versions before the suite is frozen. Current official
release evidence consulted on 2026-07-11 includes:

- Go's official download page lists Go 1.26.5 and publishes per-archive SHA-256
  checksums;
- Zig's official download page lists Zig 0.16.0, dated 2026-04-13, with signed
  platform archives;
- Rust documents `rustup` as the recommended cross-platform toolchain manager
  and uses a six-week stable release process.

No toolchain version becomes canonical merely because it was current on the
research date. The exact versions and installation artifact hashes are frozen
in the benchmark suite contract only after clean CI execution proves all four
language adapters.

## Hyperfine

Previously resolved Context7 source:

```text
/sharkdp/hyperfine
```

Decision:

```text
CAPABILITY_PROVIDER_LATER
```

Hyperfine is reserved for compiler/runtime process timing after functional
correctness is established. It supports warmups, fixed/bounded run counts,
parameter scans, setup/cleanup outside the measured command, explicit shell
selection, and result export. It is not used to score AI task success or decide
benchmark fairness.

## Core implementation decision

AXIOM-Bench 0.1 uses a small repository-owned contract layer because these
requirements are AXIOM-specific and cannot be delegated safely:

- equal-spec language-pack equivalence;
- exactly three model iterations;
- immutable public/base versus acceptance checks;
- lane separation;
- raw completion and tool-trace retention;
- contamination/provenance metadata;
- secure-correct acceptance;
- no public superiority claim from the seed suite.

The core uses established JSON Schema validation already pinned by M0. It does
not implement a model provider, tokenizer, container engine, statistics
framework, package manager, or general agent framework.

## Trust classes

The benchmark contract distinguishes:

```text
trusted_reference
trusted_seeded_wrong
replay_only
untrusted_model_output
```

Local subprocess execution is permitted only for repository-controlled trusted
fixtures in disposable CI or an explicitly trusted developer checkout.
`untrusted_model_output` requires an approved isolated sandbox implementation;
without one the runner must stop with `AX-BENCH-SANDBOX-REQUIRED` before applying
or executing candidate code.

## Non-decisions

This evidence does not authorize:

- Docker as a mandatory AXIOM developer dependency;
- local execution of arbitrary model code;
- automatic code repair or sanitizer-based score inflation;
- use of HumanEval+/MBPP+ tasks as AXIOM's M1 seed;
- a provider-specific primary benchmark format;
- merging language-only, compiler-assisted, and full-agent scores;
- changing prompts or hidden acceptance tests after observing model results.
