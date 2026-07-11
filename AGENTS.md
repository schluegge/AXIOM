# AGENTS.md

## Project

AXIOM is an AI-first universal systems language. The active repository contains
an executed Python/LLVM semantics oracle that defines and tests the future Rust
bootstrap compiler.

## Required reading

1. `README.md`
2. `PROOF_STATUS.md`
3. `ARITHMETIC_SEMANTICS.md`
4. `AGGREGATE_SEMANTICS.md`
5. `MUTATION_SEMANTICS.md`
6. `REFERENCE_SEMANTICS.md`
7. `CONTEXT7_SOURCE_EVIDENCE.md`
8. the relevant roadmap amendment
9. implementation and tests for the affected stage

## Mandatory rules

- Do not invent language semantics or external API signatures.
- Use authoritative source evidence before LLVM, ABI, linker, runtime, LSP, or
  operating-system integration.
- Stop with `BLOCKED_SOURCE_MISSING` when required evidence is unavailable.
- Deliver one visible, vertically complete capability per normal iteration.
- Preserve interpreter/native differential tests.
- Add deterministic valid, invalid, boundary, and adversarial tests.
- Keep Agent A implementation and Agent B release-blocking review separate.
- Never claim a phase passed without executable evidence.
- AI may develop and inspect AXIOM; AI is not part of runtime semantics.
- Target-specific layout or ABI facts must name the proven target.
- A green test may not be obtained by weakening a valid critic assertion.
- Safe references must remain non-null and non-forgeable.
- Borrow rules are frontend semantics; do not infer safety from LLVM pointer
  acceptance.
- Conservative rejection is preferable to unsound alias acceptance.

## Verification

```bash
python3 run_repo_proof.py
```

The command must produce a passing manifest and Evidence ZIP. Generated
binaries and archives belong in Evidence artifacts, not source commits.
