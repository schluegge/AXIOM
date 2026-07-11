from __future__ import annotations

from .llvm_model import FunctionContext, Storage
from .model import Node


class LLVMExpressionMixin:
    def emit_expr(
        self,
        expression: Node,
        environment: dict[str, Storage],
        context: FunctionContext,
    ) -> tuple[str, str]:
        if expression.kind in {"IntegerLiteral", "BoolLiteral", "NameExpr", "CallExpr"}:
            return self.emit_scalar_expr(expression, environment, context)
        if expression.kind in {"StructLiteral", "ArrayLiteral", "FieldExpr", "IndexExpr"}:
            return self.emit_aggregate_expr(expression, environment, context)
        if expression.kind == "BinaryExpr":
            return self.emit_binary_expr(expression, environment, context)
        raise ValueError(f"unsupported LLVM expression: {expression.kind}")
