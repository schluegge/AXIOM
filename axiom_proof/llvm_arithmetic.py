from __future__ import annotations

from .arithmetic import (
    PANIC_ADD_OVERFLOW,
    PANIC_DIVIDE_BY_ZERO,
    PANIC_DIVIDE_OVERFLOW,
    PANIC_INDEX_OUT_OF_BOUNDS,
    PANIC_MUL_OVERFLOW,
    PANIC_REMAINDER_BY_ZERO,
    PANIC_REMAINDER_OVERFLOW,
    PANIC_SUB_OVERFLOW,
)
from .llvm_model import FunctionContext, Storage
from .model import Node
from .type_system import parse_array_type


class LLVMArithmeticMixin:
    def emit_panic_block(
        self,
        context: FunctionContext,
        label: str,
        exit_code: int,
    ) -> None:
        context.lines.append(f"{label}:")
        context.lines.append(f"  call void @axiom_panic_i32(i32 {exit_code})")
        context.lines.append("  unreachable")

    def emit_checked_overflow(
        self,
        context: FunctionContext,
        intrinsic: str,
        left: str,
        right: str,
        exit_code: int,
    ) -> str:
        pair = context.register()
        value = context.register()
        overflow = context.register()
        fail_label = context.label("arith_fail")
        ok_label = context.label("arith_ok")
        context.lines.append(
            f"  {pair} = call {{i32, i1}} @{intrinsic}(i32 {left}, i32 {right})"
        )
        context.lines.append(f"  {value} = extractvalue {{i32, i1}} {pair}, 0")
        context.lines.append(f"  {overflow} = extractvalue {{i32, i1}} {pair}, 1")
        context.lines.append(f"  br i1 {overflow}, label %{fail_label}, label %{ok_label}")
        self.emit_panic_block(context, fail_label, exit_code)
        context.lines.append(f"{ok_label}:")
        return value

    def emit_checked_division(
        self,
        context: FunctionContext,
        left: str,
        right: str,
        *,
        remainder: bool,
    ) -> str:
        zero = context.register()
        is_min = context.register()
        is_negative_one = context.register()
        overflow = context.register()
        zero_fail = context.label("div_zero_fail" if not remainder else "rem_zero_fail")
        overflow_check = context.label("div_overflow_check" if not remainder else "rem_overflow_check")
        overflow_fail = context.label("div_overflow_fail" if not remainder else "rem_overflow_fail")
        ok_label = context.label("div_ok" if not remainder else "rem_ok")

        context.lines.append(f"  {zero} = icmp eq i32 {right}, 0")
        context.lines.append(f"  br i1 {zero}, label %{zero_fail}, label %{overflow_check}")
        self.emit_panic_block(
            context,
            zero_fail,
            PANIC_REMAINDER_BY_ZERO if remainder else PANIC_DIVIDE_BY_ZERO,
        )
        context.lines.append(f"{overflow_check}:")
        context.lines.append(f"  {is_min} = icmp eq i32 {left}, -2147483648")
        context.lines.append(f"  {is_negative_one} = icmp eq i32 {right}, -1")
        context.lines.append(f"  {overflow} = and i1 {is_min}, {is_negative_one}")
        context.lines.append(f"  br i1 {overflow}, label %{overflow_fail}, label %{ok_label}")
        self.emit_panic_block(
            context,
            overflow_fail,
            PANIC_REMAINDER_OVERFLOW if remainder else PANIC_DIVIDE_OVERFLOW,
        )
        context.lines.append(f"{ok_label}:")
        result = context.register()
        instruction = "srem" if remainder else "sdiv"
        context.lines.append(f"  {result} = {instruction} i32 {left}, {right}")
        return result

    def emit_dynamic_index(
        self,
        expression: Node,
        base_value: str,
        base_type: str,
        index_value: str,
        context: FunctionContext,
    ) -> tuple[str, str]:
        array = parse_array_type(base_type)
        if array is None:
            raise ValueError("dynamic index base is not an array")
        element_type, length = array
        llvm_array_type = self.llvm_type(base_type)
        slot = self.dynamic_slot_for(expression)
        context.lines.append(f"  store {llvm_array_type} {base_value}, ptr {slot}")

        negative = context.register()
        too_high = context.register()
        out_of_bounds = context.register()
        fail_label = context.label("index_fail")
        ok_label = context.label("index_ok")
        context.lines.append(f"  {negative} = icmp slt i32 {index_value}, 0")
        context.lines.append(f"  {too_high} = icmp sge i32 {index_value}, {length}")
        context.lines.append(f"  {out_of_bounds} = or i1 {negative}, {too_high}")
        context.lines.append(f"  br i1 {out_of_bounds}, label %{fail_label}, label %{ok_label}")
        self.emit_panic_block(context, fail_label, PANIC_INDEX_OUT_OF_BOUNDS)
        context.lines.append(f"{ok_label}:")
        element_ptr = context.register()
        result = context.register()
        context.lines.append(
            f"  {element_ptr} = getelementptr {llvm_array_type}, ptr {slot}, i32 0, i32 {index_value}"
        )
        context.lines.append(f"  {result} = load {self.llvm_type(element_type)}, ptr {element_ptr}")
        return result, element_type

