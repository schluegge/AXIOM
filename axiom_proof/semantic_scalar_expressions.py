from __future__ import annotations

from .arithmetic import I32_MAX, I32_MIN
from .model import Node
from .semantic_model import LocalBinding


class SemanticScalarExpressionMixin:
    def type_scalar_expr(
        self,
        expression: Node,
        scopes: list[dict[str, LocalBinding]],
        function_name: str,
    ) -> str:
        if expression.kind == "IntegerLiteral":
            value = expression.fields["value"]
            if not I32_MIN <= value <= I32_MAX:
                self.error(
                    "AX-INT-0001",
                    f"integer literal is outside i32 range: {value}",
                    expression,
                    "type_checker",
                )
                return "error"
            return "i32"
        if expression.kind == "BoolLiteral":
            return "bool"
        if expression.kind == "NameExpr":
            name = expression.fields["name"]
            binding = self.resolve_local(scopes, name)
            if binding is None:
                self.error("AX-NAME-0001", f"unresolved name: {name}", expression, "resolver")
                return "error"
            self.references.append(
                {
                    "node_id": expression.node_id,
                    "name": name,
                    "kind": "local",
                    "target_node_id": binding.node_id,
                }
            )
            return binding.type_name

        callee = expression.fields["callee"]
        signature = self.functions.get(callee)
        if signature is None:
            self.error("AX-NAME-0001", f"unresolved function: {callee}", expression, "resolver")
            for argument in expression.fields["arguments"]:
                self.type_expr(argument, scopes, function_name)
            return "error"
        arguments = expression.fields["arguments"]
        if len(arguments) != len(signature.parameter_types):
            self.error("AX-TYPE-0005", f"argument count mismatch for {callee}", expression, "type_checker")
        for index, argument in enumerate(arguments):
            actual = self.type_expr(argument, scopes, function_name)
            if index < len(signature.parameter_types):
                expected = signature.parameter_types[index]
                if actual != "error" and actual != expected:
                    self.error(
                        "AX-TYPE-0006",
                        f"argument {index + 1} of {callee}: expected {expected}, found {actual}",
                        argument,
                        "type_checker",
                    )
        self.call_graph.setdefault(function_name, []).append(callee)
        self.references.append(
            {
                "node_id": expression.node_id,
                "name": callee,
                "kind": "function",
                "target_node_id": signature.node_id,
            }
        )
        return signature.return_type
