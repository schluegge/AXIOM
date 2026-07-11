from __future__ import annotations

from .llvm_model import FunctionContext, Storage
from .model import Node


class LLVMScalarExpressionMixin:
    def emit_scalar_expr(
        self,
        expression: Node,
        environment: dict[str, Storage],
        context: FunctionContext,
    ) -> tuple[str, str]:
        if expression.kind == "IntegerLiteral":
            return str(expression.fields["value"]), "i32"
        if expression.kind == "BoolLiteral":
            return ("1" if expression.fields["value"] else "0"), "bool"
        if expression.kind == "NameExpr":
            storage = environment[expression.fields["name"]]
            result = context.register()
            llvm_type = self.llvm_type(storage.type_name)
            context.lines.append(f"  {result} = load {llvm_type}, ptr {storage.slot}")
            return result, storage.type_name
        if expression.kind == "CallExpr":
            function = self.signatures[expression.fields["callee"]]
            arguments = []
            for argument, parameter in zip(
                expression.fields["arguments"], function.fields["parameters"], strict=True
            ):
                value, type_name = self.emit_expr(argument, environment, context)
                arguments.append(f"{self.llvm_type(type_name)} {value}")
            return_type = function.fields["return_type"]
            result = context.register()
            context.lines.append(
                f"  {result} = call {self.llvm_type(return_type)} "
                f"@{function.fields['name']}({', '.join(arguments)})"
            )
            return result, return_type
        raise ValueError(f"unsupported scalar LLVM expression: {expression.kind}")
