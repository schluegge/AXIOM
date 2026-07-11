from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        return 90
    phase = sys.argv[1]
    candidate = Path(sys.argv[2])
    try:
        value = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return 91

    if phase == "format":
        return 0
    if phase == "check":
        return 0 if value in {"correct\n", "wrong\n"} else 2
    if phase == "public":
        return 0 if value in {"correct\n", "wrong\n"} else 3
    if phase == "acceptance":
        return 0 if value == "correct\n" else 4
    if phase == "security":
        return 0
    return 92


if __name__ == "__main__":
    raise SystemExit(main())
