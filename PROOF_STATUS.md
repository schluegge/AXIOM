# Proof Status — v0.6.0

## Passed in the sandbox

- unit/integration suite: **40/40**
- Agent B release-blocking review: **42/42**
- interpreter/native differential corpus: **24/24**
- stable invalid fixture matrix: **33/33**
- generated l-value matrix: **8 valid + 4 OOB**
- Python bytecode compilation: passed
- all v0.5.0 aggregate/layout/C-ABI regressions: passed
- all v0.4.0 arithmetic/control-flow regressions: passed

## Structured mutation proofs

- assignment target is a structured AST, HIR, and symbol object
- whole binding, field, array element, and nested writes
- immutable root rejection for `let` and parameters
- non-l-value temporary rejection
- exact assigned-leaf type checking
- dynamic write bounds check before LLVM GEP and store
- panic identity `array_index_out_of_bounds`, code `108`
- RHS fault precedes l-value bounds fault
- each dynamic index expression evaluated exactly once
- copy-by-value aggregates remain independent after subobject mutation
- LLVM stores directly to the leaf pointer without rewriting the whole aggregate
- structured write facts appear in symbols, effects, HIR, and ownership output

## Retained aggregate proofs

- structs/fixed arrays across lexer → parser → AST → formatter → semantics →
  HIR/CFG → interpreter → LLVM → Clang
- nested aggregates and by-value parameters/returns
- deterministic layout JSON
- Axiom layout == C layout == LLVM GEP layout on x86_64 Linux
- simple C ABI struct-by-value round trip

## Not proven

- references, borrowing, or owned-resource semantics
- slices or pointer syntax
- heap allocation
- packed layouts or broad cross-platform ABI stability
- complete effect/capability system
- Rust bootstrap parity
- WebAssembly runtime execution
- bare-metal execution in emulator/hardware
- GPU execution
- LSP, package ecosystem, self-hosting, or Axiom 1.0

## Evidence reproducibility

Two complete runs in the original checkout and one cache-free run from a
different absolute root produced the same byte-for-byte Evidence ZIP:

```text
a9c52dd90db9ff2b7b2c23bcd4d75683cf07a84a39e184c49807c8c5c716a4db
```

The runner normalizes only volatile unittest wall-clock duration and fixes ZIP
metadata. Compiler artifacts, diagnostics, native results, layouts, generated
matrices, and reviewer reports remain inside the archive.
