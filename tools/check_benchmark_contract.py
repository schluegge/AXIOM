from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from axiom_bench import check_benchmark_contract


def main() -> int:
    result = check_benchmark_contract(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
