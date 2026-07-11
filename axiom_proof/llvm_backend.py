from __future__ import annotations

from dataclasses import dataclass
import re

from .arithmetic import (
    PANIC_ADD_OVERFLOW,
    PANIC_DIVIDE_BY_ZERO,
    PANIC_DIVIDE_OVERFLOW,
    PANIC_MUL_OVERFLOW,
    PANIC_REMAINDER_BY_ZERO,
    PANIC_REMAINDER_OVERFLOW,
    PANIC_SUB_OVERFLOW,
)
from .model import Node


@dataclass
class FunctionContext:
    lines: list[str]
    registers: int = 0
    labels: int = 0

    def register(self) -> str:
        self.registers += 1
        return f"%v{self.registers}"

    def label(self, prefix: str) -> str:
        self.labels += 1
        return f"{prefix}{self.labels}"


@dataclass(frozen=True)
class Storage:
    slot: str
    type_name: str
    mutable: bool


class LLVMBackend:
    def __init__(self, program: Node, target_triple: str = "x86_64-unknown-linux-gnu"):
        self.program = program
        self.target_triple = target_triple
        self.signatures = {
            function.fields["name"]: function
            for function in program.fields["functions"]
        }
        self.binding_slots: dict[str, str] = {}

    def emit(self) -> str:
        parts = [
            "; Axiom vertical proof LLVM IR",
            f'target triple = "{self.target_triple}"',
            "",
            "declare {i32, i1} @llvm.sadd.with.overflow.i32(i32, i32)",
            "declare {i32, i1} @llvm.ssub.with.overflow.i32(i32, i32)",
            "declare {i32, i1} @llvm.smul.with.overflow.i32(i32, i32)",
            "declare void @axiom_panic_i32(i32) noreturn",
            "",
        ]
        for function in self.program.fields["functions"]:
            parts.extend(self.emit_function(function))
            parts.append("")
        return "\n".join(parts)

    def llvm_type(self, type_name: str) -> str:
        if type_name == "i32":
            return "i32"
        if type_name == "bool":
            return "i1"
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

    def emit_function(self, function: Node) -> list[str]:
        context = FunctionContext([])
        parameters = []
        environment: dict[str, Storage] = {}
        entry_allocas: list[str] = []
        entry_initialization: list[str] = []

        for index, parameter in enumerate(function.fields["parameters"]):
            type_name = parameter.fields["type_name"]
            llvm_type = self.llvm_type(type_name)
            incoming = f"%arg{index}"
            parameters.append(f"{llvm_type} {incoming}")
            slot = self.slot_for_node(parameter, parameter.fields["name"], "param")
            entry_allocas.append(f"  {slot} = alloca {llvm_type}")
            entry_initialization.append(f"  store {llvm_type} {incoming}, ptr {slot}")
            environment[parameter.fields["name"]] = Storage(slot, type_name, False)

        for binding in self.collect_bindings(function.fields["body"]):
            type_name = binding.fields["type_name"]
            llvm_type = self.llvm_type(type_name)
            slot = self.slot_for_node(binding, binding.fields["name"], "local")
            entry_allocas.append(f"  {slot} = alloca {llvm_type}")

        return_type = self.llvm_type(function.fields["return_type"])
        header = f"define {return_type} @{function.fields['name']}({', '.join(parameters)}) {{"
        context.lines = [header, "entry:", *entry_allocas, *entry_initialization]
        terminated = self.emit_block(function.fields["body"], environment, context)
        if not terminated:
            raise ValueError(f"function {function.fields['name']} lacks a terminating return")
        context.lines.append("}")
        return context.lines

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

    def emit_panic_block(
        self,
        context: FunctionContext,
        label: str,
        exit_code: int,
    ) -> None:
        context.lines.append(f"{label}:")
        context.lines.append(f"  call void @axiom_panic_i32(i32 {exit_code})")
        context.lines.append("  unreachable")

    def emit_checked_overflow(
        self,
        context: FunctionContext,
        intrinsic: str,
        left: str,
        right: str,
        exit_code: int,
    ) -> str:
        pair = context.register()
        value = context.register()
        overflow = context.register()
        fail_label = context.label("arith_fail")
        ok_label = context.label("arith_ok")
        context.lines.append(
            f"  {pair} = call {{i32, i1}} @{intrinsic}(i32 {left}, i32 {right})"
        )
        context.lines.append(f"  {value} = extractvalue {{i32, i1}} {pair}, 0")
        context.lines.append(f"  {overflow} = extractvalue {{i32, i1}} {pair}, 1")
        context.lines.append(f"  br i1 {overflow}, label %{fail_label}, label %{ok_label}")
        self.emit_panic_block(context, fail_label, exit_code)
        context.lines.append(f"{ok_label}:")
        return value

    def emit_checked_division(
        self,
        context: FunctionContext,
        left: str,
        right: str,
        *,
        remainder: bool,
    ) -> str:
        zero = context.register()
        is_min = context.register()
        is_negative_one = context.register()
        overflow = context.register()
        zero_fail = context.label("div_zero_fail" if not remainder else "rem_zero_fail")
        overflow_check = context.label("div_overflow_check" if not remainder else "rem_overflow_check")
        overflow_fail = context.label("div_overflow_fail" if not remainder else "rem_overflow_fail")
        ok_label = context.label("div_ok" if not remainder else "rem_ok")

        context.lines.append(f"  {zero} = icmp eq i32 {right}, 0")
        context.lines.append(f"  br i1 {zero}, label %{zero_fail}, label %{overflow_check}")
        self.emit_panic_block(
            context,
            zero_fail,
            PANIC_REMAINDER_BY_ZERO if remainder else PANIC_DIVIDE_BY_ZERO,
        )
        context.lines.append(f"{overflow_check}:")
        context.lines.append(f"  {is_min} = icmp eq i32 {left}, -2147483648")
        context.lines.append(f"  {is_negative_one} = icmp eq i32 {right}, -1")
        context.lines.append(f"  {overflow} = and i1 {is_min}, {is_negative_one}")
        context.lines.append(f"  br i1 {overflow}, label %{overflow_fail}, label %{ok_label}")
        self.emit_panic_block(
            context,
            overflow_fail,
            PANIC_REMAINDER_OVERFLOW if remainder else PANIC_DIVIDE_OVERFLOW,
        )
        context.lines.append(f"{ok_label}:")
        result = context.register()
        instruction = "srem" if remainder else "sdiv"
        context.lines.append(f"  {result} = {instruction} i32 {left}, {right}")
        return result

    def emit_expr(
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
                f"  {result} = call {self.llvm_type(return_type)} @{function.fields['name']}({', '.join(arguments)})"
            )
            return result, return_type
        if expression.kind == "BinaryExpr":
            left, left_type = self.emit_expr(expression.fields["left"], environment, context)
            right, right_type = self.emit_expr(expression.fields["right"], environment, context)
            if left_type != right_type:
                raise ValueError("LLVM backend received mismatched binary operands")
            operator = expression.fields["operator"]
            if operator == "+":
                return (
                    self.emit_checked_overflow(
                        context,
                        "llvm.sadd.with.overflow.i32",
                        left,
                        right,
                        PANIC_ADD_OVERFLOW,
                    ),
                    "i32",
                )
            if operator == "-":
                return (
                    self.emit_checked_overflow(
                        context,
                        "llvm.ssub.with.overflow.i32",
                        left,
                        right,
                        PANIC_SUB_OVERFLOW,
                    ),
                    "i32",
                )
            if operator == "*":
                return (
                    self.emit_checked_overflow(
                        context,
                        "llvm.smul.with.overflow.i32",
                        left,
                        right,
                        PANIC_MUL_OVERFLOW,
                    ),
                    "i32",
                )
            if operator == "/":
                return self.emit_checked_division(context, left, right, remainder=False), "i32"
            if operator == "%":
                return self.emit_checked_division(context, left, right, remainder=True), "i32"
            result = context.register()
            predicate = {
                "<": "slt",
                "<=": "sle",
                ">": "sgt",
                ">=": "sge",
                "==": "eq",
                "!=": "ne",
            }[operator]
            context.lines.append(
                f"  {result} = icmp {predicate} {self.llvm_type(left_type)} {left}, {right}"
            )
            return result, "bool"
        raise ValueError(f"unsupported LLVM expression: {expression.kind}")
