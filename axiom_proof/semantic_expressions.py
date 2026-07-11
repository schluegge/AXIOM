from __future__ import annotations

from .model import Node
from .semantic_model import LocalBinding
from .semantic_scalar_expressions import SemanticScalarExpressionMixin
from .semantic_aggregate_expressions import SemanticAggregateExpressionMixin
from .semantic_binary_expressions import SemanticBinaryExpressionMixin


class SemanticExpressionMixin(
    SemanticScalarExpressionMixin,
    SemanticAggregateExpressionMixin,
    SemanticBinaryExpressionMixin,
):
    def type_expr(
        self,
        expression: Node,
        scopes: list[dict[str, LocalBinding]],
        function_name: str,
    ) -> str:
        if expression.kind in {"IntegerLiteral", "BoolLiteral", "NameExpr", "CallExpr"}:
            result = self.type_scalar_expr(expression, scopes, function_name)
        elif expression.kind in {"StructLiteral", "FieldExpr", "ArrayLiteral", "IndexExpr"}:
            result = self.type_aggregate_expr(expression, scopes, function_name)
        elif expression.kind == "BinaryExpr":
            result = self.type_binary_expr(expression, scopes, function_name)
        else:
            self.error(
                "AX-TYPE-0010",
                f"unsupported expression node: {expression.kind}",
                expression,
                "type_checker",
            )
            result = "error"
        self.node_types[expression.node_id] = result
        return result
