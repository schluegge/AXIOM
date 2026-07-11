from __future__ import annotations

from dataclasses import dataclass, field, asdict
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class Position:
    byte: int
    line: int
    column: int


@dataclass(frozen=True)
class Span:
    source_path: str
    byte_start: int
    byte_end: int
    line_start: int
    column_start: int
    line_end: int
    column_end: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Token:
    kind: str
    lexeme: str
    span: Span

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "lexeme": self.lexeme, "span": self.span.to_dict()}


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    message: str
    span: Span
    stage: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "stage": self.stage,
            "primary_span": self.span.to_dict(),
        }


@dataclass
class Node:
    kind: str
    span: Span
    fields: dict[str, Any] = field(default_factory=dict)
    node_id: str = ""

    def finalize_id(self) -> None:
        seed = f"{self.kind}:{self.span.byte_start}:{self.span.byte_end}".encode("utf-8")
        self.node_id = "n_" + sha256(seed).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Node):
                return value.to_dict()
            if isinstance(value, list):
                return [convert(item) for item in value]
            if isinstance(value, dict):
                return {key: convert(item) for key, item in value.items()}
            return value

        if not self.node_id:
            self.finalize_id()
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "span": self.span.to_dict(),
            **{key: convert(value) for key, value in self.fields.items()},
        }


def merge_span(first: Span, last: Span) -> Span:
    return Span(
        source_path=first.source_path,
        byte_start=first.byte_start,
        byte_end=last.byte_end,
        line_start=first.line_start,
        column_start=first.column_start,
        line_end=last.line_end,
        column_end=last.column_end,
    )
