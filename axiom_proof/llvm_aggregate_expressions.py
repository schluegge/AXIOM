from __future__ import annotations

from .llvm_model import FunctionContext, Storage
from .model import Node
from .type_system import parse_array_type


class LLVMAggregateExpressionMixin:
    def emit_aggregate_expr(
        self,
        expression: Node,
        environment: dict[str, Storage],
        context: FunctionContext,
    ) -> tuple[str, str]:
        if expression.kind == "StructLiteral":
            type_name = expression.fields["type_name"]
            definition = self.registry.struct(type_name)
            if definition is None:
                raise ValueError(f"unknown struct literal in LLVM backend: {type_name}")
            initializers = {field.fields["name"]: field for field in expression.fields["fields"]}
            aggregate = "poison"
            llvm_struct = self.llvm_type(type_name)
            for index, field in enumerate(definition.fields):
                initializer = initializers[field.name]
                value, actual_type = self.emit_expr(initializer.fields["value"], environment, context)
                if actual_type != field.type_name:
                    raise ValueError("LLVM backend received mistyped struct literal")
                inserted = context.register()
                context.lines.append(
                    f"  {inserted} = insertvalue {llvm_struct} {aggregate}, "
                    f"{self.llvm_type(field.type_name)} {value}, {index}"
                )
                aggregate = inserted
            return aggregate, type_name

        if expression.kind == "ArrayLiteral":
            type_name = self.node_types[expression.node_id]
            array = parse_array_type(type_name)
            if array is None:
                raise ValueError("LLVM backend received untyped array literal")
            element_type, _ = array
            llvm_array = self.llvm_type(type_name)
            aggregate = "poison"
            for index, element in enumerate(expression.fields["elements"]):
                value, actual_type = self.emit_expr(element, environment, context)
                if actual_type != element_type:
                    raise ValueError("LLVM backend received heterogeneous array literal")
                inserted = context.register()
                context.lines.append(
                    f"  {inserted} = insertvalue {llvm_array} {aggregate}, "
                    f"{self.llvm_type(element_type)} {value}, {index}"
                )
                aggregate = inserted
            return aggregate, type_name

        if expression.kind == "FieldExpr":
            base, base_type = self.emit_expr(expression.fields["base"], environment, context)
            definition = self.registry.struct(base_type)
            if definition is None:
                raise ValueError("LLVM backend received field access on non-struct")
            index = definition.field_index(expression.fields["field"])
            if index is None:
                raise ValueError("LLVM backend received unknown struct field")
            field = definition.fields[index]
            result = context.register()
            context.lines.append(
                f"  {result} = extractvalue {self.llvm_type(base_type)} {base}, {index}"
            )
            return result, field.type_name

        if expression.kind == "IndexExpr":
            base, base_type = self.emit_expr(expression.fields["base"], environment, context)
            index_expression = expression.fields["index"]
            array = parse_array_type(base_type)
            if array is None:
                raise ValueError("LLVM backend received index on non-array")
            element_type, _ = array
            if index_expression.kind == "IntegerLiteral":
                index = index_expression.fields["value"]
                result = context.register()
                context.lines.append(
                    f"  {result} = extractvalue {self.llvm_type(base_type)} {base}, {index}"
                )
                return result, element_type
            index_value, index_type = self.emit_expr(index_expression, environment, context)
            if index_type != "i32":
                raise ValueError("LLVM backend received non-i32 index")
            return self.emit_dynamic_index(expression, base, base_type, index_value, context)

        raise ValueError(f"unsupported aggregate LLVM expression: {expression.kind}")
