from __future__ import annotations

from .model import Node
from .semantic_model import LocalBinding


class SemanticStatementMixin:
    def analyze_block(
        self,
        block: Node,
        scopes: list[dict[str, LocalBinding]],
        return_type: str,
        function_name: str,
        *,
        create_scope: bool,
    ) -> None:
        if create_scope:
            scopes.append({})
        try:
            for statement in block.fields["statements"]:
                if statement.kind in {"LetStmt", "VarStmt"}:
                    declared = statement.fields["type_name"]
                    actual = self.type_expr(statement.fields["value"], scopes, function_name)
                    if not self.type_is_supported(declared):
                        self.error("AX-TYPE-0004", f"unsupported binding type: {declared}", statement, "type_checker")
                    elif actual != "error" and declared != actual:
                        self.report_binding_mismatch(declared, actual, statement)
                    mutable = statement.kind == "VarStmt"
                    self.declare_local(
                        scopes,
                        LocalBinding(
                            name=statement.fields["name"],
                            type_name=declared,
                            mutable=mutable,
                            node_id=statement.node_id,
                            kind="var" if mutable else "let",
                        ),
                        statement,
                    )
                    if mutable:
                        self.function_facts[function_name]["mutable_bindings"] += 1
                elif statement.kind == "AssignmentStmt":
                    target_name = statement.fields["target"]
                    binding = self.resolve_local(scopes, target_name)
                    actual = self.type_expr(statement.fields["value"], scopes, function_name)
                    if binding is None:
                        self.error("AX-NAME-0001", f"unresolved assignment target: {target_name}", statement, "resolver")
                    else:
                        self.references.append(
                            {
                                "node_id": statement.node_id,
                                "name": target_name,
                                "kind": "assignment",
                                "target_node_id": binding.node_id,
                            }
                        )
                        if not binding.mutable:
                            self.error(
                                "AX-MUT-0001",
                                f"cannot assign to immutable binding: {target_name}",
                                statement,
                                "type_checker",
                            )
                        if actual != "error" and actual != binding.type_name:
                            self.error(
                                "AX-TYPE-0011",
                                f"assignment type mismatch: expected {binding.type_name}, found {actual}",
                                statement,
                                "type_checker",
                            )
                    self.function_facts[function_name]["assignments"] += 1
                elif statement.kind == "ReturnStmt":
                    actual = self.type_expr(statement.fields["value"], scopes, function_name)
                    if actual != "error" and actual != return_type:
                        self.error(
                            "AX-TYPE-0002",
                            f"return type mismatch: expected {return_type}, found {actual}",
                            statement,
                            "type_checker",
                        )
                elif statement.kind == "IfStmt":
                    condition = self.type_expr(statement.fields["condition"], scopes, function_name)
                    if condition != "error" and condition != "bool":
                        self.error(
                            "AX-TYPE-0003",
                            f"if condition must be bool, found {condition}",
                            statement.fields["condition"],
                            "type_checker",
                        )
                    self.analyze_block(
                        statement.fields["then_block"],
                        scopes,
                        return_type,
                        function_name,
                        create_scope=True,
                    )
                    else_block = statement.fields.get("else_block")
                    if isinstance(else_block, Node):
                        self.analyze_block(
                            else_block,
                            scopes,
                            return_type,
                            function_name,
                            create_scope=True,
                        )
                elif statement.kind == "WhileStmt":
                    condition = self.type_expr(statement.fields["condition"], scopes, function_name)
                    if condition != "error" and condition != "bool":
                        self.error(
                            "AX-TYPE-0012",
                            f"while condition must be bool, found {condition}",
                            statement.fields["condition"],
                            "type_checker",
                        )
                    self.function_facts[function_name]["while_loops"] += 1
                    self.analyze_block(
                        statement.fields["body"],
                        scopes,
                        return_type,
                        function_name,
                        create_scope=True,
                    )
                elif statement.kind == "ExprStmt":
                    self.type_expr(statement.fields["expression"], scopes, function_name)
        finally:
            if create_scope:
                scopes.pop()

