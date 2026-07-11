# Agent A — Implementer Report

Role: feature implementation  
Version: 0.4.0  
Isolation rule: Agent A does not approve its own release gate.

## Feature

Define and implement exact checked `i32` arithmetic semantics across the
semantic analyzer, interpreter, LLVM backend, runtime boundary, and evidence
pipeline.

## Compiler stages changed

- literal range validation
- type/effect facts
- interpreter arithmetic
- LLVM arithmetic lowering
- native runtime link boundary
- differential proof driver
- unit/integration tests
- invalid and adversarial corpus

## New stable diagnostics

```text
AX-INT-0001          integer literal outside i32 range
AX-RUNTIME-INT-0001  add/sub/mul overflow
AX-RUNTIME-INT-0002  division by zero
AX-RUNTIME-INT-0003  signed division overflow
AX-RUNTIME-INT-0004  remainder by zero
AX-RUNTIME-INT-0005  signed remainder overflow
```

## Implemented semantics

- signed `i32` range only
- checked `+`, `-`, `*`
- signed `/` rounds toward zero
- `%` has the sign of the dividend
- divide/remainder by zero panic
- `INT_MIN / -1` and `INT_MIN % -1` panic
- all checked arithmetic sites expose the `panic` effect

## LLVM strategy

- `llvm.sadd.with.overflow.i32`
- `llvm.ssub.with.overflow.i32`
- `llvm.smul.with.overflow.i32`
- `extractvalue` for result/overflow flag
- explicit guards before `sdiv` and `srem`
- external `axiom_panic_i32` runtime boundary

## Handoff to Agent B

Agent B must independently attempt to falsify:

- literal range enforcement
- every overflow class
- divide/remainder by zero
- `INT_MIN / -1` and `% -1`
- negative division and remainder semantics
- panic identity equality between interpreter and native execution
- panic effect visibility
- LLVM use of checked intrinsics and pre-operation division guards
- prior loop/mutation and determinism guarantees
