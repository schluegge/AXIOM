from __future__ import annotations

from typing import Any

from .model import Node
from .semantic_model import LocalBinding
from .type_system import parse_array_type


class SemanticBlockMixin:
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
        self.current_function_name = function.fields["name"]
        self.borrow_scopes = [[]]
        try:
            self.analyze_block(
                function.fields["body"],
                scopes,
                function.fields["return_type"],
                function.fields["name"],
                create_scope=False,
            )
        finally:
            self.borrow_scopes = []
            self.current_function_name = ""

    def report_binding_mismatch(self, declared: str, actual: str, node: Node) -> None:
        declared_array = parse_array_type(declared)
        actual_array = parse_array_type(actual)
        if declared_array is not None and actual_array is not None:
            if declared_array[0] == actual_array[0] and declared_array[1] != actual_array[1]:
                self.error(
                    "AX-ARRAY-0002",
                    f"array length mismatch: expected {declared_array[1]}, found {actual_array[1]}",
                    node,
                    "type_checker",
                )
                return
            if declared_array[0] != actual_array[0]:
                self.error(
                    "AX-ARRAY-0003",
                    f"array element type mismatch: expected {declared_array[0]}, found {actual_array[0]}",
                    node,
                    "type_checker",
                )
                return
        self.error(
            "AX-TYPE-0001",
            f"binding type mismatch: expected {declared}, found {actual}",
            node,
            "type_checker",
        )
