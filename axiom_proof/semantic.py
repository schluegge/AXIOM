from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .arithmetic import I32_MAX, I32_MIN
from .layout import LayoutEngine
from .model import Diagnostic, Node
from .type_system import (
    PRIMITIVE_TYPES,
    StructDefinition,
    StructField,
    TypeRegistry,
    parse_array_type,
)


from .semantic_model import FunctionSignature, LocalBinding
from .semantic_blocks import SemanticBlockMixin
from .semantic_statements import SemanticStatementMixin
from .semantic_lvalues import SemanticLValueMixin
from .semantic_expressions import SemanticExpressionMixin
from .semantic_documents import SemanticDocumentMixin


class SemanticAnalyzer(SemanticBlockMixin, SemanticLValueMixin, SemanticStatementMixin, SemanticExpressionMixin, SemanticDocumentMixin):
    def __init__(self, program: Node):
        self.program = program
        self.diagnostics: list[Diagnostic] = []
        self.registry = TypeRegistry()
        self.functions: dict[str, FunctionSignature] = {}
        self.node_types: dict[str, str] = {}
        self.references: list[dict[str, Any]] = []
        self.call_graph: dict[str, list[str]] = {}
        self.function_facts: dict[str, dict[str, Any]] = {}

    def analyze(self) -> None:
        self.collect_structs()
        self.collect_functions()
        for function in self.program.fields["functions"]:
            self.analyze_function(function)

    def error(self, code: str, message: str, node: Node, stage: str) -> None:
        self.diagnostics.append(Diagnostic(code, "error", message, node.span, stage))

    def collect_structs(self) -> None:
        declarations_by_name: dict[str, Node] = {}
        for declaration in self.program.fields.get("structs", []):
            name = declaration.fields["name"]
            if name in self.registry.structs:
                self.error("AX-STRUCT-0001", f"duplicate struct: {name}", declaration, "resolver")
                continue
            seen_fields: set[str] = set()
            fields: list[StructField] = []
            for field in declaration.fields["fields"]:
                field_name = field.fields["name"]
                if field_name in seen_fields:
                    self.error(
                        "AX-STRUCT-0002",
                        f"duplicate field {field_name} in struct {name}",
                        field,
                        "resolver",
                    )
                    continue
                seen_fields.add(field_name)
                fields.append(StructField(field_name, field.fields["type_name"], field.node_id))
            if not fields:
                self.error(
                    "AX-STRUCT-0010",
                    f"empty struct {name} is outside the C-compatible layout subset",
                    declaration,
                    "type_checker",
                )
            self.registry.structs[name] = StructDefinition(name, tuple(fields), declaration.node_id)
            declarations_by_name[name] = declaration

        for declaration in self.program.fields.get("structs", []):
            name = declaration.fields["name"]
            if declarations_by_name.get(name) is not declaration:
                continue
            for field in declaration.fields["fields"]:
                type_name = field.fields["type_name"]
                array = parse_array_type(type_name)
                if array is not None and array[1] <= 0:
                    self.error(
                        "AX-ARRAY-0004",
                        "fixed array length must be greater than zero",
                        field,
                        "type_checker",
                    )
                elif not self.registry.is_known(type_name):
                    self.error(
                        "AX-TYPE-0013",
                        f"unknown field type {type_name} in struct {name}",
                        field,
                        "type_checker",
                    )

        for cycle in self.registry.validate_acyclic():
            owner = declarations_by_name.get(cycle[0])
            if owner is not None:
                self.error(
                    "AX-TYPE-0014",
                    f"recursive value type is not allowed: {' -> '.join(cycle)}",
                    owner,
                    "type_checker",
                )

    def type_is_supported(self, type_name: str) -> bool:
        return self.registry.is_known(type_name)

    def collect_functions(self) -> None:
        for function in self.program.fields["functions"]:
            name = function.fields["name"]
            if name in self.functions:
                self.error("AX-NAME-0002", f"duplicate function: {name}", function, "resolver")
                continue
            parameter_types = tuple(parameter.fields["type_name"] for parameter in function.fields["parameters"])
            return_type = function.fields["return_type"]
            for type_name in (*parameter_types, return_type):
                if not self.type_is_supported(type_name):
                    self.error("AX-TYPE-0004", f"unsupported type: {type_name}", function, "type_checker")
            self.functions[name] = FunctionSignature(name, parameter_types, return_type, function.node_id)
            self.call_graph[name] = []
            self.function_facts[name] = {
                "mutable_bindings": 0,
                "assignments": 0,
                "while_loops": 0,
                "checked_arithmetic_sites": 0,
                "bounds_check_sites": 0,
                "panic_sites": 0,
                "aggregate_literals": 0,
                "field_accesses": 0,
                "index_accesses": 0,
                "field_writes": 0,
                "index_writes": 0,
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

