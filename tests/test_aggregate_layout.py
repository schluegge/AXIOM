from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from axiom_proof.arithmetic import PANIC_INDEX_OUT_OF_BOUNDS
from axiom_proof.cli import main as cli_main
from axiom_proof.driver import compile_source, prove
from axiom_proof.llvm_backend import LLVMBackend

ROOT = Path(__file__).resolve().parents[1]

class AggregateLayoutTests(unittest.TestCase):
    def test_struct_by_value_c_abi_round_trip(self) -> None:
            result = compile_source(ROOT / "examples" / "c_abi_aggregate.ax")
            self.assertEqual(result["diagnostics"], [])
            program = result["program"]
            semantic = result["semantic"]
            assert program is not None and semantic is not None
            from axiom_proof.llvm_backend import LLVMBackend
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
                root = Path(directory)
                ir = root / "aggregate.ll"
                obj = root / "aggregate.o"
                c_file = root / "harness.c"
                binary = root / "harness"
                ir.write_text(LLVMBackend(program, node_types=semantic.node_types).emit(), encoding="utf-8")
                c_file.write_text(c_source, encoding="utf-8")
                compile_ir = subprocess.run(
                    ["clang", "-Wno-override-module", "-x", "ir", "-c", str(ir), "-o", str(obj)],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(compile_ir.returncode, 0, compile_ir.stderr)
                link = subprocess.run(
                    ["clang", str(c_file), str(obj), str(ROOT / "runtime" / "axiom_runtime.c"), "-o", str(binary)],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(link.returncode, 0, link.stderr)
                executed = subprocess.run([str(binary)], text=True, capture_output=True)
                self.assertEqual(executed.returncode, 42, executed.stderr)

    def test_layout_document_matches_x86_64_c_layout(self) -> None:
            result = compile_source(ROOT / "examples" / "layout.ax")
            self.assertEqual(result["diagnostics"], [])
            semantic = result["semantic"]
            assert semantic is not None
            document = semantic.layout_document("Mixed")
            layout = document["layout"]
            self.assertEqual(layout["size"], 28)
            self.assertEqual(layout["alignment"], 4)
            self.assertEqual(
                {field["name"]: field["offset"] for field in layout["fields"]},
                {"flag": 0, "count": 4, "pair": 8, "values": 16},
            )
            c_source = r"""#include <stdint.h>
    #include <stdbool.h>
    #include <stddef.h>
    #include <stdio.h>
    struct Pair { int32_t left; int32_t right; };
    struct Mixed { bool flag; int32_t count; struct Pair pair; int32_t values[3]; };
    int main(void) {
        printf("%zu %zu %zu %zu %zu %zu\n",
            sizeof(struct Mixed), _Alignof(struct Mixed),
            offsetof(struct Mixed, flag), offsetof(struct Mixed, count),
            offsetof(struct Mixed, pair), offsetof(struct Mixed, values));
        return 0;
    }
    """
            with tempfile.TemporaryDirectory() as directory:
                directory_path = Path(directory)
                source = directory_path / "layout.c"
                binary = directory_path / "layout"
                source.write_text(c_source, encoding="utf-8")
                compiled = subprocess.run(["clang", str(source), "-o", str(binary)], text=True, capture_output=True)
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                executed = subprocess.run([str(binary)], text=True, capture_output=True)
                self.assertEqual(executed.returncode, 0, executed.stderr)
                values = [int(value) for value in executed.stdout.split()]
            self.assertEqual(values, [28, 4, 0, 4, 8, 16])

    def test_llvm_named_struct_layout_matches_c_layout(self) -> None:
            llvm = """target triple = "x86_64-unknown-linux-gnu"
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
                root = Path(directory)
                ir = root / "layout.ll"
                c_file = root / "layout.c"
                binary = root / "layout"
                ir.write_text(llvm, encoding="utf-8")
                c_file.write_text(c_source, encoding="utf-8")
                compiled = subprocess.run(
                    ["clang", "-Wno-override-module", "-x", "ir", str(ir), "-x", "c", str(c_file), "-o", str(binary)],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(compiled.returncode, 0, compiled.stderr)
                executed = subprocess.run([str(binary)], text=True, capture_output=True)
                self.assertEqual(executed.returncode, 0, executed.stderr)
            llvm_values = [int(value) for value in executed.stdout.split()]
            c_values = [int(value) for value in executed.stderr.split()]
            self.assertEqual(llvm_values, c_values)
            self.assertEqual(llvm_values, [28, 0, 4, 8, 16])

    def test_layout_cli_is_structured_and_deterministic(self) -> None:
            command = [
                sys.executable,
                "-m",
                "axiom_proof.cli",
                "explain",
                "layout",
                str(ROOT / "examples" / "layout.ax"),
                "Mixed",
            ]
            first = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            second = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, second.stdout)
            document = json.loads(first.stdout)
            self.assertEqual(document["document_kind"], "axiom.layout")
            self.assertEqual(document["layout"]["size"], 28)
