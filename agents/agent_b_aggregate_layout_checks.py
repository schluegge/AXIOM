from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from axiom_proof.arithmetic import PANIC_INDEX_OUT_OF_BOUNDS
from axiom_proof.driver import compile_source, prove
from axiom_proof.llvm_backend import LLVMBackend
from .agent_b_support import ROOT, check, exact_diagnostic, fixture, require, sha256

def layout_contract() -> dict[str, Any]:
        result = compile_source(fixture("layout.ax"))
        require(not result["diagnostics"], "layout fixture has diagnostics")
        semantic = result["semantic"]
        assert semantic is not None
        first = semantic.layout_document("Mixed")
        second = semantic.layout_document("Mixed")
        require(first == second, "layout document is non-deterministic")
        layout = first["layout"]
        require(layout["size"] == 28, f"Mixed size mismatch: {layout['size']}")
        require(layout["alignment"] == 4, f"Mixed alignment mismatch: {layout['alignment']}")
        offsets = {field["name"]: field["offset"] for field in layout["fields"]}
        require(offsets == {"flag": 0, "count": 4, "pair": 8, "values": 16}, f"offset mismatch: {offsets}")
        return {"size": 28, "alignment": 4, "offsets": offsets}

def llvm_c_layout_probe() -> dict[str, Any]:
        llvm = """target triple = \"x86_64-unknown-linux-gnu\"
%struct.Pair = type { i32, i32 }
%struct.Mixed = type { i1, i32, %struct.Pair, [3 x i32] }

define i64 @axiom_sizeof_mixed() {
entry:
  %end = getelementptr %struct.Mixed, ptr null, i32 1
  %value = ptrtoint ptr %end to i64
  ret i64 %value
}
define i64 @axiom_offset_flag() {
entry:
  %field = getelementptr %struct.Mixed, ptr null, i32 0, i32 0
  %value = ptrtoint ptr %field to i64
  ret i64 %value
}
define i64 @axiom_offset_count() {
entry:
  %field = getelementptr %struct.Mixed, ptr null, i32 0, i32 1
  %value = ptrtoint ptr %field to i64
  ret i64 %value
}
define i64 @axiom_offset_pair() {
entry:
  %field = getelementptr %struct.Mixed, ptr null, i32 0, i32 2
  %value = ptrtoint ptr %field to i64
  ret i64 %value
}
define i64 @axiom_offset_values() {
entry:
  %field = getelementptr %struct.Mixed, ptr null, i32 0, i32 3
  %value = ptrtoint ptr %field to i64
  ret i64 %value
}
"""
        c_source = r"""#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
struct Pair { int32_t left; int32_t right; };
struct Mixed { bool flag; int32_t count; struct Pair pair; int32_t values[3]; };
extern uint64_t axiom_sizeof_mixed(void);
extern uint64_t axiom_offset_flag(void);
extern uint64_t axiom_offset_count(void);
extern uint64_t axiom_offset_pair(void);
extern uint64_t axiom_offset_values(void);
int main(void) {
  printf("%llu %llu %llu %llu %llu\n",
    (unsigned long long)axiom_sizeof_mixed(),
    (unsigned long long)axiom_offset_flag(),
    (unsigned long long)axiom_offset_count(),
    (unsigned long long)axiom_offset_pair(),
    (unsigned long long)axiom_offset_values());
  fprintf(stderr, "%zu %zu %zu %zu %zu\n",
    sizeof(struct Mixed), offsetof(struct Mixed, flag),
    offsetof(struct Mixed, count), offsetof(struct Mixed, pair),
    offsetof(struct Mixed, values));
  return 0;
}
"""
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ir = work / "layout.ll"
            c_file = work / "layout.c"
            binary = work / "layout"
            ir.write_text(llvm, encoding="utf-8")
            c_file.write_text(c_source, encoding="utf-8")
            compiled = subprocess.run(
                ["clang", "-Wno-override-module", "-x", "ir", str(ir), "-x", "c", str(c_file), "-o", str(binary)],
                text=True,
                capture_output=True,
                check=False,
            )
            require(compiled.returncode == 0, f"layout probe compilation failed: {compiled.stderr}")
            executed = subprocess.run([str(binary)], text=True, capture_output=True, check=False)
            require(executed.returncode == 0, f"layout probe execution failed: {executed.stderr}")
            llvm_values = [int(value) for value in executed.stdout.split()]
            c_values = [int(value) for value in executed.stderr.split()]
        require(llvm_values == c_values, f"LLVM/C layout mismatch: {llvm_values} != {c_values}")
        require(llvm_values == [28, 0, 4, 8, 16], f"unexpected layout values: {llvm_values}")
        return {"llvm": llvm_values, "c": c_values}

