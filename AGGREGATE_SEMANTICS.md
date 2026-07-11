# Axiom Struct and Fixed-Array Semantics

Version: 0.5.0  
Status: Executed reference semantics

## Scope

Axiom v0.5.0 adds value-semantic structs and fixed-size arrays to the executed
Python/LLVM semantic oracle.

Supported:

```axiom
struct Pair {
    left: i32,
    right: i32,
}

let pair: Pair = Pair { left: 20, right: 22 };
let values: [i32; 3] = [4, 8, 15];
return pair.left + values[1];
```

Structs and arrays may be:

- local `let` or `var` values
- assigned as whole values to a mutable binding
- passed to functions by value
- returned from functions by value
- nested inside other structs and arrays
- read through field and index expressions

Not implemented in this slice:

- field assignment such as `pair.left = 1`
- element assignment such as `values[index] = 1`
- slices, heap allocation, references, borrowing, unions, packed structs,
  bitfields, flexible arrays, or C++ ABI
- aggregate equality

## Struct identity and fields

A struct name is unique within a program. Field order is semantically relevant
for layout and ABI lowering. A struct literal names every field exactly once.
Field order in a literal does not change the declared layout.

Rejected conditions have stable diagnostics:

```text
AX-STRUCT-0001  duplicate struct declaration
AX-STRUCT-0002  duplicate field declaration
AX-STRUCT-0003  unknown struct literal type
AX-STRUCT-0004  duplicate struct literal field
AX-STRUCT-0005  unknown/extra literal field
AX-STRUCT-0006  missing literal field
AX-STRUCT-0007  field value type mismatch
AX-STRUCT-0008  field access on a non-struct value
AX-STRUCT-0009  unknown accessed field
AX-STRUCT-0010  empty struct outside the current layout subset
```

Recursive value types are rejected with `AX-TYPE-0014`. This includes direct
and indirect recursion through fixed arrays because no reference indirection
exists yet.

## Fixed arrays

A fixed-array type is written:

```text
[element_type; positive_length]
```

Examples:

```axiom
[i32; 4]
[Pair; 2]
[[i32; 3]; 2]
```

The length is part of the type. Length zero is rejected. An array literal has
one element type and an exact compile-time length. Empty array literals are not
inferable in the current subset.

Stable diagnostics:

```text
AX-ARRAY-0001  empty array literal has no inferable element type
AX-ARRAY-0002  fixed-array length mismatch
AX-ARRAY-0003  array element type mismatch
AX-ARRAY-0004  fixed-array length is not positive
AX-INDEX-0001  literal index is outside the array bounds
AX-INDEX-0002  index access on a non-array value
AX-INDEX-0003  index expression is not i32
```

## Index execution

A literal non-negative in-range index is lowered directly through LLVM
`extractvalue`.

A dynamic `i32` index is checked before address calculation:

```text
index < 0      -> array_index_out_of_bounds
index >= N     -> array_index_out_of_bounds
otherwise      -> access element
```

The stable panic identity and reference-runtime exit code are:

```text
array_index_out_of_bounds  108
```

The interpreter reports `AX-RUNTIME-INDEX-0001`. The LLVM backend branches to
`axiom_panic_i32(108)` before executing `getelementptr` or `load`.

A dynamic index contributes the `panic` effect and increments the structured
`bounds_check_sites` and `panic_sites` facts.

## Value and ownership model

Struct and fixed-array values use copy-by-value semantics in this reference
subset. Whole-value reassignment replaces the previous aggregate. No owned
resource type exists yet, so this does not establish the future ownership or
borrow model.

## Layout model

The first executed layout target is:

```text
x86_64-unknown-linux-gnu
```

Representation identifier:

```text
axiom_natural_c_compatible_subset_v0
```

Primitive layout used by the current target proof:

```text
bool  size 1  alignment 1
i32   size 4  alignment 4
```

Arrays:

```text
stride = element size rounded up to element alignment
total size = stride * length
alignment = element alignment
```

Structs:

1. each field starts at the next offset satisfying its alignment
2. fields remain in declaration order
3. struct alignment is the maximum field alignment
4. final size includes tail padding to struct alignment

`python -m axiom_proof.cli explain layout <source> <Type>` emits deterministic
JSON containing size, alignment, field offsets, padding, array stride, element
layout, target, and representation identifier.

## Executed layout/ABI evidence

The `Mixed` fixture is:

```text
bool flag
  3 bytes padding
 i32 count
Pair pair
[i32; 3] values
```

Proven layout:

```text
size       28
alignment   4
flag        0
count       4
pair        8
values     16
```

The same values are independently produced by:

- the Axiom layout engine
- a compiled C `sizeof`/`_Alignof`/`offsetof` probe
- an LLVM `getelementptr`/`ptrtoint` probe

A second proof compiles Axiom functions that return and consume `Pair` by value,
then calls them from C. `make_pair(20, 22)` followed by `sum_pair(pair)` returns
42. This proves the current simple struct-by-value C ABI path on the documented
target; it is not a blanket promise for every aggregate or platform ABI.

## v0.6 mutation extension

Structured field and fixed-array element mutation is now defined separately in `MUTATION_SEMANTICS.md`. Aggregate values remain copy-by-value; the extension adds mutable-root l-values rather than reference aliasing.
