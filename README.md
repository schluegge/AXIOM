# AXIOM v0.7.0 Reference Compiler

AXIOM is an AI-first systems language project. This repository currently
contains an executed Python/LLVM semantic oracle for the planned Rust bootstrap
compiler.

The first product target is deliberately focused:

```text
safe deterministic local CLI and structured-data tools
```

The canonical path to that product is defined by:

- `MVP_ROADMAP.md`
- `AI_FIRST_MVP_CONTRACT.md`
- tracking issue #9

AXIOM will not claim to be measurably better for AI-driven development merely
because its own tests pass. The MVP claim requires a preregistered comparison
against Rust, Zig, and Go with preserved prompts, failures, traces, hidden tests,
and statistical evidence.

The current vertical compiler path is:

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

## Current implemented language subset

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

## Current proof

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

## MVP direction

The current v0.7 semantics are frozen while the MVP foundation is established.
The ordered roadmap is:

1. canonical project/document contracts and v0.7 consistency proof;
2. contamination-aware benchmark seed;
3. Rust bootstrap parity for v0.7;
4. stable compiler/agent interaction protocol;
5. complete scalar and conversion foundation;
6. algebraic variants, exhaustive matching, `Option`, and `Result`;
7. minimal generics;
8. moves, ownership, and deterministic destruction;
9. bytes, slices, UTF-8 strings, and lists;
10. modules, visibility, manifest, and lockfile;
11. declared external effects and capabilities;
12. minimal standard library and JSON;
13. complete Windows/Linux golden applications;
14. frozen holdout benchmark and release decision.

Exactly one language capability may be active at a time. User-visible raw
pointers and general-purpose `unsafe` are intentionally post-MVP because they do
not unlock the first product domain.

## Governing semantics and process

- `MVP_ROADMAP.md`
- `AI_FIRST_MVP_CONTRACT.md`
- `ROADMAP_AMENDMENT_007.md`
- `ARITHMETIC_SEMANTICS.md`
- `AGGREGATE_SEMANTICS.md`
- `MUTATION_SEMANTICS.md`
- `REFERENCE_SEMANTICS.md`
- `AGENTS.md`
- `PROOF_STATUS.md`
- `CONTEXT7_SOURCE_EVIDENCE.md`
- `CONTEXT7_MVP_DESIGN_EVIDENCE.md`

## Current proof boundary

This is an executable semantics oracle, not the AXIOM MVP and not AXIOM 1.0. It
does not yet prove:

- the Rust bootstrap compiler;
- algebraic variants, `Option`, or `Result`;
- broad scalar and conversion semantics;
- generics;
- owned heap values or deterministic resource destruction;
- slices, bytes, or UTF-8 strings;
- modules, manifests, or lockfiles;
- local I/O capability enforcement;
- the MVP standard library or JSON support;
- Windows target parity;
- the external AI-first benchmark claim;
- raw pointers, `unsafe`, reborrowing, non-lexical lifetimes, or reference
  returns/fields;
- broad platform ABI stability;
- networking, concurrency, GPU execution, LSP, package ecosystem, self-hosting,
  or AXIOM 1.0.
