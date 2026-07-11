from __future__ import annotations

from .model import Node
from .semantic_model import LocalBinding
from .type_system import PRIMITIVE_TYPES


class SemanticBinaryExpressionMixin:
    def type_binary_expr(
        self,
        expression: Node,
        scopes: list[dict[str, LocalBinding]],
        function_name: str,
    ) -> str:
        left = self.type_expr(expression.fields["left"], scopes, function_name)
        right = self.type_expr(expression.fields["right"], scopes, function_name)
        operator = expression.fields["operator"]
        if left == "error" or right == "error":
            return "error"
        if operator in {"+", "-", "*", "/", "%"}:
            if left != "i32" or right != "i32":
                self.error("AX-TYPE-0007", f"operator {operator} requires i32 operands", expression, "type_checker")
                return "error"
            self.function_facts[function_name]["checked_arithmetic_sites"] += 1
            self.function_facts[function_name]["panic_sites"] += 1
            return "i32"
        if operator in {"<", "<=", ">", ">="}:
            if left != "i32" or right != "i32":
                self.error("AX-TYPE-0008", f"ordered comparison requires i32 operands, found {left} and {right}", expression, "type_checker")
                return "error"
            return "bool"
        if operator in {"==", "!="}:
            if left != right:
                self.error("AX-TYPE-0008", f"comparison operands differ: {left} and {right}", expression, "type_checker")
                return "error"
            if left not in PRIMITIVE_TYPES:
                self.error("AX-TYPE-0015", f"aggregate equality is not implemented for {left}", expression, "type_checker")
                return "error"
            return "bool"
        self.error("AX-TYPE-0009", f"unsupported operator: {operator}", expression, "type_checker")
        return "error"
