# Proof Status — v0.7.0

Proven native target: `x86_64-unknown-linux-gnu`  
Current milestone: M1 AXIOM-Bench seed and preregistration

## Contract-indexed proven language features

The following IDs are the complete public proven-language claim surface. They
are checked against `contracts/project.json` by
`tools/check_project_contract.py`.

<!-- AXIOM-PROJECT-CONTRACT:FEATURES:BEGIN -->
- `core.vertical-pipeline` — source-to-native vertical pipeline and deterministic compiler documents.
- `language.mutable-control-flow` — explicit mutable locals, nested mutation, branches, and loops.
- `arithmetic.checked-i32` — checked signed arithmetic and stable fault behavior.
- `data.aggregates-fixed-arrays` — structs, fixed arrays, checked indexing, layout, and narrow C ABI proof.
- `mutation.structured-lvalues` — structured field/index assignment with specified evaluation order.
- `memory.scoped-references` — non-null scoped references and conservative lexical borrow checking.
<!-- AXIOM-PROJECT-CONTRACT:FEATURES:END -->

## Current M1 benchmark-contract implementation

Project capability `benchmark.contract-0.1` is registered as **implemented**,
not proven or frozen. The current release gate covers:

- normative `AXIOM_BENCH_SPEC.md`;
- preregistered M1 methodology;
- source-backed harness and sandbox decisions;
- strict contract, suite, task, language-pack, toolchain, attempt, run, and trace
  schemas;
- deterministic offline validation;
- semantic rules beyond JSON Schema;
- independent Agent B attacks;
- inclusion of the contract report in the repository Evidence ZIP.

Current exact-head proof target:

- project contract: 7 current capabilities, 14 deferred features, 0 findings;
- benchmark contract: 8 schemas, 0 findings;
- unit/integration suite: 80/80;
- Agent B release-blocking review: 66/66;
- interpreter/native differential corpus: 38/38;
- stable invalid fixture matrix: 52/52.

These counts must pass on the final PR head and repeated-run Evidence before the
contract PR can merge.

## Benchmark-contract laws under proof

- exactly three model iterations;
- separate language-only, compiler-assisted, and full-agent lanes;
- all task contracts require AXIOM, Rust, Zig, and Go variants;
- public/base checks remain separate from acceptance/security checks;
- raw completion evidence is immutable;
- extraction may not synthesize a more correct candidate;
- frozen suite identity requires commit, time, and semantic hash;
- controlled holdouts cannot already be public;
- remote task dependencies are rejected;
- successful attempts require complete acceptance and evidence;
- failed attempts require a stable failure reason;
- trusted conformance adapters cannot claim model usage;
- untrusted model output requires an isolated non-local sandbox and is blocked
  locally with `AX-BENCH-SANDBOX-REQUIRED`;
- M1 seed results cannot prove AI-first superiority.

## Explicit M1 non-proof boundary

The following are not yet implemented or proven:

- frozen AXIOM-Bench `0.1.0` suite;
- reference, seeded-wrong, and replay adapters;
- runner, workspace, command, budget, and bundle implementation;
- equal-spec language packs;
- frozen AXIOM/Rust/Zig/Go toolchain matrix;
- seed task corpus and equivalence reviews;
- reference and seeded-wrong conformance bundles;
- approved sandbox adapter for untrusted model output;
- Inspect AI adapter or live model provider;
- any model result or AI-first superiority claim;
- M1 completion.

## Completed M0 release-blocking proof

M0 completed through PR #27 with:

- project contract: 6 then-current features, 14 deferred features, 0 findings;
- unit/integration suite: 65/65;
- Agent B release-blocking review: 59/59;
- interpreter/native differential corpus: 38/38;
- stable invalid fixture matrix: 52/52;
- complete pinned proof dependency closure.

Two exact-head M0 runs produced byte-identical Evidence ZIPs:

```text
6f615e62c6a3347792ea4d9611904498512f53a3359dd84707c9c0928880bbeb
```

## Project-contract proofs

- Draft 2020-12 schema checked explicitly with `Draft202012Validator`;
- external schema references rejected before validator construction;
- exact dependency pins verified against installed package versions;
- every indexed repository path exists and remains inside the repository root;
- current and deferred feature IDs are unique and disjoint;
- every proven feature has normative semantics, tests, proof IDs, and a named target;
- every source diagnostic family has exactly one feature owner;
- README and proof-status language claim blocks match the contract exactly;
- project contract and v1 roadmap agree on the active milestone;
- invalid pins, missing dependencies, version drift, broken paths, claim drift,
  duplicate diagnostic ownership, unsupported targets, and deferred-as-current
  mutations are release-blocking.

## Scoped-reference proofs

- `&T`, `&mut T`, borrow expressions, dereference reads/writes;
- shared aliases coexist;
- mutable references provide exclusive access;
- immutable-root mutable borrow rejection;
- root reads/writes blocked during conflicting live borrows;
- reference returns and aggregate storage rejected;
- local reference lifetime ends at block boundary;
- direct call borrows cover complete left-to-right argument evaluation;
- existing `&mut` values cannot be copied into overlapping call loans;
- inner nested-call loan releases before the next outer argument;
- dynamic borrowed index executes once;
- OOB reference formation matches panic identity/code 108;
- struct-field and array-element references match interpreter/native execution;
- LLVM uses `ptr`, stack/GEP addresses, `load`, and `store`;
- LLVM contains no reference `inttoptr`, `ptrtoint`, or null construction;
- ownership/symbol/effect documents expose borrow facts.

## Conservative boundary

Borrow conflicts are tracked at whole-local-root granularity. Disjoint fields
of one struct are not simultaneously borrowable when either borrow conflicts at
the root. This is conservative and safe, not a field-sensitive lifetime proof.

## Language and product work not proven

- raw pointers, null pointers, pointer arithmetic, or `unsafe`;
- reborrowing or non-lexical lifetimes;
- lifetime parameters or reference returns;
- reference fields/arrays;
- slices or heap allocation;
- owned-resource destruction semantics;
- broad cross-platform ABI stability;
- complete effect/capability system;
- Rust bootstrap parity, self-hosting, GPU execution, or AXIOM 1.0.

## Evidence reproducibility

The runner normalizes only volatile unittest wall-clock duration and fixes ZIP
metadata. Compiler artifacts, diagnostics, native results, generated matrices,
project- and benchmark-contract reports, pinned dependency versions, and
reviewer reports are retained in the GitHub Evidence bundle. Each completed
capability records exact-head and repeated-run digests on its owning PR and
issue.
