from __future__ import annotations

from .arithmetic import I32_MAX, I32_MIN
from .model import Node
from .semantic_model import BorrowRecord, LocalBinding
from .type_system import parse_reference_type


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
                self.error("AX-INT-0001", f"integer literal is outside i32 range: {value}", expression, "type_checker")
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
            self.check_root_read(binding, expression)
            if any(binding.node_id in scope for scope in self.reference_loan_scopes):
                self.error(
                    "AX-BORROW-0009",
                    f"cannot use mutable reference {name} again during the same call",
                    expression,
                    "borrow_checker",
                )
            self.references.append(
                {"node_id": expression.node_id, "name": name, "kind": "local", "target_node_id": binding.node_id}
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
        temporary_borrows: list[BorrowRecord] = []
        mutable_reference_loans: set[str] = set()
        self.reference_loan_scopes.append(mutable_reference_loans)
        try:
            for index, argument in enumerate(arguments):
                expected = signature.parameter_types[index] if index < len(signature.parameter_types) else None
                expected_reference = parse_reference_type(expected) if expected is not None else None
                direct_mutable_reference_binding = None
                if argument.kind == "NameExpr" and expected_reference is not None and expected_reference[1]:
                    direct_mutable_reference_binding = self.resolve_local(scopes, argument.fields["name"])
                    if (
                        direct_mutable_reference_binding is not None
                        and parse_reference_type(direct_mutable_reference_binding.type_name) is not None
                    ):
                        if direct_mutable_reference_binding.node_id in mutable_reference_loans:
                            self.error(
                                "AX-BORROW-0008",
                                f"mutable reference {direct_mutable_reference_binding.name} is passed more than once to the same call",
                                argument,
                                "borrow_checker",
                            )
                            actual = direct_mutable_reference_binding.type_name
                        else:
                            actual = self.type_expr(argument, scopes, function_name)
                            mutable_reference_loans.add(direct_mutable_reference_binding.node_id)
                            self.function_facts[function_name]["mutable_reference_loans"] += 1
                    else:
                        actual = self.type_expr(argument, scopes, function_name)
                elif argument.kind == "BorrowExpr" and expected_reference is not None:
                    actual, record = self.type_borrow_expr(
                        argument,
                        scopes,
                        function_name,
                        holder_node=expression,
                        temporary=True,
                    )
                    if record is not None:
                        temporary_borrows.append(record)
                else:
                    actual = self.type_expr(argument, scopes, function_name)
                if expected is not None and actual != "error" and actual != expected:
                    self.error(
                        "AX-TYPE-0006",
                        f"argument {index + 1} of {callee}: expected {expected}, found {actual}",
                        argument,
                        "type_checker",
                    )
        finally:
            self.reference_loan_scopes.pop()
            self.release_temporary_borrows(temporary_borrows)
        self.call_graph.setdefault(function_name, []).append(callee)
        self.references.append(
            {"node_id": expression.node_id, "name": callee, "kind": "function", "target_node_id": signature.node_id}
        )
        return signature.return_type
