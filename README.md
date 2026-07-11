# AXIOM v0.4.0 Reference Compiler

AXIOM is an AI-first universal systems language project. This repository currently contains an executed Python/LLVM semantic oracle for the bootstrap compiler.

The proven vertical path is:

```text
UTF-8 source
→ lexer
→ parser
→ versioned AST
→ canonical formatter
→ name resolution
→ type/effect checking
→ HIR and CFG
→ interpreter
→ checked LLVM IR
→ native runtime boundary
→ Clang executable
→ interpreter/native differential proof
```

The current subset includes:

- `i32` and `bool`
- functions and recursion
- immutable `let` and mutable `var`
- assignments and lexical block scopes
- `if` and `while`
- checked signed `i32` arithmetic
- stable arithmetic panic identities
- C-compatible function lowering
- `system` and `script` profile parsing

## Run the repository proof

Requirements:

- Python 3.11 or newer
- Clang with support for textual LLVM IR

From the repository root:

```bash
python3 run_repo_proof.py
```

The command runs the unit suite and interpreter/native differential corpus, then creates:

```text
evidence/AXIOM_REPO_PROOF_EVIDENCE.zip
```

Generated binaries, objects, WebAssembly files, and Evidence ZIPs are ignored by Git.

## Checked arithmetic

The current default is checked signed `i32`:

- out-of-range literals fail compilation with `AX-INT-0001`
- addition, subtraction, and multiplication panic on overflow
- division rounds toward zero
- remainder has the dividend sign
- division/remainder by zero panic
- `INT_MIN / -1` and `INT_MIN % -1` panic
- interpreter and native execution use the same panic identity and reference exit code

See `ARITHMETIC_SEMANTICS.md`.

## Development contract

Read `AGENTS.md` before changing compiler behavior. External LLVM, ABI, linker, runtime, and protocol APIs require authoritative source evidence before implementation.

## Proof boundary

This repository is an executable architecture and semantics oracle. It is not AXIOM 1.0 and does not replace the planned Rust bootstrap compiler. Current proven and unproven boundaries are recorded in `PROOF_STATUS.md`.
