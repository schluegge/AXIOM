from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from axiom_proof.control_flow import build_control_flow_document
from axiom_proof.driver import compile_source, prove
from axiom_proof.formatter import Formatter
from axiom_proof.interpreter import Interpreter
from .agent_b_support import check, exact_diagnostic, fixture, require, sha256, write_temp_source

def ast_surface() -> dict[str, Any]:
        result = compile_source(fixture("loop.ax"))
        require(not result["diagnostics"], "loop fixture has diagnostics")
        assert result["ast"] is not None
        serialized = json.dumps(result["ast"], sort_keys=True)
        for kind in ["VarStmt", "AssignmentStmt", "WhileStmt"]:
            require(f'"kind": "{kind}"' in serialized, f"AST missing {kind}")
        return {"kinds": ["VarStmt", "AssignmentStmt", "WhileStmt"]}

def formatter_reuse() -> str:
        result = compile_source(fixture("loop.ax"))
        require(not result["diagnostics"], "loop fixture has diagnostics")
        program = result["program"]
        assert program is not None
        formatter = Formatter()
        first = formatter.format(program)
        second = formatter.format(program)
        require(first == second, "reusing a Formatter instance changed output")
        reparsed = compile_source(write_temp_source(first))
        require(not reparsed["diagnostics"], "formatted loop did not recompile")
        return "formatter is reusable and output recompiles"

def loop_differential() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(fixture("loop.ax"), Path(directory))
            require(result["interpreter_exit_code"] == 55, "interpreter loop result is not 55")
            require(result["native_exit_code"] == 55, "native loop result is not 55")
            return {
                "interpreter": result["interpreter_exit_code"],
                "native": result["native_exit_code"],
            }

def nested_mutation() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(fixture("mutation_if.ax"), Path(directory))
            require(result["interpreter_exit_code"] == 9, "nested interpreter mutation did not persist")
            require(result["native_exit_code"] == 9, "nested native mutation did not persist")
            return {"interpreter": 9, "native": 9}

def infinite_loop_limit() -> str:
        result = compile_source(fixture("infinite_loop.ax"))
        require(not result["diagnostics"], "infinite loop fixture has compile diagnostics")
        program = result["program"]
        assert program is not None
        try:
            Interpreter(program, step_limit=25).run_main()
        except RuntimeError as error:
            require("AX-RUNTIME-0001" in str(error), f"wrong runtime failure: {error}")
            return str(error)
        raise AssertionError("infinite loop escaped the interpreter step limit")

def llvm_shape() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(fixture("loop.ax"), Path(directory))
            require(result["status"] == "passed", "loop proof failed before IR inspection")
            llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
            lines = llvm.splitlines()
            alloca_indexes = [index for index, line in enumerate(lines) if " = alloca " in line]
            first_branch = next(index for index, line in enumerate(lines) if line.strip().startswith("br "))
            require(alloca_indexes, "LLVM IR contains no allocas")
            require(all(index < first_branch for index in alloca_indexes), "alloca appeared after control flow began")
            for fragment in ["while_cond", "while_body", "while_after", "br i1", "store i32", "load i32"]:
                require(fragment in llvm, f"LLVM IR missing {fragment}")
            return {
                "allocas": len(alloca_indexes),
                "all_before_first_branch": True,
                "llvm_sha256": sha256(Path(directory) / "program.ll"),
            }

def cfg_shape() -> dict[str, Any]:
        result = compile_source(fixture("loop.ax"))
        require(not result["diagnostics"], "loop fixture has diagnostics")
        program = result["program"]
        assert program is not None
        document = build_control_flow_document(program)
        function = document["functions"][0]
        kinds = {edge["kind"] for edge in function["edges"]}
        for expected in ["true", "false", "loop_back", "return"]:
            require(expected in kinds, f"CFG missing {expected} edge")
        require(function["all_reachable_paths_terminate"], "CFG reports a reachable fallthrough")
        require(not function["unreachable_nodes"], f"unexpected unreachable CFG nodes: {function['unreachable_nodes']}")
        return {"edge_kinds": sorted(kinds), "nodes": len(function["nodes"])}

def determinism() -> dict[str, str]:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            prove(fixture("loop.ax"), first)
            prove(fixture("loop.ax"), second)
            names = [
                "tokens.json",
                "ast.json",
                "formatted.ax",
                "symbols.json",
                "types.json",
                "effects.json",
                "ownership.json",
                "hir.json",
                "control-flow.json",
                "interpreter.json",
                "program.ll",
                "differential.json",
            ]
            hashes: dict[str, str] = {}
            for name in names:
                first_hash = sha256(first / name)
                second_hash = sha256(second / name)
                require(first_hash == second_hash, f"non-deterministic output: {name}")
                hashes[name] = first_hash
            return hashes
def register() -> None:
    check("ast-surface", ast_surface)
    check("formatter-reuse", formatter_reuse)
    check("immutable-assignment-rejected", lambda: exact_diagnostic("invalid_assign_let.ax", "AX-MUT-0001"))
    check("assignment-type-rejected", lambda: exact_diagnostic("invalid_assign_type.ax", "AX-TYPE-0011"))
    check("while-condition-rejected", lambda: exact_diagnostic("invalid_while_condition.ax", "AX-TYPE-0012"))
    check("block-scope-enforced", lambda: exact_diagnostic("invalid_block_scope.ax", "AX-NAME-0001"))
    check("loop-interpreter-native-differential", loop_differential)
    check("nested-mutation-persists", nested_mutation)
    check("infinite-loop-step-limit", infinite_loop_limit)
    check("llvm-loop-shape", llvm_shape)
    check("control-flow-graph", cfg_shape)
    check("deterministic-outputs", determinism)
    check("i32-literal-range-enforced", lambda: exact_diagnostic("invalid_i32_literal.ax", "AX-INT-0001"))
