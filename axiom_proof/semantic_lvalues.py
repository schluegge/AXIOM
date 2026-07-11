from __future__ import annotations

from .model import Node
from .semantic_model import LocalBinding
from .type_system import parse_array_type


class SemanticLValueMixin:
    def type_lvalue(
        self,
        target: Node,
        scopes: list[dict[str, LocalBinding]],
        function_name: str,
    ) -> tuple[LocalBinding | None, str]:
        if target.kind == "NameExpr":
            name = target.fields["name"]
            binding = self.resolve_local(scopes, name)
            if binding is None:
                self.error(
                    "AX-NAME-0001",
                    f"unresolved assignment target: {name}",
                    target,
                    "resolver",
                )
                self.node_types[target.node_id] = "error"
                return None, "error"
            self.references.append(
                {
                    "node_id": target.node_id,
                    "name": name,
                    "kind": "assignment_root",
                    "target_node_id": binding.node_id,
                }
            )
            self.node_types[target.node_id] = binding.type_name
            return binding, binding.type_name

        if target.kind == "FieldExpr":
            binding, base_type = self.type_lvalue(target.fields["base"], scopes, function_name)
            if base_type == "error":
                self.node_types[target.node_id] = "error"
                return binding, "error"
            definition = self.registry.struct(base_type)
            if definition is None:
                self.error(
                    "AX-STRUCT-0008",
                    f"field assignment requires a struct, found {base_type}",
                    target,
                    "type_checker",
                )
                self.node_types[target.node_id] = "error"
                return binding, "error"
            field_name = target.fields["field"]
            field = definition.field(field_name)
            if field is None:
                self.error(
                    "AX-STRUCT-0009",
                    f"struct {base_type} has no field {field_name}",
                    target,
                    "type_checker",
                )
                self.node_types[target.node_id] = "error"
                return binding, "error"
            self.references.append(
                {
                    "node_id": target.node_id,
                    "name": field_name,
                    "kind": "field_write",
                    "target_node_id": field.node_id,
                }
            )
            self.function_facts[function_name]["field_writes"] += 1
            self.node_types[target.node_id] = field.type_name
            return binding, field.type_name

        if target.kind == "IndexExpr":
            binding, base_type = self.type_lvalue(target.fields["base"], scopes, function_name)
            index_type = self.type_expr(target.fields["index"], scopes, function_name)
            if base_type == "error" or index_type == "error":
                self.node_types[target.node_id] = "error"
                return binding, "error"
            array = parse_array_type(base_type)
            if array is None:
                self.error(
                    "AX-INDEX-0002",
                    f"index assignment requires an array, found {base_type}",
                    target,
                    "type_checker",
                )
                self.node_types[target.node_id] = "error"
                return binding, "error"
            if index_type != "i32":
                self.error(
                    "AX-INDEX-0003",
                    f"array index must be i32, found {index_type}",
                    target.fields["index"],
                    "type_checker",
                )
                self.node_types[target.node_id] = "error"
                return binding, "error"
            element_type, length = array
            index_expression = target.fields["index"]
            if index_expression.kind == "IntegerLiteral":
                index = index_expression.fields["value"]
                if not 0 <= index < length:
                    self.error(
                        "AX-INDEX-0001",
                        f"constant array index {index} is outside 0..{length - 1}",
                        index_expression,
                        "type_checker",
                    )
                    self.node_types[target.node_id] = "error"
                    return binding, "error"
            else:
                self.function_facts[function_name]["bounds_check_sites"] += 1
                self.function_facts[function_name]["panic_sites"] += 1
            self.references.append(
                {
                    "node_id": target.node_id,
                    "name": "[]",
                    "kind": "index_write",
                    "target_node_id": binding.node_id if binding is not None else target.node_id,
                }
            )
            self.function_facts[function_name]["index_writes"] += 1
            self.node_types[target.node_id] = element_type
            return binding, element_type

        self.error(
            "AX-MUT-0002",
            f"assignment target is not an l-value: {target.kind}",
            target,
            "type_checker",
        )
        self.node_types[target.node_id] = "error"
        return None, "error"