def aggregate_c_abi_round_trip() -> dict[str, Any]:
        result = compile_source(fixture("c_abi_aggregate.ax"))
        require(not result["diagnostics"], "aggregate C ABI fixture has diagnostics")
        program = result["program"]
        semantic = result["semantic"]
        assert program is not None and semantic is not None
        c_source = r"""#include <stdint.h>
struct Pair { int32_t left; int32_t right; };
extern struct Pair make_pair(int32_t left, int32_t right);
extern int32_t sum_pair(struct Pair pair);
int main(void) {
  struct Pair pair = make_pair(20, 22);
  return sum_pair(pair);
}
"""
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ir = work / "aggregate.ll"
            obj = work / "aggregate.o"
            c_file = work / "harness.c"
            binary = work / "harness"
            ir.write_text(LLVMBackend(program, node_types=semantic.node_types).emit(), encoding="utf-8")
            c_file.write_text(c_source, encoding="utf-8")
            compiled = subprocess.run(
                ["clang", "-Wno-override-module", "-x", "ir", "-c", str(ir), "-o", str(obj)],
                text=True,
                capture_output=True,
                check=False,
            )
            require(compiled.returncode == 0, f"aggregate IR compilation failed: {compiled.stderr}")
            linked = subprocess.run(
                ["clang", str(c_file), str(obj), str(ROOT / "runtime" / "axiom_runtime.c"), "-o", str(binary)],
                text=True,
                capture_output=True,
                check=False,
            )
            require(linked.returncode == 0, f"aggregate C ABI link failed: {linked.stderr}")
            executed = subprocess.run([str(binary)], text=True, capture_output=True, check=False)
            require(executed.returncode == 42, f"aggregate C ABI result mismatch: {executed.returncode}")
        return {"exit_code": 42, "direction": "C -> Axiom return struct -> C -> Axiom consume struct"}

def aggregate_llvm_shape() -> dict[str, Any]:
        with tempfile.TemporaryDirectory() as directory:
            result = prove(fixture("aggregates.ax"), Path(directory))
            require(result["status"] == "passed", "aggregate proof failed")
            llvm = (Path(directory) / "program.ll").read_text(encoding="utf-8")
            required = [
                "%struct.Pair = type { i32, i32 }",
                "%struct.Packet = type { i1, %struct.Pair, [3 x i32] }",
                "insertvalue",
                "extractvalue",
                "getelementptr [3 x i32]",
                "call void @axiom_panic_i32(i32 108)",
            ]
            for fragment in required:
                require(fragment in llvm, f"aggregate LLVM missing {fragment}")
            lines = llvm.splitlines()
            function_checks: list[dict[str, Any]] = []
            index = 0
            while index < len(lines):
                stripped = lines[index].strip()
                if not stripped.startswith("define "):
                    index += 1
                    continue
                header = stripped
                body_start = index
                index += 1
                while index < len(lines) and lines[index].strip() != "}":
                    index += 1
                body_end = min(index, len(lines) - 1)
                body = lines[body_start:body_end + 1]
                alloca_indexes = [i for i, line in enumerate(body) if " = alloca " in line]
                branch_indexes = [i for i, line in enumerate(body) if line.strip().startswith("br ")]
                if alloca_indexes and branch_indexes:
                    require(
                        all(i < branch_indexes[0] for i in alloca_indexes),
                        f"aggregate temp alloca appears after control flow began in {header}",
                    )
                function_checks.append({
                    "function": header,
                    "allocas": len(alloca_indexes),
                    "branches": len(branch_indexes),
                    "allocas_before_first_branch": True,
                })
                index += 1
            require(function_checks, "aggregate LLVM contains no function definitions")
            return {"fragments": required, "functions": function_checks}

def register() -> None:
    check("layout-contract", layout_contract)
    check("llvm-c-layout-probe", llvm_c_layout_probe)
    check("aggregate-c-abi-round-trip", aggregate_c_abi_round_trip)
    check("aggregate-llvm-shape", aggregate_llvm_shape)
