from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .arithmetic import checked_add, checked_mul, checked_sub, truncating_division, truncating_remainder
from .model import Node
from .runtime_faults import array_index_out_of_bounds


@dataclass(frozen=True)
class StructValue:
    type_name: str
    fields: tuple[tuple[str, Any], ...]

    def get(self, name: str) -> Any:
        for field_name, value in self.fields:
            if field_name == name:
                return value
        raise RuntimeError(f"AX-RUNTIME-STRUCT-0001: missing field {name} on {self.type_name}")

    def with_field(self, name: str, value: Any) -> "StructValue":
        found = False
        fields: list[tuple[str, Any]] = []
        for field_name, field_value in self.fields:
            if field_name == name:
                fields.append((field_name, value))
                found = True
            else:
                fields.append((field_name, field_value))
        if not found:
            raise RuntimeError(f"AX-RUNTIME-STRUCT-0001: missing field {name} on {self.type_name}")
        return StructValue(self.type_name, tuple(fields))


@dataclass(frozen=True)
class ArrayValue:
    items: tuple[Any, ...]

    def with_item(self, index: int, value: Any) -> "ArrayValue":
        if not 0 <= index < len(self.items):
            raise array_index_out_of_bounds(index, len(self.items))
        items = list(self.items)
        items[index] = value
        return ArrayValue(tuple(items))


@dataclass
class Returned(Exception):
    value: Any


@dataclass
class RuntimeBinding:
    value: Any
    mutable: bool


@dataclass(frozen=True)
class RuntimeLocation:
    environment: Any
    root_name: str
    selectors: tuple[tuple[str, Any], ...]
    mutable: bool


