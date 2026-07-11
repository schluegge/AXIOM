from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from axiom_bench import RunnerError, run_conformance


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a trusted AXIOM-Bench conformance fixture")
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--language", choices=["axiom", "rust", "zig", "go"], required=True)
    parser.add_argument("--adapter", choices=["reference", "seeded_wrong"], required=True)
    parser.add_argument("--wrong-index", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        result = run_conformance(
            ROOT,
            args.task,
            language=args.language,
            adapter=args.adapter,
            wrong_index=args.wrong_index,
            output_directory=args.output,
        )
    except RunnerError as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "exit_code": 20,
                    "finding": error.finding.as_dict(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 20

    print(json.dumps(result.report, indent=2, sort_keys=True))
    return 0 if result.conformance_passed else 21


if __name__ == "__main__":
    raise SystemExit(main())
