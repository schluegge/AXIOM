from __future__ import annotations

from dataclasses import dataclass

from .arithmetic import PANIC_INDEX_OUT_OF_BOUNDS, PANIC_NAMES


@dataclass(frozen=True)
class BoundsFault(Exception):
    diagnostic_code: str
    panic_name: str
    exit_code: int
    message: str

    def __str__(self) -> str:
        return f"{self.diagnostic_code}: {self.message}"


def array_index_out_of_bounds(index: int, length: int) -> BoundsFault:
    return BoundsFault(
        diagnostic_code="AX-RUNTIME-INDEX-0001",
        panic_name=PANIC_NAMES[PANIC_INDEX_OUT_OF_BOUNDS],
        exit_code=PANIC_INDEX_OUT_OF_BOUNDS,
        message=f"array index {index} is outside 0..{length - 1}",
    )
