# AGENTS.md

## Project

AXIOM is an AI-first universal systems language. The current repository contains an executed Python/LLVM semantic oracle and a Rust Phase 1 lexer reference.

## Required reading order

1. `README.md`
2. `PROOF_STATUS.md`
3. `ARITHMETIC_SEMANTICS.md`
4. `CONTEXT7_SOURCE_EVIDENCE.md`
5. `rust_phase1_reference/LANGUAGE_CONSTITUTION.md`
6. `rust_phase1_reference/AI_DEVELOPMENT_PROTOCOL.md`
7. the relevant specification and schemas

## Mandatory rules

- Do not invent language semantics or external API signatures.
- Use authoritative source evidence before implementing LLVM, ABI, linker, runtime, LSP, or operating-system integration.
- Stop with `BLOCKED_SOURCE_MISSING` when required evidence is unavailable.
- Deliver one visible, vertically complete language capability per normal iteration.
- Preserve interpreter/native differential tests.
- Add deterministic valid, invalid, boundary, and adversarial tests.
- Keep Agent A implementation and Agent B release-blocking review separate.
- Never claim a phase passed without executable evidence.
- AI may develop and inspect AXIOM; AI is not part of runtime semantics.
- Do not introduce a custom IDE, linker, debugger, package registry, or backend before a current blocker proves it necessary.

## Verification

From the repository root:

```bash
python3 run_proof.py
```

The command must generate a passing evidence manifest and Evidence ZIP. Generated binaries and archives are ignored by Git and belong in evidence artifacts, not source commits.
