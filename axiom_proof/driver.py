from __future__ import annotations

import json
import subprocess
from hashlib import sha256
from pathlib import Path
from typing import Any

from .arithmetic import ArithmeticFault, panic_name_for_exit_code
from .control_flow import build_control_flow_document
from .formatter import Formatter
from .hir import lower_program
from .interpreter import Interpreter
from .runtime_faults import BoundsFault
from .lexer import Lexer
from .llvm_backend import LLVMBackend
from .parser import Parser
from .semantic import SemanticAnalyzer
from .source import SourceFile


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def structural_ast(node: dict[str, Any]) -> dict[str, Any]:
    ignored = {"node_id", "span"}
    result: dict[str, Any] = {}
    for key, value in node.items():
        if key in ignored:
            continue
        if isinstance(value, dict):
            result[key] = structural_ast(value)
        elif isinstance(value, list):
            result[key] = [structural_ast(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    return result


def compile_source(source_path: Path) -> dict[str, Any]:
    source = SourceFile.load(source_path)
    tokens, lexer_diagnostics = Lexer(source).run()
    token_document = {
        "document_kind": "axiom.tokens",
        "schema_version": "0.7.0",
        "source": {
            "path": source.path,
            "sha256": source.sha256,
            "encoding": "utf-8",
            "byte_length": len(source.data),
        },
        "tokens": [token.to_dict() for token in tokens],
        "diagnostics": [diagnostic.to_dict() for diagnostic in lexer_diagnostics],
    }
    parser = Parser(tokens)
    program = parser.parse() if not lexer_diagnostics else None
    diagnostics = [*lexer_diagnostics, *parser.diagnostics]
    ast_document = None
    semantic = None
    if program is not None:
        ast_document = {
            "document_kind": "axiom.ast",
            "schema_version": "0.7.0",
            "root": program.to_dict(),
        }
        semantic = SemanticAnalyzer(program)
        semantic.analyze()
        diagnostics.extend(semantic.diagnostics)
    return {
        "source": source,
        "tokens": token_document,
        "program": program,
        "ast": ast_document,
        "semantic": semantic,
        "diagnostics": diagnostics,
    }


def prove(source_path: Path, output_dir: Path, clang: str = "clang") -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    compilation = compile_source(source_path)
    diagnostics = compilation["diagnostics"]
    (output_dir / "tokens.json").write_text(canonical_json(compilation["tokens"]), encoding="utf-8")
    (output_dir / "diagnostics.json").write_text(
        canonical_json(
            {
                "document_kind": "axiom.diagnostics",
                "schema_version": "0.7.0",
                "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
            }
        ),
        encoding="utf-8",
    )
    if diagnostics:
        return {"status": "failed", "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics]}

    program = compilation["program"]
    semantic = compilation["semantic"]
    assert program is not None and semantic is not None and compilation["ast"] is not None
    (output_dir / "ast.json").write_text(canonical_json(compilation["ast"]), encoding="utf-8")
    formatted = Formatter().format(program)
    (output_dir / "formatted.ax").write_text(formatted, encoding="utf-8")
    reparsed = compile_source(output_dir / "formatted.ax")
    if reparsed["diagnostics"] or reparsed["ast"] is None:
        raise RuntimeError("formatted source did not recompile")
    format_proof = {
        "idempotent": Formatter().format(reparsed["program"]) == formatted,
        "structurally_equivalent": structural_ast(reparsed["ast"]["root"]) == structural_ast(compilation["ast"]["root"]),
    }
    (output_dir / "format-proof.json").write_text(canonical_json(format_proof), encoding="utf-8")
    if not all(format_proof.values()):
        raise RuntimeError("formatter proof failed")

    documents = {
        "symbols.json": semantic.symbol_document(),
        "types.json": semantic.type_document(),
        "effects.json": semantic.effect_document(),
        "ownership.json": semantic.ownership_document(),
        "layouts.json": {
            "document_kind": "axiom.layouts",
            "schema_version": "0.7.0",
            "target": "x86_64-unknown-linux-gnu",
            "layouts": [semantic.layout_document(name)["layout"] for name in sorted(semantic.registry.structs)],
        },
        "hir.json": lower_program(program, semantic.node_types),
        "control-flow.json": build_control_flow_document(program),
    }
    for name, document in documents.items():
        (output_dir / name).write_text(canonical_json(document), encoding="utf-8")

    interpreter = Interpreter(program)
    try:
        interpreter_result = interpreter.run_main()
        interpreter_outcome = {
            "kind": "returned",
            "exit_code": interpreter_result,
            "panic_name": None,
            "diagnostic_code": None,
        }
    except (ArithmeticFault, BoundsFault) as fault:
        interpreter_result = fault.exit_code
        interpreter_outcome = {
            "kind": ("arithmetic_fault" if isinstance(fault, ArithmeticFault) else "bounds_fault"),
            "exit_code": fault.exit_code,
            "panic_name": fault.panic_name,
            "diagnostic_code": fault.diagnostic_code,
            "message": fault.message,
        }
    interpreter_document = {
        "document_kind": "axiom.interpreter-result",
        "schema_version": "0.7.0",
        "outcome": interpreter_outcome,
        "exit_code": interpreter_result,
        "steps": interpreter.steps,
        "function_calls": interpreter.call_count,
    }
    (output_dir / "interpreter.json").write_text(canonical_json(interpreter_document), encoding="utf-8")

    llvm_ir = LLVMBackend(program, node_types=semantic.node_types).emit()
    llvm_path = output_dir / "program.ll"
    binary_path = output_dir / "program.native"
    llvm_path.write_text(llvm_ir, encoding="utf-8")
    runtime_absolute = Path(__file__).resolve().parents[1] / "runtime" / "axiom_runtime.c"
    try:
        runtime_path = runtime_absolute.relative_to(Path.cwd().resolve())
    except ValueError:
        runtime_path = runtime_absolute
    compile_command = [
        clang,
        "-Wno-override-module",
        "-x",
        "ir",
        str(llvm_path),
        "-x",
        "c",
        str(runtime_path),
        "-o",
        str(binary_path),
    ]
    compile_process = subprocess.run(
        compile_command,
        text=True,
        capture_output=True,
        check=False,
    )
    native_document: dict[str, Any] = {
        "compile_command": compile_command,
        "compile_exit_code": compile_process.returncode,
        "compile_stdout": compile_process.stdout,
        "compile_stderr": compile_process.stderr,
    }
    if compile_process.returncode != 0:
        (output_dir / "native.json").write_text(canonical_json(native_document), encoding="utf-8")
        raise RuntimeError("Clang failed to compile LLVM IR")
    run_process = subprocess.run([str(binary_path)], text=True, capture_output=True, check=False)
    native_document.update(
        run_exit_code=run_process.returncode,
        run_stdout=run_process.stdout,
        run_stderr=run_process.stderr,
        binary_sha256=sha256(binary_path.read_bytes()).hexdigest(),
        llvm_sha256=sha256(llvm_path.read_bytes()).hexdigest(),
    )
    (output_dir / "native.json").write_text(canonical_json(native_document), encoding="utf-8")
    native_panic_name = panic_name_for_exit_code(run_process.returncode)
    differential = {
        "interpreter_exit_code": interpreter_result,
        "native_exit_code": run_process.returncode,
        "interpreter_outcome_kind": interpreter_outcome["kind"],
        "interpreter_panic_name": interpreter_outcome.get("panic_name"),
        "native_panic_name": native_panic_name,
        "match": (
            interpreter_result == run_process.returncode
            and (
                interpreter_outcome["kind"] == "returned"
                or interpreter_outcome.get("panic_name") == native_panic_name
            )
        ),
    }
    (output_dir / "differential.json").write_text(canonical_json(differential), encoding="utf-8")
    if not differential["match"]:
        raise RuntimeError("interpreter/native differential mismatch")

    return {
        "status": "passed",
        "interpreter_exit_code": interpreter_result,
        "native_exit_code": run_process.returncode,
        "interpreter_outcome": interpreter_outcome,
        "native_panic_name": native_panic_name,
        "outputs": sorted(path.name for path in output_dir.iterdir() if path.is_file()),
    }
