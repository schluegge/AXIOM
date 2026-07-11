# Roadmap Amendment 006 — Scoped References

Version: 0.7.0

## Trigger

AXIOM v0.6.0 could address and mutate structured local storage internally, but
source programs could not pass a safe alias to a function. References are the
next required bridge toward ownership, lifetimes, raw pointers, and hardware
APIs.

## Decision

Introduce a deliberately restricted safe reference core before raw pointers:

- `&T` and `&mut T`
- borrow and dereference expressions
- dereference writes through `&mut`
- function parameters and immutable local reference bindings
- lexical, non-escaping lifetimes
- conservative whole-root conflict analysis

## Why this order

Directly introducing raw pointers would bypass the safety model before the
compiler can express and test legal aliasing. This slice first proves a
non-null, non-forgeable reference path from source through borrow analysis,
interpreter locations, LLVM pointers, and native execution.

## Vertical acceptance gate

The slice is complete only when:

- parser, AST, formatter, types, HIR, symbols, effects, and ownership agree
- shared and mutable aliasing run identically in interpreter and native code
- field/array subobject borrows lower through GEP
- dynamic borrowed indices execute once and are checked before GEP
- borrow conflicts and escapes emit stable diagnostics
- mutable-reference call loans cover the whole argument evaluation
- generated reference programs pass
- all v0.6 regressions remain green
- exact GitHub PR checkout produces passing Evidence

## Deferred work

- reborrowing and non-lexical lifetimes
- partial/field-sensitive borrowing
- reference returns and explicit lifetime parameters
- reference fields and arrays
- raw pointers and `unsafe`
- slices and owned heap values
