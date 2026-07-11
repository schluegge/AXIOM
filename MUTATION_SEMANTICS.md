# Structured Mutation Semantics

Version: 0.6.0  
Proven target: `x86_64-unknown-linux-gnu`

## 1. Purpose

AXIOM v0.6.0 extends assignment from whole local bindings to structured
l-values while retaining explicit local mutability and aggregate value
semantics.

Supported targets:

```axiom
variable = value;
record.field = value;
array[index] = value;
record.array[row][column] = value;
```

## 2. L-value grammar

An assignment target is semantically valid only when it is built from:

```text
NameExpr
FieldExpr(lvalue, field)
IndexExpr(lvalue, index_expression)
```

Calls, literals, binary expressions, struct temporaries, array temporaries, and
other r-values are not assignable. They produce `AX-MUT-0002`.

The parser preserves the entire target as an expression-shaped AST. It does not
collapse the target to a string name.

## 3. Mutable root law

Every structured target resolves to one root local binding.

The root must be declared with `var`. Parameters and `let` bindings are
immutable, including all of their subobjects.

```axiom
let pair: Pair = Pair { left: 1, right: 2 };
pair.left = 3; // AX-MUT-0001
```

Mutability is not inferred from the leaf field or array element. It is a
property of the root storage binding.

## 4. Type law

The assigned value must have exactly the leaf l-value type.

- struct field type comes from the declared struct definition
- array element type comes from `[Element; Length]`
- no implicit conversions are introduced

A mismatch produces `AX-TYPE-0011`.

## 5. Evaluation order

Assignment evaluates in this order:

1. right-hand value
2. l-value path from root to leaf, left to right
3. bounds checks for each dynamic index as encountered
4. final store/update

Each dynamic index expression is evaluated exactly once.

Consequently, in:

```axiom
values[index] = 1 / 0;
```

checked division failure occurs before an out-of-bounds target failure.
Interpreter and LLVM/native execution are differentially tested for this rule.

## 6. Array write bounds

Constant indices are checked during semantic analysis. An invalid constant
index produces `AX-INDEX-0001`.

Dynamic indices are checked at runtime:

```text
index < 0 OR index >= length
```

Failure identity:

```text
array_index_out_of_bounds
reference runtime code 108
```

LLVM emits the lower/upper guard before the dynamic `getelementptr`, and the
scalar `store` occurs only on the success path.

## 7. Interpreter value update

Structs and arrays remain immutable value objects inside the reference
interpreter. A structured write:

1. resolves the root and all selectors exactly once
2. functionally rebuilds only the path from the modified leaf to the root
3. replaces the mutable root binding with the rebuilt value

This preserves copy-by-value isolation. Mutating one copied aggregate does not
mutate another copy.

## 8. LLVM lowering

Local aggregate roots already have stack storage. The backend lowers a
structured target to a pointer:

- root name → existing storage slot
- field → constant-index struct `getelementptr`
- array element → array `getelementptr`
- nested target → chained GEP operations

The assigned scalar or aggregate leaf value is stored directly through that
pointer. The backend does not rewrite unrelated fields or elements for a
subobject write.

Struct field indices are constant `i32` values. Array indices may be dynamic.
This follows the official LLVM GEP contract captured in
`CONTEXT7_SOURCE_EVIDENCE.md`.

## 9. Structured compiler facts

HIR stores the target as a normal expression tree.

Symbol output identifies:

```text
assignment_root
field_write
index_write
```

Effect facts count:

```text
field_writes
index_writes
bounds_check_sites
panic_sites
```

Ownership output states that structured l-values are enabled while references,
borrows, and owned-resource semantics remain absent.

## 10. Stable diagnostics

```text
AX-MUT-0001     immutable root binding
AX-MUT-0002     target is not an l-value
AX-TYPE-0011    assigned value type mismatch
AX-STRUCT-0008  field target base is not a struct
AX-STRUCT-0009  unknown struct field
AX-INDEX-0001   constant index out of bounds
AX-INDEX-0002   index target base is not an array
AX-INDEX-0003   index is not i32
```

## 11. Non-goals

This slice does not add:

- references or borrowing
- pointer syntax
- slices
- heap allocation
- mutation through function-return temporaries
- compound assignment operators
- destructuring assignment
- packed structures or unions
- concurrency or atomic mutation
