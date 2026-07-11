# Roadmap Amendment 001 — Sandbox Vertical Proof

## Trigger

Local Windows evidence repeatedly required user execution. The user required
that the project first run autonomously in the assistant sandbox until every
core compiler layer had been exercised at least once.

## Decision

Add an executable reference prototype that proves a thin path through every
core compiler transformation before continuing broad phase implementation.

## Effect

The following architectural risks are now reduced:

- parser/AST shape is executable rather than purely documentary
- semantic diagnostics have stable codes
- HIR exists as structured data
- interpreter and native backend have an independent differential oracle
- LLVM IR syntax and Clang integration are exercised
- C ABI, script profile, WebAssembly artifact, and freestanding object paths
  have at least one concrete proof

## Non-effect

This amendment does not mark the Rust Phase 1 gate as passed and does not mark
later roadmap phases complete. A thin proof is not equivalent to production
coverage, soundness, platform support, or Axiom 1.0.

## Next implementation direction

Use the sandbox prototype as the executable semantic oracle while porting the
same stage contracts into the Rust bootstrap compiler. Each Rust phase must
match the oracle and then replace prototype authority for that phase.
