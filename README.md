# AXIOM v0.7.0 Reference Compiler

AXIOM is an AI-first universal systems language project. This repository
contains an executed Python/LLVM semantic oracle for the planned Rust bootstrap
compiler.

The current vertical path is:

```text
UTF-8 source
→ lexer
→ parser and versioned AST
→ canonical formatter
→ name/type/effect/l-value/borrow analysis
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
- functions, recursion, `let`, `var`, lexical scopes
- `if` and `while`
- checked signed `i32` arithmetic
- structs and fixed-size arrays
- nested aggregate values and structured mutation
- checked dynamic indices for reads, writes, and borrows
- non-null scoped shared references `&T`
- non-null scoped mutable references `&mut T`
- borrow expressions, dereference reads, and dereference writes
- conservative lexical whole-root borrow checking
- reference parameters and immutable local reference bindings
- deterministic x86_64 Linux layout inspection
- simple C-compatible struct-by-value interoperability
- `system` and `script` profile parsing

Example:

```axiom
fn increment(value: &mut i32) -> i32 {
    *value = *value + 1;
    return *value;
}

fn main() -> i32 {
    var value: i32 = 41;
    return increment(&mut value);
}
```

## Run the complete repository proof

Requirements:

- Python 3.11+
- Clang with textual LLVM IR support

```bash
python3 run_repo_proof.py
```

The runner executes the full suite, separate Agent B process, native
differential corpus, invalid diagnostics, generated matrices, layout/ABI
checks, and reproducibility-sensitive Evidence generation. It creates:

```text
evidence/AXIOM_REPO_PROOF_EVIDENCE.zip
```

## Governing semantics

- `ARITHMETIC_SEMANTICS.md`
- `AGGREGATE_SEMANTICS.md`
- `MUTATION_SEMANTICS.md`
- `REFERENCE_SEMANTICS.md`
- `AGENTS.md`
- `PROOF_STATUS.md`
- `CONTEXT7_SOURCE_EVIDENCE.md`

## Proof boundary

This is an executable semantics oracle, not AXIOM 1.0. It does not yet prove
raw pointers, `unsafe`, reborrowing, non-lexical lifetimes, reference returns,
reference fields, slices, heap ownership, broad platform ABI stability, the
Rust bootstrap compiler, GPU execution, LSP, package ecosystem, or
self-hosting.
