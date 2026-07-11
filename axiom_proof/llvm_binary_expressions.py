from __future__ import annotations

from .arithmetic import PANIC_ADD_OVERFLOW, PANIC_MUL_OVERFLOW, PANIC_SUB_OVERFLOW
from .llvm_model import FunctionContext, Storage
from .model import Node


class LLVMBinaryExpressionMixin:
    def emit_binary_expr(
        self,
        expression: Node,
        environment: dict[str, Storage],
        context: FunctionContext,
    ) -> tuple[str, str]:
        left, left_type = self.emit_expr(expression.fields["left"], environment, context)
        right, right_type = self.emit_expr(expression.fields["right"], environment, context)
        if left_type != right_type:
            raise ValueError("LLVM backend received mismatched binary operands")
        operator = expression.fields["operator"]
        if operator == "+":
            return self.emit_checked_overflow(
                context, "llvm.sadd.with.overflow.i32", left, right, PANIC_ADD_OVERFLOW
            ), "i32"
        if operator == "-":
            return self.emit_checked_overflow(
                context, "llvm.ssub.with.overflow.i32", left, right, PANIC_SUB_OVERFLOW
            ), "i32"
        if operator == "*":
            return self.emit_checked_overflow(
                context, "llvm.smul.with.overflow.i32", left, right, PANIC_MUL_OVERFLOW
            ), "i32"
        if operator == "/":
            return self.emit_checked_division(context, left, right, remainder=False), "i32"
        if operator == "%":
            return self.emit_checked_division(context, left, right, remainder=True), "i32"
        result = context.register()
        predicate = {
            "<": "slt",
            "<=": "sle",
            ">": "sgt",
            ">=": "sge",
            "==": "eq",
            "!=": "ne",
        }[operator]
        context.lines.append(
            f"  {result} = icmp {predicate} {self.llvm_type(left_type)} {left}, {right}"
        )
        return result, "bool"
