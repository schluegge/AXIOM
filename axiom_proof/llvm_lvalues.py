from __future__ import annotations

from .arithmetic import PANIC_INDEX_OUT_OF_BOUNDS
from .llvm_model import FunctionContext, Storage
from .model import Node
from .type_system import parse_array_type


class LLVMLValueMixin:
    def emit_lvalue_ptr(
        self,
        target: Node,
        environment: dict[str, Storage],
        context: FunctionContext,
    ) -> tuple[str, str]:
        if target.kind == "NameExpr":
            storage = environment[target.fields["name"]]
            if not storage.mutable:
                raise ValueError("LLVM backend received assignment through immutable storage")
            return storage.slot, storage.type_name

        if target.kind == "FieldExpr":
            base_ptr, base_type = self.emit_lvalue_ptr(target.fields["base"], environment, context)
            definition = self.registry.struct(base_type)
            if definition is None:
                raise ValueError("LLVM backend received field l-value on non-struct")
            field_index = definition.field_index(target.fields["field"])
            if field_index is None:
                raise ValueError("LLVM backend received unknown field l-value")
            field = definition.fields[field_index]
            pointer = context.register()
            context.lines.append(
                f"  {pointer} = getelementptr {self.llvm_type(base_type)}, ptr {base_ptr}, "
                f"i32 0, i32 {field_index}"
            )
            return pointer, field.type_name

        if target.kind == "IndexExpr":
            base_ptr, base_type = self.emit_lvalue_ptr(target.fields["base"], environment, context)
            array = parse_array_type(base_type)
            if array is None:
                raise ValueError("LLVM backend received index l-value on non-array")
            element_type, length = array
            index_expression = target.fields["index"]
            if index_expression.kind == "IntegerLiteral":
                index_value = str(index_expression.fields["value"])
            else:
                index_value, index_type = self.emit_expr(index_expression, environment, context)
                if index_type != "i32":
                    raise ValueError("LLVM backend received non-i32 l-value index")
                self.emit_index_guard(index_value, length, context)
            pointer = context.register()
            context.lines.append(
                f"  {pointer} = getelementptr {self.llvm_type(base_type)}, ptr {base_ptr}, "
                f"i32 0, i32 {index_value}"
            )
            return pointer, element_type

        raise ValueError(f"LLVM backend received non-l-value target: {target.kind}")

    def emit_index_guard(self, index_value: str, length: int, context: FunctionContext) -> None:
        negative = context.register()
        too_high = context.register()
        out_of_bounds = context.register()
        fail_label = context.label("index_write_fail")
        ok_label = context.label("index_write_ok")
        context.lines.append(f"  {negative} = icmp slt i32 {index_value}, 0")
        context.lines.append(f"  {too_high} = icmp sge i32 {index_value}, {length}")
        context.lines.append(f"  {out_of_bounds} = or i1 {negative}, {too_high}")
        context.lines.append(f"  br i1 {out_of_bounds}, label %{fail_label}, label %{ok_label}")
        self.emit_panic_block(context, fail_label, PANIC_INDEX_OUT_OF_BOUNDS)
        context.lines.append(f"{ok_label}:")
