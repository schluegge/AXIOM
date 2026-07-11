from __future__ import annotations

import re

from .model import Node
from .semantic import SemanticAnalyzer
from .type_system import TypeRegistry
from .llvm_model import FunctionContext, Storage
from .llvm_support import LLVMSupportMixin
from .llvm_expressions import LLVMExpressionMixin
from .llvm_scalar_expressions import LLVMScalarExpressionMixin
from .llvm_aggregate_expressions import LLVMAggregateExpressionMixin
from .llvm_binary_expressions import LLVMBinaryExpressionMixin
from .llvm_arithmetic import LLVMArithmeticMixin
from .llvm_statements import LLVMStatementMixin
from .llvm_lvalues import LLVMLValueMixin


class LLVMBackend(
    LLVMSupportMixin,
    LLVMArithmeticMixin,
    LLVMScalarExpressionMixin,
    LLVMAggregateExpressionMixin,
    LLVMBinaryExpressionMixin,
    LLVMExpressionMixin,
    LLVMLValueMixin,
    LLVMStatementMixin,
):
    def __init__(
        self,
        program: Node,
        target_triple: str = "x86_64-unknown-linux-gnu",
        node_types: dict[str, str] | None = None,
    ):
        self.program = program
        self.target_triple = target_triple
        self.signatures = {
            function.fields["name"]: function
            for function in program.fields["functions"]
        }
        self.registry = TypeRegistry.from_program(program)
        if node_types is None:
            semantic = SemanticAnalyzer(program)
            semantic.analyze()
            if semantic.diagnostics:
                raise ValueError("LLVM backend requires a semantically valid program")
            node_types = semantic.node_types
        self.node_types = node_types
        self.binding_slots: dict[str, str] = {}
        self.dynamic_index_slots: dict[str, str] = {}

    def emit(self) -> str:
        parts = [
            "; Axiom vertical proof LLVM IR",
            f'target triple = "{self.target_triple}"',
            "",
        ]
        for declaration in self.program.fields.get("structs", []):
            name = declaration.fields["name"]
            field_types = ", ".join(
                self.llvm_type(field.fields["type_name"])
                for field in declaration.fields["fields"]
            )
            parts.append(f"{self.llvm_struct_name(name)} = type {{ {field_types} }}")
        if self.program.fields.get("structs", []):
            parts.append("")
        parts.extend(
            [
                "declare {i32, i1} @llvm.sadd.with.overflow.i32(i32, i32)",
                "declare {i32, i1} @llvm.ssub.with.overflow.i32(i32, i32)",
                "declare {i32, i1} @llvm.smul.with.overflow.i32(i32, i32)",
                "declare void @axiom_panic_i32(i32) noreturn",
                "",
            ]
        )
        for function in self.program.fields["functions"]:
            parts.extend(self.emit_function(function))
            parts.append("")
        return "\n".join(parts)

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

        seen_indexes: set[str] = set()
        for index_expression in self.collect_dynamic_indexes(function.fields["body"]):
            if index_expression.node_id in seen_indexes:
                continue
            seen_indexes.add(index_expression.node_id)
            base_type = self.node_types[index_expression.fields["base"].node_id]
            slot = self.dynamic_slot_for(index_expression)
            entry_allocas.append(f"  {slot} = alloca {self.llvm_type(base_type)}")

        return_type = self.llvm_type(function.fields["return_type"])
        header = f"define {return_type} @{function.fields['name']}({', '.join(parameters)}) {{"
        context.lines = [header, "entry:", *entry_allocas, *entry_initialization]
        terminated = self.emit_block(function.fields["body"], environment, context)
        if not terminated:
            raise ValueError(f"function {function.fields['name']} lacks a terminating return")
        context.lines.append("}")
        return context.lines
