# Proof Status — v0.7.0

## Passed locally before the exact GitHub gate

- unit/integration suite: **51/51**
- Agent B release-blocking review: **51/51**
- all v0.6 structured-mutation regressions: passed
- all v0.5 aggregate/layout/C-ABI regressions: passed
- all v0.4 arithmetic/control-flow regressions: passed

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
different absolute root produced the same byte-for-byte Evidence ZIP:

```text
2d22975825266171713bedf77150b27df59015d338204a4d5908ae7a7c4a939e
```

The runner normalizes only volatile unittest wall-clock duration and fixes ZIP
metadata. Compiler artifacts, diagnostics, native results, generated matrices,
and reviewer reports remain inside the archive.
