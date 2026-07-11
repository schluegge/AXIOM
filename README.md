# Axiom Sandbox Vertical Proof v0.4.0

This repository contains an executable reference compiler slice proving checked `i32` arithmetic through every implemented stage:

```text
UTF-8 source
→ lexer
→ parser
→ versioned AST
→ canonical formatter
→ name resolution
→ type and effect checking
→ HIR and CFG
→ interpreter
→ checked LLVM IR
→ native runtime boundary
→ Clang executable
→ interpreter/native differential proof
```

The current reference subset also preserves proofs for mutable locals, lexical blocks, `while`, recursion, C ABI, script profile, WebAssembly artifact generation, and a RISC-V freestanding object.

Run from the repository root:

```bash
python3 run_proof.py
```

Generated evidence:

```text
evidence/AXIOM_SANDBOX_VERTICAL_PROOF_EVIDENCE.zip
```

## Checked arithmetic

The current default arithmetic mode is checked signed `i32`:

- out-of-range literals fail compilation
- addition, subtraction, and multiplication panic on overflow
- division rounds toward zero
- remainder has the dividend sign
- division/remainder by zero panic
- `INT_MIN / -1` and `INT_MIN % -1` panic
- interpreter and native execution use the same panic identities

See `ARITHMETIC_SEMANTICS.md`.

## Review split

- Agent A owns implementation and the regular test suite.
- Agent B is a separate deterministic review process with a read-only charter and release-blocking adversarial checks.
- Agent B is not claimed to be a second language-model instance.

## Proof boundary

This is an executed architecture and semantics oracle. It is not Axiom 1.0 and does not replace the planned Rust bootstrap compiler.
