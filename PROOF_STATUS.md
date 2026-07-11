# Proof Status — v0.7.0

Proven native target: `x86_64-unknown-linux-gnu`  
Current milestone: M1 AXIOM-Bench seed

## Proven language surface

The complete public proven-language claim surface is checked against
`contracts/project.json`.

<!-- AXIOM-PROJECT-CONTRACT:FEATURES:BEGIN -->
- `core.vertical-pipeline` — source-to-native vertical pipeline and deterministic compiler documents.
- `language.mutable-control-flow` — explicit mutable locals, nested mutation, branches, and loops.
- `arithmetic.checked-i32` — checked signed arithmetic and stable fault behavior.
- `data.aggregates-fixed-arrays` — structs, fixed arrays, checked indexing, layout, and narrow C ABI proof.
- `mutation.structured-lvalues` — structured field/index assignment with specified evaluation order.
- `memory.scoped-references` — non-null scoped references and conservative lexical borrow checking.
<!-- AXIOM-PROJECT-CONTRACT:FEATURES:END -->

## Current exact-head proof target

- project contract: 8 current capabilities, 14 deferred features, 0 findings;
- benchmark contract: 8 schemas, 0 findings;
- unit/integration suite: 109/109;
- Agent B release-blocking checks: 73/73;
- interpreter/native differential corpus: 38/38;
- stable invalid fixture matrix: 52/52;
- deterministic repository Evidence ZIP.

These counts are targets until the final PR head passes and a repeated run
produces byte-identical inner Evidence.

## Implemented M1 benchmark contract

Capability `benchmark.contract-0.1` is implemented, not frozen. It covers:

- normative methodology and preregistration;
- contract, suite, task, language-pack, toolchain, attempt, run, and trace schemas;
- deterministic offline schema and semantic validation;
- exactly three model iterations;
- separate language-only, compiler-assisted, and full-agent lanes;
- mandatory AXIOM, Rust, Zig, and Go task variants;
- immutable raw completions and preserved negative results;
- public checks separated from acceptance and security checks;
- controlled-holdout provenance and contamination laws;
- prohibition on local execution of untrusted model output;
- prohibition on claiming AI-first superiority from the M1 seed.

## Implemented trusted conformance layer

Capability `benchmark.trusted-conformance-0.1` is implemented and integrated
into `run_repo_proof.py`.

The proof establishes:

- repository-controlled `reference` success;
- repository-controlled `seeded_wrong` rejection at the exact required phase;
- a minimal explicit child environment and argument-array execution;
- per-command and total-task timeout handling;
- combined output, cumulative feedback, invocation, candidate-byte, file, and
  changed-line limits;
- structured Evidence for process-start and output-directory creation failures;
- raw versus canonical Evidence separation;
- canonical stdout/stderr normalization of temporary workspace and task roots;
- byte-identical repeated reference bundles even when a command emits absolute
  temporary paths;
- canonical ZIP path, collision, symlink, encryption, count, declared-size, and
  actual-decompressed-size checks;
- replay conversion of malformed or memory-exhausting input into failed reports;
- replay validation of internal paths, schemas, identities, hashes, sizes, and
  trace sequence numbers;
- direct verification of candidate bytes against raw/extracted attempt hashes;
- independent derivation of outcomes and failure reasons from command records,
  stream sizes, retained budgets, and trace terminal events;
- cross-checking of derived results against attempt outcomes, report decisions,
  check-result trace events, and the score-decision event;
- exact agreement between attempt and conformance-report failure-reason enums;
- adversarial rejection when an attacker repairs the manifest/hash chain after
  replacing the candidate or rewriting an acceptance command result;
- replay with zero subprocesses;
- local rejection of untrusted model output before candidate application.

The integrated fixture has four language keys but one synthetic byte-level
behavior. It proves runner mechanics only. It is not a language benchmark.

## Security boundary

The trusted executor is a reliability-controlled local process runner, not a
sandbox. It does not provide filesystem namespaces, syscall filtering, network
isolation, CPU or memory quotas, or malicious process-tree containment.

Only repository-controlled reference and seeded-wrong fixtures may execute
locally. Model-generated candidate execution still requires an approved
isolated non-local backend.

## Completed M0 proof

M0 completed with:

- 6 then-current proven language features and 14 deferred features;
- 65/65 unit/integration tests;
- 59/59 Agent B checks;
- 38/38 differential cases;
- 52/52 invalid fixtures;
- exact dependency pins;
- two byte-identical Evidence ZIPs with SHA-256
  `6f615e62c6a3347792ea4d9611904498512f53a3359dd84707c9c0928880bbeb`.

## Language proof details

The current semantic oracle proves checked `i32`, functions, recursion, lexical
scopes, mutable control flow, structs, fixed arrays, checked indexing,
structured l-values, and scoped shared/mutable references. References remain
non-null and non-forgeable. Borrow conflicts are conservatively tracked at
whole-local-root granularity. The LLVM path contains no reference `inttoptr`,
`ptrtoint`, or null construction.

## Still unproven

- frozen AXIOM-Bench `0.1.0` suite;
- equal-spec language packs and real AXIOM/Rust/Zig/Go task corpus;
- frozen comparison toolchains and equivalence reviews;
- approved sandbox and live-model adapters;
- Inspect AI integration or any model result;
- any AI-first superiority claim;
- M1 completion;
- Rust bootstrap parity;
- broader scalar types and explicit conversions;
- variants, exhaustive matching, `Option`, `Result`, and generics;
- ownership, deterministic destruction, slices, bytes, UTF-8 strings, and lists;
- modules, visibility, manifest, lockfile, capability-enforced I/O, standard
  library, deterministic JSON, and Windows parity;
- raw pointers, `unsafe`, reborrowing, non-lexical lifetimes, reference returns,
  reference fields, networking, concurrency, GPU execution, LSP, package
  ecosystem, self-hosting, or broad ABI stability.

## Evidence reproducibility

The repository proof normalizes declared volatile timestamps, durations,
temporary paths in metadata, and temporary roots embedded in canonical command
streams. It retains candidate bytes, normalized command arguments and streams,
exit codes, limits, outcomes, diagnostics, native results, dependency versions,
and review reports. Raw Evidence retains original command streams outside the
canonical bundle. Final capability completion requires exact-head Evidence and
a second independent run with the same inner Evidence digest.
