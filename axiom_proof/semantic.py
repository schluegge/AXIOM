from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .arithmetic import I32_MAX, I32_MIN
from .model import Diagnostic, Node

SUPPORTED_TYPES = {"i32", "bool"}


@dataclass(frozen=True)
class FunctionSignature:
    name: str
    parameter_types: tuple[str, ...]
    return_type: str
    node_id: str


@dataclass(frozen=True)
class LocalBinding:
    name: str
    type_name: str
    mutable: bool
    node_id: str
    kind: str


class SemanticAnalyzer:
    def __init__(self, program: Node):
        self.program = program
        self.diagnostics: list[Diagnostic] = []
        self.functions: dict[str, FunctionSignature] = {}
        self.node_types: dict[str, str] = {}
        self.references: list[dict[str, Any]] = []
        self.call_graph: dict[str, list[str]] = {}
        self.function_facts: dict[str, dict[str, Any]] = {}

    def analyze(self) -> None:
        self.collect_functions()
        for function in self.program.fields["functions"]:
            self.analyze_function(function)

    def error(self, code: str, message: str, node: Node, stage: str) -> None:
        self.diagnostics.append(Diagnostic(code, "error", message, node.span, stage))

    def collect_functions(self) -> None:
        for function in self.program.fields["functions"]:
            name = function.fields["name"]
            if name in self.functions:
                self.error("AX-NAME-0002", f"duplicate function: {name}", function, "resolver")
                continue
            parameter_types = tuple(parameter.fields["type_name"] for parameter in function.fields["parameters"])
            return_type = function.fields["return_type"]
            for type_name in (*parameter_types, return_type):
                if type_name not in SUPPORTED_TYPES:
                    self.error("AX-TYPE-0004", f"unsupported type in vertical proof: {type_name}", function, "type_checker")
            self.functions[name] = FunctionSignature(name, parameter_types, return_type, function.node_id)
            self.call_graph[name] = []
            self.function_facts[name] = {
                "mutable_bindings": 0,
                "assignments": 0,
                "while_loops": 0,
                "checked_arithmetic_sites": 0,
                "panic_sites": 0,
            }

    def resolve_local(self, scopes: list[dict[str, LocalBinding]], name: str) -> LocalBinding | None:
        for scope in reversed(scopes):
            binding = scope.get(name)
            if binding is not None:
                return binding
        return None

    def declare_local(self, scopes: list[dict[str, LocalBinding]], binding: LocalBinding, node: Node) -> None:
        if self.resolve_local(scopes, binding.name) is not None:
            self.error("AX-NAME-0004", f"duplicate local binding: {binding.name}", node, "resolver")
            return
        scopes[-1][binding.name] = binding

    def analyze_function(self, function: Node) -> None:
        parameter_scope: dict[str, LocalBinding] = {}
        for parameter in function.fields["parameters"]:
            name = parameter.fields["name"]
            if name in parameter_scope:
                self.error("AX-NAME-0003", f"duplicate parameter: {name}", parameter, "resolver")
                continue
            parameter_scope[name] = LocalBinding(
                name=name,
                type_name=parameter.fields["type_name"],
                mutable=False,
                node_id=parameter.node_id,
                kind="parameter",
            )
        scopes = [parameter_scope]
        self.analyze_block(
            function.fields["body"],
            scopes,
            function.fields["return_type"],
            function.fields["name"],
            create_scope=False,
        )

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
                    if declared not in SUPPORTED_TYPES:
                        self.error("AX-TYPE-0004", f"unsupported binding type: {declared}", statement, "type_checker")
                    elif actual != "error" and declared != actual:
                        self.error(
                            "AX-TYPE-0001",
                            f"binding type mismatch: expected {declared}, found {actual}",
                            statement,
                            "type_checker",
                        )
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

    def type_expr(self, expression: Node, scopes: list[dict[str, LocalBinding]], function_name: str) -> str:
        if expression.kind == "IntegerLiteral":
            value = expression.fields["value"]
            if not I32_MIN <= value <= I32_MAX:
                self.error(
                    "AX-INT-0001",
                    f"integer literal is outside i32 range: {value}",
                    expression,
                    "type_checker",
                )
                result = "error"
            else:
                result = "i32"
        elif expression.kind == "BoolLiteral":
            result = "bool"
        elif expression.kind == "NameExpr":
            name = expression.fields["name"]
            binding = self.resolve_local(scopes, name)
            if binding is None:
                self.error("AX-NAME-0001", f"unresolved name: {name}", expression, "resolver")
                result = "error"
            else:
                result = binding.type_name
                self.references.append(
                    {
                        "node_id": expression.node_id,
                        "name": name,
                        "kind": "local",
                        "target_node_id": binding.node_id,
                    }
                )
        elif expression.kind == "CallExpr":
            callee = expression.fields["callee"]
            signature = self.functions.get(callee)
            if signature is None:
                self.error("AX-NAME-0001", f"unresolved function: {callee}", expression, "resolver")
                for argument in expression.fields["arguments"]:
                    self.type_expr(argument, scopes, function_name)
                result = "error"
            else:
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
                result = signature.return_type
        elif expression.kind == "BinaryExpr":
            left = self.type_expr(expression.fields["left"], scopes, function_name)
            right = self.type_expr(expression.fields["right"], scopes, function_name)
            operator = expression.fields["operator"]
            if left == "error" or right == "error":
                result = "error"
            elif operator in {"+", "-", "*", "/", "%"}:
                if left != "i32" or right != "i32":
                    self.error("AX-TYPE-0007", f"operator {operator} requires i32 operands", expression, "type_checker")
                    result = "error"
                else:
                    result = "i32"
                    self.function_facts[function_name]["checked_arithmetic_sites"] += 1
                    self.function_facts[function_name]["panic_sites"] += 1
            elif operator in {"<", "<=", ">", ">=", "==", "!="}:
                if left != right:
                    self.error(
                        "AX-TYPE-0008",
                        f"comparison operands differ: {left} and {right}",
                        expression,
                        "type_checker",
                    )
                    result = "error"
                else:
                    result = "bool"
            else:
                self.error("AX-TYPE-0009", f"unsupported operator: {operator}", expression, "type_checker")
                result = "error"
        else:
            self.error("AX-TYPE-0010", f"unsupported expression node: {expression.kind}", expression, "type_checker")
            result = "error"
        self.node_types[expression.node_id] = result
        return result

    def symbol_document(self) -> dict[str, Any]:
        return {
            "document_kind": "axiom.symbols",
            "schema_version": "0.4.0",
            "functions": [
                {
                    "name": signature.name,
                    "node_id": signature.node_id,
                    "parameter_types": list(signature.parameter_types),
                    "return_type": signature.return_type,
                }
                for signature in sorted(self.functions.values(), key=lambda item: item.name)
            ],
            "references": sorted(self.references, key=lambda item: (item["node_id"], item["name"], item["kind"])),
            "call_graph": {name: sorted(set(calls)) for name, calls in sorted(self.call_graph.items())},
        }

    def type_document(self) -> dict[str, Any]:
        return {
            "document_kind": "axiom.types",
            "schema_version": "0.4.0",
            "node_types": dict(sorted(self.node_types.items())),
        }

    def effect_document(self) -> dict[str, Any]:
        return {
            "document_kind": "axiom.effects",
            "schema_version": "0.4.0",
            "functions": [
                {
                    "name": name,
                    "effects": (["panic"] if self.function_facts[name]["panic_sites"] else []),
                    "local_facts": self.function_facts[name],
                    "proof": (
                        "checked_i32_arithmetic_may_panic"
                        if self.function_facts[name]["panic_sites"]
                        else "no_external_effects_in_reference_subset"
                    ),
                }
                for name in sorted(self.functions)
            ],
        }

    def ownership_document(self) -> dict[str, Any]:
        mutable_bindings = sum(facts["mutable_bindings"] for facts in self.function_facts.values())
        assignments = sum(facts["assignments"] for facts in self.function_facts.values())
        return {
            "document_kind": "axiom.ownership",
            "schema_version": "0.4.0",
            "mode": "copy_scalar_with_explicit_local_mutation",
            "borrows": [],
            "moves": [],
            "mutable_bindings": mutable_bindings,
            "assignments": assignments,
            "proof": "no_owned_resource_types_exist_in_reference_subset",
        }
