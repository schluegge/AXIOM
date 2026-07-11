from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FunctionSignature:
    name: str
    parameter_types: tuple[str, ...]
    return_type: str
    node_id: str


@dataclass(frozen=True)
class LocalBinding:
    name: str
    type_name: str
    mutable: bool
    node_id: str
    kind: str


