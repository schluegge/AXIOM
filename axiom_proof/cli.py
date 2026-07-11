from __future__ import annotations

import argparse
import json
from pathlib import Path

from .driver import compile_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="axiom")
    subcommands = parser.add_subparsers(dest="command", required=True)
    explain = subcommands.add_parser("explain")
    explain_subcommands = explain.add_subparsers(dest="explain_command", required=True)
    layout = explain_subcommands.add_parser("layout")
    layout.add_argument("source", type=Path)
    layout.add_argument("type_name")
    layout.add_argument("--target", default="x86_64-unknown-linux-gnu")
    args = parser.parse_args(argv)

    if args.command == "explain" and args.explain_command == "layout":
        compilation = compile_source(args.source)
        if compilation["diagnostics"]:
            print(
                json.dumps(
                    {
                        "document_kind": "axiom.diagnostics",
                        "schema_version": "0.5.0",
                        "diagnostics": [item.to_dict() for item in compilation["diagnostics"]],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1
        semantic = compilation["semantic"]
        assert semantic is not None
        if not semantic.registry.is_known(args.type_name):
            print(
                json.dumps(
                    {
                        "document_kind": "axiom.cli-error",
                        "schema_version": "0.5.0",
                        "code": "AX-LAYOUT-0001",
                        "message": f"unknown type: {args.type_name}",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2
        print(json.dumps(semantic.layout_document(args.type_name, args.target), indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
