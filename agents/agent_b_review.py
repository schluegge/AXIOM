from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents import agent_b_support as support
from agents.agent_b_aggregate_semantic_checks import register as register_aggregate_semantics
from agents.agent_b_aggregate_layout_checks import register as register_aggregate_layout
from agents.agent_b_aggregate_generated_checks import register as register_aggregate_generated
from agents.agent_b_arithmetic_checks import register as register_arithmetic
from agents.agent_b_core_checks import register as register_core
from agents.agent_b_lvalue_checks import register as register_lvalues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
    support.configure(root, output)
    try:
        register_aggregate_semantics()
        register_aggregate_layout()
        register_aggregate_generated()
        register_lvalues()
        register_core()
        register_arithmetic()
    finally:
        support.cleanup()

    failed = [item for item in support.CHECKS if item["status"] != "passed"]
    report = {
        "document_kind": "axiom.agent-b-adversarial-review",
        "schema_version": "0.6.0",
        "status": "failed" if failed else "passed",
        "role": "separate deterministic review process; not a second language-model instance",
        "checks": support.CHECKS,
        "passed": len(support.CHECKS) - len(failed),
        "failed": len(failed),
    }
    (output / "agent-b-review.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown = [
        "# Agent B Adversarial Review", "", f"Status: **{report['status'].upper()}**", "",
        "This is a separate deterministic review process, not a second language-model instance.", "",
    ]
    for item in support.CHECKS:
        markdown.append(f"- `{item['status'].upper()}` — {item['name']}: {item['detail']}")
    (output / "agent-b-review.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
