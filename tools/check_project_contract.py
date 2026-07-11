from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from axiom_contract import check_project_contract, render_text
from axiom_contract.checker import canonical_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the AXIOM project contract")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    contract = args.contract.resolve() if args.contract else root / "contracts" / "project.json"
    schema = args.schema.resolve() if args.schema else root / "contracts" / "project.schema.json"
    result = check_project_contract(root, contract, schema)
    rendered = canonical_json(result) if args.format == "json" else render_text(result)

    if args.output is not None:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
