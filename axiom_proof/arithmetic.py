from __future__ import annotations

from dataclasses import dataclass

I32_MIN = -(2**31)
I32_MAX = 2**31 - 1

PANIC_ADD_OVERFLOW = 101
PANIC_SUB_OVERFLOW = 102
PANIC_MUL_OVERFLOW = 103
PANIC_DIVIDE_BY_ZERO = 104
PANIC_DIVIDE_OVERFLOW = 105
PANIC_REMAINDER_BY_ZERO = 106
PANIC_REMAINDER_OVERFLOW = 107
PANIC_INDEX_OUT_OF_BOUNDS = 108

PANIC_NAMES = {
    PANIC_ADD_OVERFLOW: "i32_add_overflow",
    PANIC_SUB_OVERFLOW: "i32_sub_overflow",
    PANIC_MUL_OVERFLOW: "i32_mul_overflow",
    PANIC_DIVIDE_BY_ZERO: "i32_divide_by_zero",
    PANIC_DIVIDE_OVERFLOW: "i32_divide_overflow",
    PANIC_REMAINDER_BY_ZERO: "i32_remainder_by_zero",
    PANIC_REMAINDER_OVERFLOW: "i32_remainder_overflow",
    PANIC_INDEX_OUT_OF_BOUNDS: "array_index_out_of_bounds",
}


@dataclass(frozen=True)
class ArithmeticFault(Exception):
    diagnostic_code: str
    panic_name: str
    exit_code: int
    message: str

    def __str__(self) -> str:
        return f"{self.diagnostic_code}: {self.message}"


def panic_name_for_exit_code(exit_code: int) -> str | None:
    return PANIC_NAMES.get(exit_code)


def require_i32(value: int, *, operation: str) -> int:
    if I32_MIN <= value <= I32_MAX:
        return value
    raise ValueError(f"{operation} received non-i32 value: {value}")


def _overflow_fault(operation: str, exit_code: int) -> ArithmeticFault:
    return ArithmeticFault(
        diagnostic_code="AX-RUNTIME-INT-0001",
        panic_name=PANIC_NAMES[exit_code],
        exit_code=exit_code,
        message=f"checked i32 {operation} overflow",
    )


def checked_add(left: int, right: int) -> int:
    result = require_i32(left, operation="add") + require_i32(right, operation="add")
    if not I32_MIN <= result <= I32_MAX:
        raise _overflow_fault("addition", PANIC_ADD_OVERFLOW)
    return result


def checked_sub(left: int, right: int) -> int:
    result = require_i32(left, operation="sub") - require_i32(right, operation="sub")
    if not I32_MIN <= result <= I32_MAX:
        raise _overflow_fault("subtraction", PANIC_SUB_OVERFLOW)
    return result


def checked_mul(left: int, right: int) -> int:
    result = require_i32(left, operation="mul") * require_i32(right, operation="mul")
    if not I32_MIN <= result <= I32_MAX:
        raise _overflow_fault("multiplication", PANIC_MUL_OVERFLOW)
    return result


def truncating_division(left: int, right: int) -> int:
    left = require_i32(left, operation="div")
    right = require_i32(right, operation="div")
    if right == 0:
        raise ArithmeticFault(
            diagnostic_code="AX-RUNTIME-INT-0002",
            panic_name=PANIC_NAMES[PANIC_DIVIDE_BY_ZERO],
            exit_code=PANIC_DIVIDE_BY_ZERO,
            message="checked i32 division by zero",
        )
    if left == I32_MIN and right == -1:
        raise ArithmeticFault(
            diagnostic_code="AX-RUNTIME-INT-0003",
            panic_name=PANIC_NAMES[PANIC_DIVIDE_OVERFLOW],
            exit_code=PANIC_DIVIDE_OVERFLOW,
            message="checked i32 division overflow",
        )
    quotient = abs(left) // abs(right)
    if (left < 0) != (right < 0):
        quotient = -quotient
    return quotient


def truncating_remainder(left: int, right: int) -> int:
    left = require_i32(left, operation="rem")
    right = require_i32(right, operation="rem")
    if right == 0:
        raise ArithmeticFault(
            diagnostic_code="AX-RUNTIME-INT-0004",
            panic_name=PANIC_NAMES[PANIC_REMAINDER_BY_ZERO],
            exit_code=PANIC_REMAINDER_BY_ZERO,
            message="checked i32 remainder by zero",
        )
    if left == I32_MIN and right == -1:
        raise ArithmeticFault(
            diagnostic_code="AX-RUNTIME-INT-0005",
            panic_name=PANIC_NAMES[PANIC_REMAINDER_OVERFLOW],
            exit_code=PANIC_REMAINDER_OVERFLOW,
            message="checked i32 remainder overflow",
        )
    quotient = truncating_division(left, right)
    return left - quotient * right
