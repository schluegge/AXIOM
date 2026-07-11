# Roadmap Amendment 003 — Checked `i32` Semantics

## Trigger

Axiom v0.3.0 proved mutable locals and loops, but direct Python arithmetic and
raw LLVM `sdiv`/`srem` did not establish identical edge-case semantics.

## Change

Axiom v0.4.0 defines checked `i32` as the current default arithmetic mode and
adds a profile-provided panic boundary.

## Delivered

- compile-time `i32` literal range validation
- integer-only truncating signed division
- dividend-sign remainder semantics
- checked add/sub/mul
- explicit division/remainder zero guards
- explicit `INT_MIN / -1` division/remainder guards
- LLVM signed overflow intrinsics
- structured panic identities and stable reference runtime codes
- panic-effect reporting
- interpreter/native differential tests for all fault classes

## Roadmap impact

This closes the arithmetic-semantics blocker identified after Amendment 002.
It does not complete the broader type system. The next feature-first slice is
aggregate data layout: fixed-size arrays and structs with an inspectable layout
contract, while preserving the checked scalar arithmetic oracle.
