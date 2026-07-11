# AXIOM v0.5.0 Reference Compiler

AXIOM is an AI-first universal systems language project. This repository
contains an executed Python/LLVM semantic oracle for the planned Rust bootstrap
compiler.

The current vertical path is:

```text
UTF-8 source
→ lexer
→ parser and versioned AST
→ canonical formatter
→ name/type/effect analysis
→ target layout engine
→ HIR and CFG
→ interpreter
→ checked LLVM IR
→ native runtime boundary
→ Clang executable
→ interpreter/native differential proof
```

## Current language subset

- `i32` and `bool`
- functions, recursion, `let`, `var`, assignment, lexical scopes
- `if` and `while`
- checked signed `i32` arithmetic
- structs and fixed-size arrays
- nested aggregate values
- aggregate parameters and returns by value
- field and index reads
- checked dynamic array indexing
- deterministic x86_64 Linux layout inspection
- simple C-compatible struct-by-value interoperability
- `system` and `script` profile parsing

## Run the complete repository proof

Requirements:

- Python 3.11+
- Clang with textual LLVM IR support

```bash
python3 run_repo_proof.py
```

The runner executes the complete test suite, the separate Agent B adversarial
review, the interpreter/native differential corpus, invalid diagnostics, and
layout inspection. It creates:

```text
evidence/AXIOM_REPO_PROOF_EVIDENCE.zip
```

## Inspect layout

```bash
python3 -m axiom_proof.cli explain layout examples/layout.ax Mixed
```

The command emits deterministic JSON with size, alignment, offsets, padding,
array stride, target, and representation identity.

## Governing semantics

- `ARITHMETIC_SEMANTICS.md`
- `AGGREGATE_SEMANTICS.md`
- `AGENTS.md`
- `PROOF_STATUS.md`
- `CONTEXT7_SOURCE_EVIDENCE.md`

## Proof boundary

This is an executable architecture and semantics oracle, not AXIOM 1.0. It
does not yet prove the Rust bootstrap compiler, full ownership/lifetimes,
slices, heap allocation, broad platform ABI stability, GPU execution, LSP,
package ecosystem, or self-hosting.
