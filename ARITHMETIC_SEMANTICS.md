# Axiom Checked `i32` Arithmetic Semantics

Version: 0.4.0  
Status: Executed reference semantics

## Default mode

The current Axiom reference subset uses **checked signed 32-bit arithmetic**.

Every `i32` value is in the inclusive range:

```text
-2147483648 .. 2147483647
```

An integer literal outside that range is rejected with:

```text
AX-INT-0001
```

## Addition, subtraction, multiplication

`+`, `-`, and `*` produce the mathematical result when it is representable as
`i32`. Otherwise execution enters the arithmetic panic boundary.

Stable panic identities and reference-runtime exit codes:

```text
i32_add_overflow  101
i32_sub_overflow  102
i32_mul_overflow  103
```

The exit codes are the default system-profile reference runtime behavior. The
semantic event is the named arithmetic panic; another profile may supply a
different panic handler while preserving the panic identity.

## Division

Signed division rounds toward zero.

Examples:

```text
 7 / 3 =  2
-7 / 3 = -2
 7 / -3 = -2
```

Panic cases:

```text
divisor == 0                 → i32_divide_by_zero  (104)
-2147483648 / -1             → i32_divide_overflow (105)
```

## Remainder

The remainder satisfies:

```text
left == (left / right) * right + (left % right)
```

where division rounds toward zero. A non-zero remainder has the sign of the
dividend.

Example:

```text
-7 % 3 = -1
```

Panic cases:

```text
divisor == 0                 → i32_remainder_by_zero  (106)
-2147483648 % -1             → i32_remainder_overflow (107)
```

The second case is guarded explicitly because LLVM `srem` does not define this
overflow input safely for direct execution.

## Interpreter implementation

The interpreter uses integer-only algorithms. It does not convert operands to
floating point for signed division.

Runtime diagnostics:

```text
AX-RUNTIME-INT-0001  checked add/sub/mul overflow
AX-RUNTIME-INT-0002  division by zero
AX-RUNTIME-INT-0003  signed division overflow
AX-RUNTIME-INT-0004  remainder by zero
AX-RUNTIME-INT-0005  signed remainder overflow
```

## LLVM lowering

Checked addition, subtraction, and multiplication lower through:

```text
llvm.sadd.with.overflow.i32
llvm.ssub.with.overflow.i32
llvm.smul.with.overflow.i32
```

The result value and overflow bit are extracted. The overflow branch calls:

```llvm
call void @axiom_panic_i32(i32 <panic-code>)
unreachable
```

Signed division and remainder receive explicit zero and
`INT_MIN / -1` guards before `sdiv` or `srem` is emitted.

## Effect model

Every checked arithmetic site currently contributes the `panic` effect. The
structured effect document includes:

```text
checked_arithmetic_sites
panic_sites
effects: ["panic"]
```

## Deferred arithmetic modes

Not implemented yet:

- wrapping
- saturating
- explicitly unchecked
- arbitrary-width integers
- floating-point arithmetic
