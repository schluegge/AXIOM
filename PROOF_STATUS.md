# Proof Status — v0.5.0

## Passed in the sandbox

- unit/integration suite: **31/31**
- Agent B release-blocking review: **33/33**
- deterministic generated aggregate matrix: **8 valid + 4 OOB**
- Python bytecode compilation: passed
- clean interpreter/native aggregate differential: passed
- all v0.4.0 checked arithmetic and control-flow regressions: passed

## Aggregate proofs

- structs and arrays survive lexer → parser → AST → formatter → semantic
  analysis → HIR/CFG → interpreter → LLVM → Clang
- aggregate parameters, returns, local storage, and whole-value reassignment
- nested structs and nested arrays
- dynamic negative and upper-bound checks before LLVM GEP
- panic identity `array_index_out_of_bounds`, reference code `108`
- stable diagnostic matrix for declarations, literals, fields, arrays, indices,
  recursion, empty aggregates, and unsupported equality
- deterministic layout JSON and aggregate compiler outputs
- Axiom layout engine == C layout == LLVM GEP layout on x86_64 Linux
- C calls Axiom aggregate-return and aggregate-parameter functions by value

## Earlier retained proofs

- strict UTF-8 source loading and SHA-256
- exact token spans
- deterministic AST and canonical formatting
- names, scalar types, effects, HIR, CFG, ownership summary
- checked signed `i32` arithmetic and panic identities 101–107
- mutable locals, lexical scopes, assignments, `if`, `while`, recursion
- native x86_64 Clang build and interpreter/native differential execution
- script profile

## Not proven

- aggregate field or element mutation
- slices, references, borrowing, or owned-resource semantics
- explicit/packed layouts or broad cross-platform ABI stability
- complete effect/capability system
- Rust bootstrap parity
- WebAssembly runtime execution
- bare-metal execution in emulator/hardware
- GPU execution
- LSP, package ecosystem, self-hosting, or Axiom 1.0

## Evidence reproducibility

Two complete runs in the original checkout and a third run from a cache-free
copy at a different absolute path produced the same byte-for-byte Evidence ZIP:

```text
5ba6bc52f65188cf2082dbbc7802f332679e0527b2e135c6c8506f58e5ecc659
```

The runner normalizes only volatile unittest wall-clock duration and uses
fixed ZIP metadata. Source and compiler paths used by the proof are repo-relative.
Semantic output, command results, diagnostics, native hashes, and review reports
remain part of the archive.
