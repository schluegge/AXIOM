# AGENTS.md

## Project

AXIOM is an AI-first universal systems language. The active repository contains an executed Python/LLVM semantic oracle used to define and test the future Rust bootstrap compiler.

## Required reading order

1. `README.md`
2. `PROOF_STATUS.md`
3. `ARITHMETIC_SEMANTICS.md`
4. `CONTEXT7_SOURCE_EVIDENCE.md`
5. the relevant roadmap amendment
6. the implementation and tests for the affected compiler stage

## Mandatory rules

- Do not invent language semantics or external API signatures.
- Use authoritative source evidence before implementing LLVM, ABI, linker, runtime, LSP, or operating-system integration.
- Stop with `BLOCKED_SOURCE_MISSING` when required evidence is unavailable.
- Deliver one visible, vertically complete language capability per normal iteration.
- Preserve interpreter/native differential tests.
- Add deterministic valid, invalid, boundary, and adversarial tests.
- Keep Agent A implementation and Agent B release-blocking review conceptually separate.
- Never claim a phase passed without executable evidence.
- AI may develop and inspect AXIOM; AI is not part of runtime semantics.
- Do not introduce a custom IDE, linker, debugger, package registry, or backend before a current blocker proves it necessary.

## Verification

From the repository root:

```bash
python3 run_repo_proof.py
```

The command must generate a passing manifest and Evidence ZIP. Generated binaries and archives belong in Evidence artifacts, not source commits.

## Change format

Every non-trivial change must state:

```text
GOAL
GOVERNING SEMANTICS
COMPILER STAGES CHANGED
VALID TESTS
INVALID/ADVERSARIAL TESTS
SOURCE EVIDENCE
PROOF RESULT
KNOWN UNPROVEN
```
