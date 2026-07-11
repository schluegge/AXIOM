# Proof Status — v0.7.0

Proven target: `x86_64-unknown-linux-gnu`  
Current milestone: M0 project authority and consistency gate

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

## Last released v0.7 proof before M0

- unit/integration suite: **51/51**
- Agent B release-blocking review: **51/51**
- all v0.6 structured-mutation regressions: passed
- all v0.5 aggregate/layout/C-ABI regressions: passed
- all v0.4 arithmetic/control-flow regressions: passed

The M0 pull request must produce a new exact-head manifest containing the
project-contract result. Until that run passes, this section remains historical
rather than a claim that M0 itself is complete.

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

Two complete runs in the original checkout and one cache-free run from a
different absolute root produced the same byte-for-byte pre-M0 Evidence ZIP:

```text
2d22975825266171713bedf77150b27df59015d338204a4d5908ae7a7c4a939e
```

The runner normalizes only volatile unittest wall-clock duration and fixes ZIP
metadata. Compiler artifacts, diagnostics, native results, generated matrices,
contract reports, and reviewer reports remain inside the archive.
