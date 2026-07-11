from __future__ import annotations

from .model import Node
from .llvm_model import FunctionContext, Storage


class LLVMStatementMixin:
    def emit_block(
        self,
        block: Node,
        environment: dict[str, Storage],
        context: FunctionContext,
    ) -> bool:
        for statement in block.fields["statements"]:
            if statement.kind in {"LetStmt", "VarStmt"}:
                value, type_name = self.emit_expr(statement.fields["value"], environment, context)
                declared_type = statement.fields["type_name"]
                if type_name != declared_type:
                    raise ValueError("LLVM backend received a mistyped binding")
                slot = self.slot_for_node(statement, statement.fields["name"], "local")
                context.lines.append(f"  store {self.llvm_type(type_name)} {value}, ptr {slot}")
                environment[statement.fields["name"]] = Storage(
                    slot=slot,
                    type_name=type_name,
                    mutable=statement.kind == "VarStmt",
                )
            elif statement.kind == "AssignmentStmt":
                target = environment[statement.fields["target"]]
                if not target.mutable:
                    raise ValueError("LLVM backend received assignment to immutable storage")
                value, type_name = self.emit_expr(statement.fields["value"], environment, context)
                if type_name != target.type_name:
                    raise ValueError("LLVM backend received mistyped assignment")
                context.lines.append(f"  store {self.llvm_type(type_name)} {value}, ptr {target.slot}")
            elif statement.kind == "ReturnStmt":
                value, type_name = self.emit_expr(statement.fields["value"], environment, context)
                context.lines.append(f"  ret {self.llvm_type(type_name)} {value}")
                return True
            elif statement.kind == "ExprStmt":
                self.emit_expr(statement.fields["expression"], environment, context)
            elif statement.kind == "IfStmt":
                condition, condition_type = self.emit_expr(statement.fields["condition"], environment, context)
                if condition_type != "bool":
                    raise ValueError("LLVM backend received non-bool if condition")
                then_label = context.label("if_then")
                else_label = context.label("if_else")
                cont_label = context.label("if_cont")
                has_else = isinstance(statement.fields.get("else_block"), Node)
                context.lines.append(
                    f"  br i1 {condition}, label %{then_label}, label %{else_label if has_else else cont_label}"
                )
                context.lines.append(f"{then_label}:")
                then_terminated = self.emit_block(
                    statement.fields["then_block"],
                    dict(environment),
                    context,
                )
                if not then_terminated:
                    context.lines.append(f"  br label %{cont_label}")

                else_terminated = False
                if has_else:
                    context.lines.append(f"{else_label}:")
                    else_terminated = self.emit_block(
                        statement.fields["else_block"],
                        dict(environment),
                        context,
                    )
                    if not else_terminated:
                        context.lines.append(f"  br label %{cont_label}")

                if has_else and then_terminated and else_terminated:
                    return True
                context.lines.append(f"{cont_label}:")
            elif statement.kind == "WhileStmt":
                condition_label = context.label("while_cond")
                body_label = context.label("while_body")
                after_label = context.label("while_after")
                context.lines.append(f"  br label %{condition_label}")
                context.lines.append(f"{condition_label}:")
                condition, condition_type = self.emit_expr(
                    statement.fields["condition"],
                    environment,
                    context,
                )
                if condition_type != "bool":
                    raise ValueError("LLVM backend received non-bool while condition")
                context.lines.append(
                    f"  br i1 {condition}, label %{body_label}, label %{after_label}"
                )
                context.lines.append(f"{body_label}:")
                body_terminated = self.emit_block(
                    statement.fields["body"],
                    dict(environment),
                    context,
                )
                if not body_terminated:
                    context.lines.append(f"  br label %{condition_label}")
                context.lines.append(f"{after_label}:")
            else:
                raise ValueError(f"unsupported LLVM statement: {statement.kind}")
        return False

