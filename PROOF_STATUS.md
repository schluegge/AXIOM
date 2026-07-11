# Proof Status — v0.7.0

Proven target: `x86_64-unknown-linux-gnu`  
Current milestone: M1 AXIOM-Bench seed and preregistration

## Contract-indexed proven features

The following IDs are the complete public proven-feature claim surface. They are
checked against `contracts/project.json` by `tools/check_project_contract.py`.

<!-- AXIOM-PROJECT-CONTRACT:FEATURES:BEGIN -->
- `core.vertical-pipeline` — source-to-native vertical pipeline and deterministic compiler documents.
- `language.mutable-control-flow` — explicit mutable locals, nested mutation, branches, and loops.
- `arithmetic.checked-i32` — checked signed arithmetic and stable fault behavior.
- `data.aggregates-fixed-arrays` — structs, fixed arrays, checked indexing, layout, and narrow C ABI proof.
- `mutation.structured-lvalues` — structured field/index assignment with specified evaluation order.
- `memory.scoped-references` — non-null scoped references and conservative lexical borrow checking.
<!-- AXIOM-PROJECT-CONTRACT:FEATURES:END -->

## Completed M0 release-blocking proof

The project-contract gate is part of the canonical repository proof and runs
before the ordinary test suite and Agent B review.

M0 proof dimensions:

- project contract: **passed**, 6 current features, 14 deferred features, 0 findings
- unit/integration suite: **65/65**
- Agent B release-blocking review: **59/59**
- interpreter/native differential corpus: **38/38**
- stable invalid fixture matrix: **52/52**
- complete pinned proof dependency closure: passed
- all v0.6 structured-mutation regressions: passed
- all v0.5 aggregate/layout/C-ABI regressions: passed
- all v0.4 arithmetic/control-flow regressions: passed

PR #27 passed the exact-head proof twice. Both independently generated inner
Evidence archives were byte-identical:

```text
6f615e62c6a3347792ea4d9611904498512f53a3359dd84707c9c0928880bbeb
```

## Project-contract proofs

- Draft 2020-12 schema checked explicitly with `Draft202012Validator`
- external schema references rejected before validator construction
- exact dependency pins verified against installed package versions
- every indexed repository path exists and remains inside the repository root
- current and deferred feature IDs are unique and disjoint
- every proven feature has normative semantics, tests, proof IDs, and a named target
- every source diagnostic family has exactly one feature owner
- README and proof-status feature claim blocks match the contract exactly
- project contract and v1 roadmap agree on the active milestone
- invalid pins, missing dependencies, version drift, broken paths, claim drift,
  duplicate diagnostic ownership, unsupported targets, and deferred-as-current
  mutations are release-blocking

## Scoped-reference proofs

- `&T`, `&mut T`, borrow expressions, dereference reads/writes
- shared aliases coexist
- mutable references provide exclusive access
- immutable-root mutable borrow rejection
- root reads/writes blocked during conflicting live borrows
- reference returns and aggregate storage rejected
- local reference lifetime ends at block boundary
- direct call borrows cover complete left-to-right argument evaluation
- existing `&mut` values cannot be copied into overlapping call loans
- inner nested-call loan releases before the next outer argument
- dynamic borrowed index executes once
- OOB reference formation matches panic identity/code 108
- struct-field and array-element references match interpreter/native execution
- LLVM uses `ptr`, stack/GEP addresses, `load`, and `store`
- LLVM contains no reference `inttoptr`, `ptrtoint`, or null construction
- ownership/symbol/effect documents expose borrow facts

## Conservative boundary

Borrow conflicts are tracked at whole-local-root granularity. Disjoint fields
of one struct are not simultaneously borrowable when either borrow conflicts at
the root. This is conservative and safe, not a field-sensitive lifetime proof.

## Not proven

- raw pointers, null pointers, pointer arithmetic, or `unsafe`
- reborrowing or non-lexical lifetimes
- lifetime parameters or reference returns
- reference fields/arrays
- slices or heap allocation
- owned-resource destruction semantics
- broad cross-platform ABI stability
- complete effect/capability system
- Rust bootstrap parity, self-hosting, GPU execution, or AXIOM 1.0

## Evidence reproducibility

The runner normalizes only volatile unittest wall-clock duration and fixes ZIP
metadata. Compiler artifacts, diagnostics, native results, generated matrices,
project-contract reports, pinned dependency versions, and reviewer reports are
retained in the GitHub Evidence bundle. Each milestone records exact-head and
repeated-run digests on its owning PR and issue.
