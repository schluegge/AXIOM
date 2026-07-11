# AGENTS.md

## Project

AXIOM is an AI-first systems language project. The active repository contains
an executed Python/LLVM semantics oracle that defines and tests the future Rust
bootstrap compiler.

The current product target is the MVP defined in issue #9:

```text
safe deterministic local CLI and structured-data tools
```

Universal systems-language expansion remains a long-term direction, not a
license to develop unrelated domains in parallel.

## Planning authority

Current authority order:

1. normative semantic specifications;
2. machine-readable project/feature contracts when introduced;
3. `MVP_ROADMAP.md` for implementation sequence and scope;
4. `AI_FIRST_MVP_CONTRACT.md` for measurable product claims;
5. roadmap amendments/ADRs for historical rationale;
6. `README.md` as a checked summary.

Historical amendments do not override the current canonical roadmap unless a
new amendment also updates that roadmap.

## Required reading

1. `README.md`
2. `MVP_ROADMAP.md`
3. `AI_FIRST_MVP_CONTRACT.md`
4. `PROOF_STATUS.md`
5. `ARITHMETIC_SEMANTICS.md`
6. `AGGREGATE_SEMANTICS.md`
7. `MUTATION_SEMANTICS.md`
8. `REFERENCE_SEMANTICS.md`
9. `CONTEXT7_SOURCE_EVIDENCE.md`
10. `CONTEXT7_MVP_DESIGN_EVIDENCE.md`
11. the relevant roadmap amendment
12. implementation and tests for the affected stage

## Mandatory rules

- Do not invent language semantics or external API signatures.
- Use authoritative source evidence before LLVM, ABI, linker, runtime, standard
  library, file-format, benchmark-tool, or operating-system integration.
- Stop with `BLOCKED_SOURCE_MISSING` when required evidence is unavailable.
- Deliver one visible, vertically complete capability per normal iteration.
- Exactly one language capability may be active at a time.
- Supporting parallel work is limited to regressions, required source evidence,
  documentation consistency, proof parity, and the benchmark slice for the
  active capability.
- Every capability must state the real program it unlocks and a falsifiable
  AI-development hypothesis or an explicit non-AI product justification.
- Preserve interpreter/native differential tests.
- Preserve Python/Rust implementation independence when the Rust bootstrap is
  introduced; a shared semantic bug must not be hidden by shared implementation
  code.
- Add deterministic valid, invalid, boundary, adversarial, generated, and
  differential tests.
- Keep Agent A implementation and Agent B release-blocking review separate.
- Never claim a phase passed without executable evidence.
- Never claim AI-first superiority from internal tests, shorter syntax, one
  model, one prompt, or compiler success alone.
- Preserve all benchmark failures and historical benchmark versions.
- Do not weaken a preregistered benchmark gate after viewing holdout results.
- AI may develop and inspect AXIOM; AI is not part of runtime semantics.
- Target-specific layout or ABI facts must name the proven target.
- A green test may not be obtained by weakening a valid critic assertion.
- Safe references must remain non-null and non-forgeable.
- Borrow rules are frontend semantics; do not infer safety from LLVM pointer
  acceptance.
- Conservative rejection is preferable to unsound alias acceptance.
- Unknown symbols or imports may suggest only compiler-resolved existing names;
  never auto-install an undeclared package.
- Do not introduce a custom IDE, linker, debugger, package registry, backend, or
  orchestration framework before a current blocker proves it necessary.
- User-visible raw pointers and general-purpose `unsafe` remain post-MVP unless a
  reviewed roadmap amendment changes the canonical roadmap with new evidence.

## Required feature workflow

1. Define the current real-program blocker, AI failure class, falsifiable
   hypothesis, comparison behavior, and non-goals.
2. Capture authoritative source evidence and classify external components.
3. Write or update normative grammar, typing, evaluation, effect, ownership,
   runtime, diagnostic, formatter, target, and non-goal contracts.
4. Implement every affected compiler stage vertically.
5. Run all proof categories and previous regressions.
6. Add the benchmark delta without rewriting historical results.
7. Run separate Agent B review.
8. Produce exact-PR Evidence and a known-unproven list.

## Verification

Current repository proof:

```bash
python3 run_repo_proof.py
```

After the Rust bootstrap and MVP gates are introduced, use the canonical
commands named by `MVP_ROADMAP.md` and the repository workflow. The proof command
must produce a passing manifest and Evidence ZIP. Generated binaries, benchmark
raw outputs, and archives belong in Evidence or benchmark artifacts, not source
commits unless a specification explicitly requires a small fixture.
