# AXIOM v0.7.0 Reference Compiler

AXIOM is an AI-first systems language project. This repository currently
contains an executed Python/LLVM semantic oracle for the planned Rust bootstrap
compiler.

The first product target is deliberately focused:

```text
safe deterministic local CLI and structured-data tools
```

The canonical path to AXIOM v1.0 is defined by:

- `MVP_ROADMAP.md`
- `AI_FIRST_MVP_CONTRACT.md`
- `V1_TRACKING.md`
- machine-readable graph `roadmap/v1.json`
- GitHub program issue #9
- GitHub release gate #25

AXIOM will not claim to be measurably better for AI-driven development merely
because its own tests pass. The v1 claim requires a preregistered comparison
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

## Ordered path to v1.0

The current v0.7 semantics are frozen while the v1 foundation is established.
Every milestone has a dedicated GitHub issue and a mechanical exit gate:

1. M0 / #11 — project authority and v0.7 consistency;
2. M1 / #12 — contamination-aware AXIOM-Bench seed;
3. M2 / #13 — independent Rust bootstrap parity for v0.7;
4. M3 / #14 — stable compiler and agent interaction protocol;
5. M4 / #15 — scalar and explicit-conversion foundation;
6. M5 / #16 — algebraic variants, exhaustive matching, `Option`, and `Result`;
7. M6 / #17 — minimal monomorphized generics;
8. M7 / #18 — moves, ownership, and deterministic destruction;
9. M8 / #19 — bytes, slices, UTF-8 strings, and lists;
10. M9 / #20 — modules, visibility, manifest, and lockfile;
11. M10 / #21 — declared external effects and least-authority capabilities;
12. M11 / #22 — minimal standard library and deterministic JSON;
13. M12 / #23 — golden applications, Windows/Linux proof, and hardening;
14. M13 / #24 — frozen holdout benchmark and release decision;
15. V1 / #25 — stable `v1.0.0` release and compatibility gate.

Exactly one language milestone may be active at a time. The repository action
`.github/workflows/v1-roadmap-contract.yml` verifies the machine-readable graph
and live GitHub issue state. New capabilities and pull requests use mandatory
GitHub forms/templates that require source evidence, normative semantics,
vertical proof, benchmark deltas, and exact-PR Evidence.

User-visible raw pointers and general-purpose `unsafe` remain explicitly
post-v1 because they do not unlock the first product domain.

## Governing semantics and process

- `MVP_ROADMAP.md`
- `AI_FIRST_MVP_CONTRACT.md`
- `V1_TRACKING.md`
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

This is an executable semantics oracle, not AXIOM v1.0. It does not yet prove:

- the Rust bootstrap compiler;
- algebraic variants, `Option`, or `Result`;
- broad scalar and conversion semantics;
- generics;
- owned heap values or deterministic resource destruction;
- slices, bytes, or UTF-8 strings;
- modules, manifests, or lockfiles;
- local I/O capability enforcement;
- the v1 standard library or JSON support;
- Windows target parity;
- the external AI-first benchmark claim;
- raw pointers, `unsafe`, reborrowing, non-lexical lifetimes, or reference returns/fields;
- broad platform ABI stability;
- networking, concurrency, GPU execution, LSP, package ecosystem, self-hosting,
  or universal systems-language completeness.
