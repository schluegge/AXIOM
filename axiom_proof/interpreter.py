from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .arithmetic import checked_add, checked_mul, checked_sub, truncating_division, truncating_remainder
from .model import Node


@dataclass
class Returned(Exception):
    value: Any


@dataclass
class RuntimeBinding:
    value: Any
    mutable: bool


class RuntimeEnvironment:
    def __init__(self) -> None:
        self.scopes: list[dict[str, RuntimeBinding]] = [{}]

    def push(self) -> None:
        self.scopes.append({})

    def pop(self) -> None:
        if len(self.scopes) == 1:
            raise RuntimeError("AX-RUNTIME-0006: attempted to pop function scope")
        self.scopes.pop()

    def define(self, name: str, value: Any, *, mutable: bool) -> None:
        if name in self.scopes[-1]:
            raise RuntimeError(f"AX-RUNTIME-0007: duplicate runtime binding: {name}")
        self.scopes[-1][name] = RuntimeBinding(value, mutable)

    def resolve(self, name: str) -> RuntimeBinding:
        for scope in reversed(self.scopes):
            binding = scope.get(name)
            if binding is not None:
                return binding
        raise RuntimeError(f"AX-RUNTIME-0005: unresolved runtime binding: {name}")

    def get(self, name: str) -> Any:
        return self.resolve(name).value

    def assign(self, name: str, value: Any) -> None:
        binding = self.resolve(name)
        if not binding.mutable:
            raise RuntimeError(f"AX-RUNTIME-0004: immutable runtime binding: {name}")
        binding.value = value


class Interpreter:
    def __init__(self, program: Node, step_limit: int = 100_000):
        self.functions = {function.fields["name"]: function for function in program.fields["functions"]}
        self.step_limit = step_limit
        self.steps = 0
        self.call_count = 0

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.step_limit:
            raise RuntimeError("AX-RUNTIME-0001: interpreter step limit exceeded")

    def run_main(self) -> int:
        value = self.call("main", [])
        if type(value) is not int:
            raise RuntimeError("AX-RUNTIME-0002: main did not return i32")
        return value

    def call(self, name: str, arguments: list[Any]) -> Any:
        self.tick()
        self.call_count += 1
        function = self.functions[name]
        environment = RuntimeEnvironment()
        for parameter, value in zip(function.fields["parameters"], arguments, strict=True):
            environment.define(parameter.fields["name"], value, mutable=False)
        try:
            self.execute_block(function.fields["body"], environment, create_scope=False)
        except Returned as returned:
            return returned.value
        raise RuntimeError(f"AX-RUNTIME-0003: function {name} completed without return")

    def execute_block(self, block: Node, environment: RuntimeEnvironment, *, create_scope: bool = True) -> None:
        if create_scope:
            environment.push()
        try:
            for statement in block.fields["statements"]:
                self.tick()
                if statement.kind in {"LetStmt", "VarStmt"}:
                    environment.define(
                        statement.fields["name"],
                        self.eval_expr(statement.fields["value"], environment),
                        mutable=statement.kind == "VarStmt",
                    )
                elif statement.kind == "AssignmentStmt":
                    environment.assign(
                        statement.fields["target"],
                        self.eval_expr(statement.fields["value"], environment),
                    )
                elif statement.kind == "ReturnStmt":
                    raise Returned(self.eval_expr(statement.fields["value"], environment))
                elif statement.kind == "ExprStmt":
                    self.eval_expr(statement.fields["expression"], environment)
                elif statement.kind == "IfStmt":
                    condition = self.eval_expr(statement.fields["condition"], environment)
                    if condition:
                        self.execute_block(statement.fields["then_block"], environment)
                    else:
                        else_block = statement.fields.get("else_block")
                        if isinstance(else_block, Node):
                            self.execute_block(else_block, environment)
                elif statement.kind == "WhileStmt":
                    while self.eval_expr(statement.fields["condition"], environment):
                        self.tick()
                        self.execute_block(statement.fields["body"], environment)
                else:
                    raise RuntimeError(f"unsupported statement: {statement.kind}")
        finally:
            if create_scope:
                environment.pop()

    def eval_expr(self, expression: Node, environment: RuntimeEnvironment) -> Any:
        self.tick()
        if expression.kind in {"IntegerLiteral", "BoolLiteral"}:
            return expression.fields["value"]
        if expression.kind == "NameExpr":
            return environment.get(expression.fields["name"])
        if expression.kind == "CallExpr":
            return self.call(
                expression.fields["callee"],
                [self.eval_expr(argument, environment) for argument in expression.fields["arguments"]],
            )
        if expression.kind == "BinaryExpr":
            left = self.eval_expr(expression.fields["left"], environment)
            right = self.eval_expr(expression.fields["right"], environment)
            operator = expression.fields["operator"]
            if operator == "+":
                return checked_add(left, right)
            if operator == "-":
                return checked_sub(left, right)
            if operator == "*":
                return checked_mul(left, right)
            if operator == "/":
                return truncating_division(left, right)
            if operator == "%":
                return truncating_remainder(left, right)
            if operator == "<":
                return left < right
            if operator == "<=":
                return left <= right
            if operator == ">":
                return left > right
            if operator == ">=":
                return left >= right
            if operator == "==":
                return left == right
            if operator == "!=":
                return left != right
            raise RuntimeError(f"unsupported operator: {operator}")
        raise RuntimeError(f"unsupported expression: {expression.kind}")
