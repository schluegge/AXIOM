from __future__ import annotations

from .model import Node
from .semantic_model import LValueInfo, LocalBinding
from .type_system import parse_array_type, parse_reference_type


class SemanticLValueMixin:
    def type_lvalue(
        self,
        target: Node,
        scopes: list[dict[str, LocalBinding]],
        function_name: str,
        *,
        purpose: str = "write",
    ) -> LValueInfo:
        if target.kind == "NameExpr":
            name = target.fields["name"]
            binding = self.resolve_local(scopes, name)
            if binding is None:
                self.error("AX-NAME-0001", f"unresolved l-value: {name}", target, "resolver")
                self.node_types[target.node_id] = "error"
                return LValueInfo(None, "error", False)
            if purpose == "write":
                self.check_root_write(binding, target)
            self.references.append(
                {
                    "node_id": target.node_id,
                    "name": name,
                    "kind": "assignment_root" if purpose == "write" else "borrow_root",
                    "target_node_id": binding.node_id,
                }
            )
            self.node_types[target.node_id] = binding.type_name
            return LValueInfo(binding, binding.type_name, binding.mutable)

        if target.kind == "DerefExpr":
            if purpose == "borrow":
                self.error(
                    "AX-BORROW-0007",
                    "reborrowing through a reference is outside the v0.7 subset",
                    target,
                    "borrow_checker",
                )
                self.node_types[target.node_id] = "error"
                return LValueInfo(None, "error", False, True)
            reference_type_name = self.type_expr(target.fields["reference"], scopes, function_name)
            parsed = parse_reference_type(reference_type_name)
            if parsed is None:
                if reference_type_name != "error":
                    self.error(
                        "AX-REF-0006",
                        f"dereference assignment requires a reference, found {reference_type_name}",
                        target,
                        "type_checker",
                    )
                self.node_types[target.node_id] = "error"
                return LValueInfo(None, "error", False, True)
            referent, mutable = parsed
            self.node_types[target.node_id] = referent
            self.function_facts[function_name]["deref_writes"] += 1
            self.references.append(
                {
                    "node_id": target.node_id,
                    "name": "*",
                    "kind": "dereference_write",
                    "target_node_id": target.fields["reference"].node_id,
                }
            )
            return LValueInfo(None, referent, mutable, True)

        if target.kind == "FieldExpr":
            base = self.type_lvalue(target.fields["base"], scopes, function_name, purpose=purpose)
            if base.type_name == "error":
                self.node_types[target.node_id] = "error"
                return LValueInfo(base.root_binding, "error", False, base.via_reference)
            definition = self.registry.struct(base.type_name)
            if definition is None:
                self.error(
                    "AX-STRUCT-0008",
                    f"field l-value requires a struct, found {base.type_name}",
                    target,
                    "type_checker",
                )
                self.node_types[target.node_id] = "error"
                return LValueInfo(base.root_binding, "error", False, base.via_reference)
            field_name = target.fields["field"]
            field = definition.field(field_name)
            if field is None:
                self.error(
                    "AX-STRUCT-0009",
                    f"struct {base.type_name} has no field {field_name}",
                    target,
                    "type_checker",
                )
                self.node_types[target.node_id] = "error"
                return LValueInfo(base.root_binding, "error", False, base.via_reference)
            kind = "field_write" if purpose == "write" else "field_borrow"
            self.references.append(
                {"node_id": target.node_id, "name": field_name, "kind": kind, "target_node_id": field.node_id}
            )
            if purpose == "write":
                self.function_facts[function_name]["field_writes"] += 1
            self.node_types[target.node_id] = field.type_name
            return LValueInfo(base.root_binding, field.type_name, base.writable, base.via_reference)

        if target.kind == "IndexExpr":
            base = self.type_lvalue(target.fields["base"], scopes, function_name, purpose=purpose)
            index_type = self.type_expr(target.fields["index"], scopes, function_name)
            if base.type_name == "error" or index_type == "error":
                self.node_types[target.node_id] = "error"
                return LValueInfo(base.root_binding, "error", False, base.via_reference)
            array = parse_array_type(base.type_name)
            if array is None:
                self.error("AX-INDEX-0002", f"index l-value requires an array, found {base.type_name}", target, "type_checker")
                self.node_types[target.node_id] = "error"
                return LValueInfo(base.root_binding, "error", False, base.via_reference)
            if index_type != "i32":
                self.error("AX-INDEX-0003", f"array index must be i32, found {index_type}", target.fields["index"], "type_checker")
                self.node_types[target.node_id] = "error"
                return LValueInfo(base.root_binding, "error", False, base.via_reference)
            element_type, length = array
            index_expression = target.fields["index"]
            if index_expression.kind == "IntegerLiteral":
                index = index_expression.fields["value"]
                if not 0 <= index < length:
                    self.error("AX-INDEX-0001", f"constant array index {index} is outside 0..{length - 1}", index_expression, "type_checker")
                    self.node_types[target.node_id] = "error"
                    return LValueInfo(base.root_binding, "error", False, base.via_reference)
            else:
                self.function_facts[function_name]["bounds_check_sites"] += 1
                self.function_facts[function_name]["panic_sites"] += 1
            kind = "index_write" if purpose == "write" else "index_borrow"
            self.references.append({"node_id": target.node_id, "name": "[]", "kind": kind, "target_node_id": target.fields["base"].node_id})
            if purpose == "write":
                self.function_facts[function_name]["index_writes"] += 1
            self.node_types[target.node_id] = element_type
            return LValueInfo(base.root_binding, element_type, base.writable, base.via_reference)

        self.error("AX-MUT-0002", f"expression {target.kind} is not an l-value", target, "type_checker")
        self.node_types[target.node_id] = "error"
        return LValueInfo(None, "error", False)
