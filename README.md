# AXIOM v0.6.0 Reference Compiler

AXIOM is an AI-first universal systems language project. This repository
contains an executed Python/LLVM semantic oracle for the planned Rust bootstrap
compiler.

The current vertical path is:

```text
UTF-8 source
→ lexer
→ parser and versioned AST
→ canonical formatter
→ name/type/effect/l-value analysis
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
- nested aggregate values
- aggregate parameters and returns by value
- field and index reads
- whole-value, field, array-element, and nested structured assignment
- checked dynamic indices for reads and writes
- deterministic x86_64 Linux layout inspection
- simple C-compatible struct-by-value interoperability
- `system` and `script` profile parsing

Example:

```axiom
struct Holder {
    values: [[i32; 2]; 2],
}

fn main() -> i32 {
    var holder: Holder = Holder { values: [[1, 2], [3, 4]] };
    let row: i32 = 1;
    holder.values[row][0] = 35;
    return holder.values[0][0] + holder.values[1][0] + holder.values[1][1];
}
```

## Run the complete repository proof

Requirements:

- Python 3.11+
- Clang with textual LLVM IR support

```bash
python3 run_repo_proof.py
```

The runner executes the test suite, separate Agent B process, differential
corpus, invalid diagnostics, layout/ABI checks, generated matrices, and
reproducibility-sensitive evidence generation. It creates:

```text
evidence/AXIOM_REPO_PROOF_EVIDENCE.zip
```

## Inspect layout

```bash
python3 -m axiom_proof.cli explain layout examples/layout.ax Mixed
```

## Governing semantics

- `ARITHMETIC_SEMANTICS.md`
- `AGGREGATE_SEMANTICS.md`
- `MUTATION_SEMANTICS.md`
- `AGENTS.md`
- `PROOF_STATUS.md`
- `CONTEXT7_SOURCE_EVIDENCE.md`

## Proof boundary

This is an executable architecture and semantics oracle, not AXIOM 1.0. It
does not yet prove the Rust bootstrap compiler, references/borrowing, full
ownership/lifetimes, slices, heap allocation, broad platform ABI stability,
GPU execution, LSP, package ecosystem, or self-hosting.