@dataclass(frozen=True)
class RuntimeReference:
    location: RuntimeLocation
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
                    value = self.eval_expr(statement.fields["value"], environment)
                    self.assign_lvalue(statement.fields["target"], value, environment)
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


    def resolve_lvalue(
        self,
        target: Node,
        environment: RuntimeEnvironment,
    ) -> RuntimeLocation:
        if target.kind == "NameExpr":
            name = target.fields["name"]
            binding = environment.resolve(name)
            return RuntimeLocation(environment, name, (), binding.mutable)
        if target.kind == "DerefExpr":
            reference = self.eval_expr(target.fields["reference"], environment)
            if not isinstance(reference, RuntimeReference):
                raise RuntimeError("AX-RUNTIME-REF-0001: dereference requires a reference")
            return RuntimeLocation(
                reference.location.environment,
                reference.location.root_name,
                reference.location.selectors,
                reference.mutable,
            )
        if target.kind == "FieldExpr":
            base = self.resolve_lvalue(target.fields["base"], environment)
            return RuntimeLocation(
                base.environment,
                base.root_name,
                (*base.selectors, ("field", target.fields["field"])),
                base.mutable,
            )
        if target.kind == "IndexExpr":
            base = self.resolve_lvalue(target.fields["base"], environment)
            index = self.eval_expr(target.fields["index"], environment)
            return RuntimeLocation(
                base.environment,
                base.root_name,
                (*base.selectors, ("index", index)),
                base.mutable,
            )
        raise RuntimeError(f"AX-RUNTIME-MUT-0001: unsupported l-value {target.kind}")

    def read_path(self, current: Any, selectors: tuple[tuple[str, Any], ...]) -> Any:
        for kind, key in selectors:
            if kind == "field":
                if not isinstance(current, StructValue):
                    raise RuntimeError("AX-RUNTIME-STRUCT-0002: field access on non-struct value")
                current = current.get(key)
            elif kind == "index":
                if not isinstance(current, ArrayValue):
                    raise RuntimeError("AX-RUNTIME-INDEX-0002: index access on non-array value")
                if not 0 <= key < len(current.items):
                    raise array_index_out_of_bounds(key, len(current.items))
                current = current.items[key]
            else:
                raise RuntimeError(f"AX-RUNTIME-MUT-0002: unsupported l-value selector {kind}")
        return current

    def read_location(self, location: RuntimeLocation) -> Any:
        return self.read_path(
            location.environment.get(location.root_name),
            location.selectors,
        )

    def replace_path(
        self,
        current: Any,
        selectors: tuple[tuple[str, Any], ...],
        replacement: Any,
    ) -> Any:
        if not selectors:
            return replacement
        kind, key = selectors[0]
        remaining = selectors[1:]
        if kind == "field":
            if not isinstance(current, StructValue):
                raise RuntimeError("AX-RUNTIME-STRUCT-0002: field assignment on non-struct value")
            updated = self.replace_path(current.get(key), remaining, replacement)
            return current.with_field(key, updated)
        if kind == "index":
            if not isinstance(current, ArrayValue):
                raise RuntimeError("AX-RUNTIME-INDEX-0002: index assignment on non-array value")
            if not 0 <= key < len(current.items):
                raise array_index_out_of_bounds(key, len(current.items))
            updated = self.replace_path(current.items[key], remaining, replacement)
            return current.with_item(key, updated)
        raise RuntimeError(f"AX-RUNTIME-MUT-0002: unsupported l-value selector {kind}")

    def assign_location(self, location: RuntimeLocation, value: Any) -> None:
        if not location.mutable:
            raise RuntimeError("AX-RUNTIME-REF-0002: write through immutable location")
        root_value = location.environment.get(location.root_name)
        location.environment.assign(
            location.root_name,
            self.replace_path(root_value, location.selectors, value),
        )

    def assign_lvalue(
        self,
        target: Node,
        value: Any,
        environment: RuntimeEnvironment,
    ) -> None:
        self.assign_location(self.resolve_lvalue(target, environment), value)

    def eval_expr(self, expression: Node, environment: RuntimeEnvironment) -> Any:
        self.tick()
        if expression.kind in {"IntegerLiteral", "BoolLiteral"}:
            return expression.fields["value"]
        if expression.kind == "NameExpr":
            return environment.get(expression.fields["name"])
        if expression.kind == "BorrowExpr":
            location = self.resolve_lvalue(expression.fields["target"], environment)
            mutable = bool(expression.fields["mutable"])
            if mutable and not location.mutable:
                raise RuntimeError("AX-RUNTIME-REF-0003: mutable borrow of immutable location")
            return RuntimeReference(location, mutable)
        if expression.kind == "DerefExpr":
            reference = self.eval_expr(expression.fields["reference"], environment)
            if not isinstance(reference, RuntimeReference):
                raise RuntimeError("AX-RUNTIME-REF-0001: dereference requires a reference")
            return self.read_location(reference.location)
        if expression.kind == "CallExpr":
            return self.call(
                expression.fields["callee"],
                [self.eval_expr(argument, environment) for argument in expression.fields["arguments"]],
            )
        if expression.kind == "StructLiteral":
            return StructValue(
                expression.fields["type_name"],
                tuple(
                    (field.fields["name"], self.eval_expr(field.fields["value"], environment))
                    for field in expression.fields["fields"]
                ),
            )
        if expression.kind == "ArrayLiteral":
            return ArrayValue(tuple(self.eval_expr(item, environment) for item in expression.fields["elements"]))
        if expression.kind == "FieldExpr":
            base = self.eval_expr(expression.fields["base"], environment)
            if not isinstance(base, StructValue):
                raise RuntimeError("AX-RUNTIME-STRUCT-0002: field access on non-struct value")
            return base.get(expression.fields["field"])
        if expression.kind == "IndexExpr":
            base = self.eval_expr(expression.fields["base"], environment)
            index = self.eval_expr(expression.fields["index"], environment)
            if not isinstance(base, ArrayValue):
                raise RuntimeError("AX-RUNTIME-INDEX-0002: index access on non-array value")
            if not 0 <= index < len(base.items):
                raise array_index_out_of_bounds(index, len(base.items))
            return base.items[index]
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
