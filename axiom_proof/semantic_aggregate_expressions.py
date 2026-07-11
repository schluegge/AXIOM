from __future__ import annotations

from .model import Node
from .semantic_model import LocalBinding
from .type_system import parse_array_type


class SemanticAggregateExpressionMixin:
    def type_aggregate_expr(
        self,
        expression: Node,
        scopes: list[dict[str, LocalBinding]],
        function_name: str,
    ) -> str:
        if expression.kind == "StructLiteral":
            return self.type_struct_literal(expression, scopes, function_name)
        if expression.kind == "FieldExpr":
            base_type = self.type_expr(expression.fields["base"], scopes, function_name)
            definition = self.registry.struct(base_type)
            if base_type == "error":
                return "error"
            if definition is None:
                self.error("AX-STRUCT-0008", f"field access requires a struct, found {base_type}", expression, "type_checker")
                return "error"
            field = definition.field(expression.fields["field"])
            if field is None:
                self.error("AX-STRUCT-0009", f"struct {base_type} has no field {expression.fields['field']}", expression, "type_checker")
                return "error"
            self.function_facts[function_name]["field_accesses"] += 1
            return field.type_name
        if expression.kind == "ArrayLiteral":
            elements = expression.fields["elements"]
            if not elements:
                self.error("AX-ARRAY-0001", "empty array literal has no inferable element type", expression, "type_checker")
                return "error"
            element_types = [self.type_expr(element, scopes, function_name) for element in elements]
            first = element_types[0]
            for index, element_type in enumerate(element_types[1:], start=2):
                if first != "error" and element_type != "error" and element_type != first:
                    self.error("AX-ARRAY-0003", f"array element {index}: expected {first}, found {element_type}", elements[index - 1], "type_checker")
            self.function_facts[function_name]["aggregate_literals"] += 1
            return "error" if "error" in element_types else f"[{first}; {len(elements)}]"
        return self.type_index_expr(expression, scopes, function_name)

    def type_struct_literal(self, expression: Node, scopes: list[dict[str, LocalBinding]], function_name: str) -> str:
        type_name = expression.fields["type_name"]
        definition = self.registry.struct(type_name)
        if definition is None:
            self.error("AX-STRUCT-0003", f"unknown struct literal type: {type_name}", expression, "type_checker")
            for field in expression.fields["fields"]:
                self.type_expr(field.fields["value"], scopes, function_name)
            return "error"
        supplied: dict[str, Node] = {}
        for field_init in expression.fields["fields"]:
            field_name = field_init.fields["name"]
            actual = self.type_expr(field_init.fields["value"], scopes, function_name)
            if field_name in supplied:
                self.error("AX-STRUCT-0004", f"duplicate struct literal field: {field_name}", field_init, "type_checker")
                continue
            supplied[field_name] = field_init
            expected_field = definition.field(field_name)
            if expected_field is None:
                self.error("AX-STRUCT-0005", f"unknown field {field_name} for struct {type_name}", field_init, "type_checker")
            elif actual != "error" and actual != expected_field.type_name:
                self.error("AX-STRUCT-0007", f"field {field_name}: expected {expected_field.type_name}, found {actual}", field_init, "type_checker")
        for field in definition.fields:
            if field.name not in supplied:
                self.error("AX-STRUCT-0006", f"missing field {field.name} for struct {type_name}", expression, "type_checker")
        self.function_facts[function_name]["aggregate_literals"] += 1
        return type_name

    def type_index_expr(self, expression: Node, scopes: list[dict[str, LocalBinding]], function_name: str) -> str:
        base_type = self.type_expr(expression.fields["base"], scopes, function_name)
        index_type = self.type_expr(expression.fields["index"], scopes, function_name)
        array = parse_array_type(base_type)
        if base_type == "error" or index_type == "error":
            return "error"
        if array is None:
            self.error("AX-INDEX-0002", f"index access requires an array, found {base_type}", expression, "type_checker")
            return "error"
        if index_type != "i32":
            self.error("AX-INDEX-0003", f"array index must be i32, found {index_type}", expression.fields["index"], "type_checker")
            return "error"
        element_type, length = array
        index_expression = expression.fields["index"]
        if index_expression.kind == "IntegerLiteral":
            index = index_expression.fields["value"]
            if not 0 <= index < length:
                self.error("AX-INDEX-0001", f"constant array index {index} is outside 0..{length - 1}", index_expression, "type_checker")
                return "error"
        else:
            self.function_facts[function_name]["bounds_check_sites"] += 1
            self.function_facts[function_name]["panic_sites"] += 1
        self.function_facts[function_name]["index_accesses"] += 1
        return element_type
