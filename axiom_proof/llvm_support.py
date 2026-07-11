from __future__ import annotations

import re

from .model import Node
from .type_system import parse_array_type


class LLVMSupportMixin:
    def llvm_struct_name(self, name: str) -> str:
        return f"%struct.{self.safe_name(name)}"

    def llvm_type(self, type_name: str) -> str:
        if type_name == "i32":
            return "i32"
        if type_name == "bool":
            return "i1"
        array = parse_array_type(type_name)
        if array is not None:
            element_type, length = array
            return f"[{length} x {self.llvm_type(element_type)}]"
        if self.registry.struct(type_name) is not None:
            return self.llvm_struct_name(type_name)
        raise ValueError(f"unsupported LLVM type: {type_name}")

    def safe_name(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]", "_", value)

    def slot_for_node(self, node: Node, name: str, prefix: str) -> str:
        existing = self.binding_slots.get(node.node_id)
        if existing is not None:
            return existing
        suffix = node.node_id.removeprefix("n_")[:8]
        slot = f"%slot_{prefix}_{self.safe_name(name)}_{suffix}"
        self.binding_slots[node.node_id] = slot
        return slot

    def dynamic_slot_for(self, expression: Node) -> str:
        existing = self.dynamic_index_slots.get(expression.node_id)
        if existing is not None:
            return existing
        suffix = expression.node_id.removeprefix("n_")[:8]
        slot = f"%slot_index_base_{suffix}"
        self.dynamic_index_slots[expression.node_id] = slot
        return slot

    def collect_bindings(self, block: Node) -> list[Node]:
        result: list[Node] = []
        for statement in block.fields["statements"]:
            if statement.kind in {"LetStmt", "VarStmt"}:
                result.append(statement)
            elif statement.kind == "IfStmt":
                result.extend(self.collect_bindings(statement.fields["then_block"]))
                else_block = statement.fields.get("else_block")
                if isinstance(else_block, Node):
                    result.extend(self.collect_bindings(else_block))
            elif statement.kind == "WhileStmt":
                result.extend(self.collect_bindings(statement.fields["body"]))
        return result

    def walk_expr(self, expression: Node) -> list[Node]:
        result = [expression]
        for value in expression.fields.values():
            if isinstance(value, Node):
                result.extend(self.walk_expr(value))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, Node):
                        if item.kind == "FieldInit":
                            result.extend(self.walk_expr(item.fields["value"]))
                        else:
                            result.extend(self.walk_expr(item))
        return result

    def collect_dynamic_indexes(self, block: Node) -> list[Node]:
        expressions: list[Node] = []

        def inspect_statement(statement: Node) -> None:
            for value in statement.fields.values():
                if isinstance(value, Node):
                    if value.kind == "Block":
                        for child in value.fields["statements"]:
                            inspect_statement(child)
                    else:
                        expressions.extend(self.walk_expr(value))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, Node):
                            expressions.extend(self.walk_expr(item))

        for statement in block.fields["statements"]:
            inspect_statement(statement)
        return [
            expression
            for expression in expressions
            if expression.kind == "IndexExpr"
            and expression.fields["index"].kind != "IntegerLiteral"
        ]

