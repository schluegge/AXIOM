# Scoped Reference Semantics

Version: 0.7.0  
Proven target: `x86_64-unknown-linux-gnu`

## Purpose

AXIOM v0.7.0 introduces the first safe aliasing surface:

```axiom
&T
&mut T
&value
&mut value
*reference
*reference = new_value;
```

References are non-null, non-forgeable, lexically scoped, and non-escaping in
this slice. They are produced only from valid l-values whose storage already
exists.

## Types

`&T` is a shared reference. It permits reads of `T`.

`&mut T` is an exclusive mutable reference. It permits reads and writes of
`T`.

References may be function parameters and immutable local `let` bindings.
They may not be:

- function return types
- struct fields
- fixed-array elements
- mutable local reference bindings
- forged from integers or null
- reborrowed in v0.7

## Borrow roots

Borrow analysis is intentionally conservative. Every l-value borrow resolves
to its local root binding. Borrowing `holder.values[index]` therefore locks the
whole `holder` root for the lexical lifetime of the reference.

This can reject programs that a future field-sensitive borrow checker could
accept. It must not accept unsafe aliasing merely for ergonomics.

## Shared-borrow law

Any number of shared borrows of one root may coexist.

While at least one shared borrow is live:

- the root may be read
- shared references may be copied and passed repeatedly
- the root may not be written
- the root may not be mutably borrowed

## Mutable-borrow law

A mutable borrow requires a `var` root.

While a mutable borrow is live:

- the root may not be read directly
- the root may not be written directly
- no second shared or mutable borrow may be created
- the mutable reference is the exclusive access path

A shared reference cannot be used as an assignment target.

## Lexical lifetime

A reference local remains live until the end of its declaring block. The
corresponding borrow is released when that block ends.

A direct borrow used as a call argument is temporary. It remains live through
the complete left-to-right evaluation of that call's argument list and is
released when the call expression finishes.

## Mutable-reference call loans

Passing an existing `&mut T` value to a function creates a temporary exclusive
loan of that reference for the complete call argument evaluation.

Consequences:

```axiom
f(reference, reference);   // rejected
f(reference, *reference);  // rejected
```

An inner call's temporary loan ends when that inner call completes:

```axiom
combine(bump(&mut value), &mut value); // accepted
```

An outer call's earlier mutable-reference argument remains loaned while later
arguments are evaluated:

```axiom
combine(reference, bump(reference)); // rejected
```

## Evaluation order

Call arguments evaluate left to right.

Borrow/index expressions evaluate exactly once. Dynamic array indices are
checked before a GEP, load, or store is executed.

Reference formation itself may therefore panic with
`array_index_out_of_bounds` / reference runtime code `108` when a dynamic
borrowed array index is invalid.

## Interpreter representation

The interpreter represents a reference as a non-null runtime location:

- environment/root binding
- ordered field/index path
- mutability bit

Dereference reads resolve that location. Mutable dereference writes rebuild
the nested value path and replace the root, preserving existing deep
copy-by-value isolation between independent aggregate values.

## LLVM lowering

References lower to opaque LLVM `ptr` values.

- local roots originate from `alloca`
- struct-field and array-element borrows use `getelementptr`
- reference parameters are `ptr`
- reference locals use pointer slots
- dereference reads use `load`
- dereference writes use `store`

The backend emits no `inttoptr`, `ptrtoint`, or null reference construction for
this language surface. Calls are ordinary calls, not tail calls, when local
stack storage is borrowed.

Frontend borrow analysis enforces exclusivity. The current backend does not
claim `noalias`-attribute optimization semantics.

## Stable diagnostics

```text
AX-BORROW-0001  mutable borrow of immutable root
AX-BORROW-0002  shared borrow conflicts with live mutable borrow
AX-BORROW-0003  mutable borrow conflicts with another live borrow
AX-BORROW-0004  direct root read during mutable borrow
AX-BORROW-0005  direct root write while a borrow is live
AX-BORROW-0006  write through shared reference
AX-BORROW-0007  reborrowing is outside the v0.7 subset
AX-BORROW-0008  same mutable reference passed more than once to one call
AX-BORROW-0009  mutable reference used again while its call loan is live
AX-REF-0001     reference return type is forbidden
AX-REF-0002     reference storage inside aggregate is forbidden
AX-REF-0003     reference value may not escape through return
AX-REF-0004     mutable local reference binding is forbidden
AX-REF-0005     local reference must be initialized by a borrow expression
AX-REF-0006     dereference requires a reference
```

## Non-goals

This slice does not establish:

- raw pointers, null pointers, or pointer arithmetic
- `unsafe`
- reference returns or lifetime parameters
- non-lexical lifetimes
- field-sensitive disjoint borrowing
- reborrowing
- references stored in aggregates
- slices
- heap allocation
- interior mutability
- atomics or volatile access
