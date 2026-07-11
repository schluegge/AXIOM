from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from axiom_proof.arithmetic import (
    PANIC_ADD_OVERFLOW, PANIC_DIVIDE_BY_ZERO, PANIC_DIVIDE_OVERFLOW,
    PANIC_MUL_OVERFLOW, PANIC_REMAINDER_BY_ZERO, PANIC_REMAINDER_OVERFLOW,
    PANIC_SUB_OVERFLOW,
)
from axiom_proof.driver import compile_source, prove
from .agent_b_support import check, fixture, require

def arithmetic_fault_differential(fixture: str, expected: int) -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(Path("examples") / fixture, Path(directory))
            require(result["status"] == "passed", f"{fixture}: proof did not pass")
            require(result["interpreter_exit_code"] == expected, f"{fixture}: interpreter code mismatch")
            require(result["native_exit_code"] == expected, f"{fixture}: native code mismatch")
            require(result["interpreter_outcome"]["kind"] == "arithmetic_fault", f"{fixture}: missing fault outcome")
            require(result["native_panic_name"] == result["interpreter_outcome"]["panic_name"], f"{fixture}: panic identity mismatch")
            return {
                "fixture": fixture,
                "exit_code": expected,
                "panic_name": result["native_panic_name"],
            }

def signed_division_semantics() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(fixture("arithmetic_normal.ax"), Path(directory))
            require(result["interpreter_exit_code"] == 17, "interpreter signed div/rem result mismatch")
            require(result["native_exit_code"] == 17, "native signed div/rem result mismatch")
            return {"combined_result": 17, "division": -2, "remainder": -1}

def checked_llvm_shape() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            prove(fixture("arithmetic_normal.ax"), Path(directory))
            llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
            for intrinsic in [
                "llvm.sadd.with.overflow.i32",
                "llvm.ssub.with.overflow.i32",
                "llvm.smul.with.overflow.i32",
            ]:
                require(intrinsic in llvm, f"missing checked intrinsic {intrinsic}")
            require("call void @axiom_panic_i32" in llvm, "missing arithmetic panic boundary")
            require("sdiv i32" in llvm and "srem i32" in llvm, "missing signed div/rem")
            require(llvm.index("icmp eq i32") < llvm.index("sdiv i32"), "sdiv appears before zero guard")
            return {
                "checed_intrinsics": 3,
                "panic_boundary": True,
                "division_guards_precede_operations": True,
            }

def panic_effect_is_visible() -> dict[str, Any]:
        result = compile_source(fixture("arithmetic_normal.ax"))
        require(not result["diagnostics"], "arithmetic fixture has diagnostics")
        semantic = result["semantic"]
        assert semantic is not None
        function = next(item for item in semantic.effect_document()["functions"] if item["name"] == "main")
        require(function["effects"] == ["panic"], f"unexpected effects: {function['effects']}")
        require(function["local_facts"]["checked_arithmetic_sites"] >= 5, "arithmetic sites not counted")
        return function
def register() -> None:
    check("signed-division-remainder-semantics", signed_division_semantics)
    check("checked-llvm-arithmetic-shape", checked_llvm_shape)
    check("panic-effect-visible", panic_effect_is_visible)
    check("add-overflow-differential", lambda: arithmetic_fault_differential("overflow_add.ax", PANIC_ADD_OVERFLOW))
    check("sub-overflow-differential", lambda: arithmetic_fault_differential("overflow_sub.ax", PANIC_SUB_OVERFLOW))
    check("mul-overflow-differential", lambda: arithmetic_fault_differential("overflow_mul.ax", PANIC_MUL_OVERFLOW))
    check("divide-zero-differential", lambda: arithmetic_fault_differential("divide_zero.ax", PANIC_DIVIDE_BY_ZERO))
    check("divide-overflow-differential", lambda: arithmetic_fault_differential("divide_overflow.ax", PANIC_DIVIDE_OVERFLOW))
    check("remainder-zero-differential", lambda: arithmetic_fault_differential("remainder_zero.ax", PANIC_REMAINDER_BY_ZERO))
    check("remainder-overflow-differential", lambda: arithmetic_fault_differential("remainder_overflow.ax", PANIC_REMAINDER_OVERFLOW))
