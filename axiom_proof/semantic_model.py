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


@dataclass(frozen=True)
class LValueInfo:
    root_binding: LocalBinding | None
    type_name: str
    writable: bool
    via_reference: bool = False


@dataclass(frozen=True)
class BorrowRecord:
    root_node_id: str
    root_name: str
    mutable: bool
    holder_node_id: str
    borrow_node_id: str
    temporary: bool
