# Roadmap Amendment 005 — Structured L-Value Mutation

Status: implemented and sandbox-proven  
Version: 0.6.0

## Trigger

AXIOM v0.5.0 supported aggregate values, reads, whole-value assignment, layout,
and simple C ABI proof, but could not update a field or array element directly.
That gap blocked the path toward references, borrowing, direct memory APIs, and
useful mutable data structures.

## Added capability

- expression-shaped assignment targets
- field writes
- fixed-array element writes
- nested field/index combinations
- dynamic checked write indices
- direct LLVM subobject stores
- structured write facts in HIR, symbols, effects, and ownership documents

## Preserved laws

- root mutability remains explicit through `var`
- aggregates remain value types
- dynamic indexing remains checked
- RHS evaluation precedes l-value path evaluation
- interpreter/native differential execution remains mandatory
- unsafe pointer or reference semantics are not implied

## Exit evidence

- 40 unit/integration tests
- 42 deterministic Agent B checks
- 24 interpreter/native differential cases
- 33 invalid fixtures
- 8 generated valid writes and 4 generated OOB writes
- repeated and clean-root Evidence archives byte-identical

## Next dependency

The next safe systems step is not arbitrary pointer syntax. It is a formal
place-expression and reference model built on this proven l-value layer:

1. shared references
2. exclusive references
3. borrow duration and alias rules
4. reference parameters
5. safe dereference
6. raw pointers only behind an explicit unsafe boundary
