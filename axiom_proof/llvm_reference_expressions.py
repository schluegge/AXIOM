from __future__ import annotations

from .llvm_model import FunctionContext, Storage
from .model import Node
from .type_system import parse_reference_type, reference_type


class LLVMReferenceExpressionMixin:
    def emit_reference_expr(
        self,
        expression: Node,
        environment: dict[str, Storage],
        context: FunctionContext,
    ) -> tuple[str, str]:
        if expression.kind == "BorrowExpr":
            mutable = bool(expression.fields["mutable"])
            pointer, referent = self.emit_lvalue_ptr(
                expression.fields["target"],
                environment,
                context,
                require_mutable=mutable,
            )
            return pointer, reference_type(referent, mutable)

        reference_value, reference_type_name = self.emit_expr(
            expression.fields["reference"], environment, context
        )
        parsed = parse_reference_type(reference_type_name)
        if parsed is None:
            raise ValueError("LLVM backend received dereference of non-reference")
        referent, _ = parsed
        result = context.register()
        context.lines.append(
            f"  {result} = load {self.llvm_type(referent)}, ptr {reference_value}"
        )
        return result, referent
