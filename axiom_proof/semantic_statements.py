from __future__ import annotations

from .model import Node
from .semantic_model import LocalBinding
from .type_system import contains_reference, parse_reference_type


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
            self.borrow_scopes.append([])
        try:
            for statement in block.fields["statements"]:
                if statement.kind in {"LetStmt", "VarStmt"}:
                    declared = statement.fields["type_name"]
                    declared_reference = parse_reference_type(declared)
                    if declared_reference is not None:
                        if statement.kind == "VarStmt":
                            self.error(
                                "AX-REF-0004",
                                "reference bindings are immutable in the v0.7 subset; use let",
                                statement,
                                "borrow_checker",
                            )
                        if statement.fields["value"].kind == "BorrowExpr":
                            actual, _ = self.type_borrow_expr(
                                statement.fields["value"],
                                scopes,
                                function_name,
                                holder_node=statement,
                                temporary=False,
                            )
                        else:
                            actual = self.type_expr(statement.fields["value"], scopes, function_name)
                            self.error(
                                "AX-REF-0005",
                                "a local reference binding must be initialized by a borrow expression",
                                statement.fields["value"],
                                "borrow_checker",
                            )
                    else:
                        actual = self.type_expr(statement.fields["value"], scopes, function_name)
                        if contains_reference(declared):
                            self.error(
                                "AX-REF-0002",
                                f"references cannot be stored in aggregate binding type: {declared}",
                                statement,
                                "borrow_checker",
                            )
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
                    target = statement.fields["target"]
                    info = self.type_lvalue(target, scopes, function_name)
                    actual = self.type_expr(statement.fields["value"], scopes, function_name)
                    if not info.writable:
                        if info.via_reference and info.type_name != "error":
                            self.error(
                                "AX-BORROW-0006",
                                "cannot assign through a shared reference",
                                target,
                                "borrow_checker",
                            )
                        elif info.root_binding is not None:
                            self.error(
                                "AX-MUT-0001",
                                f"cannot assign through immutable binding: {info.root_binding.name}",
                                target,
                                "type_checker",
                            )
                    if info.type_name != "error" and actual != "error" and actual != info.type_name:
                        self.error(
                            "AX-TYPE-0011",
                            f"assignment type mismatch: expected {info.type_name}, found {actual}",
                            statement,
                            "type_checker",
                        )
                    self.function_facts[function_name]["assignments"] += 1
                elif statement.kind == "ReturnStmt":
                    actual = self.type_expr(statement.fields["value"], scopes, function_name)
                    if parse_reference_type(actual) is not None:
                        self.error(
                            "AX-REF-0003",
                            "reference values cannot escape through return in the v0.7 subset",
                            statement,
                            "borrow_checker",
                        )
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
                        statement.fields["then_block"], scopes, return_type, function_name, create_scope=True
                    )
                    else_block = statement.fields.get("else_block")
                    if isinstance(else_block, Node):
                        self.analyze_block(else_block, scopes, return_type, function_name, create_scope=True)
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
                        statement.fields["body"], scopes, return_type, function_name, create_scope=True
                    )
                elif statement.kind == "ExprStmt":
                    self.type_expr(statement.fields["expression"], scopes, function_name)
        finally:
            if create_scope:
                self.borrow_scopes.pop()
                scopes.pop()
