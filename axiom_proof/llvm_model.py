from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FunctionContext:
    lines: list[str]
    registers: int = 0
    labels: int = 0

    def register(self) -> str:
        self.registers += 1
        return f"%v{self.registers}"

    def label(self, prefix: str) -> str:
        self.labels += 1
        return f"{prefix}{self.labels}"


@dataclass(frozen=True)
class Storage:
    slot: str
    type_name: str
    mutable: bool


