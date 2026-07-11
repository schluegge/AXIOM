from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .type_system import TypeRegistry, parse_array_type


@dataclass(frozen=True)
class TypeLayout:
    type_name: str
    size: int
    alignment: int
    kind: str
    fields: tuple[dict[str, Any], ...] = ()
    element_type: str | None = None
    element_stride: int | None = None
    length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": self.type_name,
            "kind": self.kind,
            "size": self.size,
            "alignment": self.alignment,
        }
        if self.fields:
            result["fields"] = list(self.fields)
        if self.element_type is not None:
            result.update(
                element_type=self.element_type,
                element_stride=self.element_stride,
                length=self.length,
            )
        return result


def align_up(value: int, alignment: int) -> int:
    if alignment <= 0:
        raise ValueError("alignment must be positive")
    return (value + alignment - 1) // alignment * alignment


class LayoutEngine:
    def __init__(self, registry: TypeRegistry, target: str = "x86_64-unknown-linux-gnu"):
        self.registry = registry
        self.target = target
        self.cache: dict[str, TypeLayout] = {}
        self.active: list[str] = []

    def layout(self, type_name: str) -> TypeLayout:
        cached = self.cache.get(type_name)
        if cached is not None:
            return cached
        if type_name in self.active:
            cycle = " -> ".join([*self.active, type_name])
            raise ValueError(f"recursive value layout: {cycle}")
        self.active.append(type_name)
        try:
            if type_name == "i32":
                result = TypeLayout(type_name, 4, 4, "primitive")
            elif type_name == "bool":
                result = TypeLayout(type_name, 1, 1, "primitive")
            elif (array := parse_array_type(type_name)) is not None:
                element_type, length = array
                if length <= 0:
                    raise ValueError("fixed array length must be positive")
                element = self.layout(element_type)
                stride = align_up(element.size, element.alignment)
                result = TypeLayout(
                    type_name,
                    stride * length,
                    element.alignment,
                    "array",
                    element_type=element_type,
                    element_stride=stride,
                    length=length,
                )
            else:
                definition = self.registry.struct(type_name)
                if definition is None:
                    raise ValueError(f"unknown type for layout: {type_name}")
                offset = 0
                alignment = 1
                fields: list[dict[str, Any]] = []
                for field in definition.fields:
                    field_layout = self.layout(field.type_name)
                    offset = align_up(offset, field_layout.alignment)
                    fields.append(
                        {
                            "name": field.name,
                            "type": field.type_name,
                            "offset": offset,
                            "size": field_layout.size,
                            "alignment": field_layout.alignment,
                        }
                    )
                    offset += field_layout.size
                    alignment = max(alignment, field_layout.alignment)
                result = TypeLayout(
                    type_name,
                    align_up(offset, alignment),
                    alignment,
                    "struct",
                    fields=tuple(fields),
                )
            self.cache[type_name] = result
            return result
        finally:
            self.active.pop()

    def document(self, type_name: str) -> dict[str, Any]:
        return {
            "document_kind": "axiom.layout",
            "schema_version": "0.7.0",
            "target": self.target,
            "representation": "axiom_natural_c_compatible_subset_v0",
            "layout": self.layout(type_name).to_dict(),
        }
