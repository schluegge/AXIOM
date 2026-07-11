# Roadmap Amendment 004 — Structs, Fixed Arrays, and Layout Inspection

## Trigger

Issue #2 required the first aggregate-value slice after checked `i32`
arithmetic.

## Implemented capability

- struct declarations and literals
- fixed-size array types and literals
- nested aggregate values
- by-value function parameters and returns
- whole-aggregate local reassignment
- field and array reads
- compile-time literal-index rejection
- runtime checked dynamic indexing
- deterministic target layout documents
- simple struct-by-value C ABI proof

## Compiler stages changed

```text
lexer
parser / AST
formatter
name and type analysis
layout engine
HIR
interpreter
LLVM lowering
runtime fault model
CLI inspection
proof runner
Agent B review
```

## Gate evidence

- 31/31 unit and integration tests
- 33/33 independent deterministic Agent B checks
- generated aggregate matrix: 8 valid and 4 OOB programs
- native/interpreter parity for structs, arrays, aggregate return/assignment,
  nested arrays, and both bounds directions
- Axiom/Python, C, and LLVM layout agreement
- C-to-Axiom struct-by-value round trip
- deterministic aggregate compiler artifacts
- v0.4.0 arithmetic, mutation, loop, and scope regression suite retained

## Deliberately deferred

- aggregate subobject mutation
- slices
- references and borrowing
- heap ownership
- aggregate equality
- packed/explicit-layout structs
- unions, bitfields, flexible arrays, C++ ABI
- target-independent ABI claims
