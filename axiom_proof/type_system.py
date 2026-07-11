from __future__ import annotations

from dataclasses import dataclass

from .model import Node

PRIMITIVE_TYPES = {"i32", "bool"}


@dataclass(frozen=True)
class StructField:
    name: str
    type_name: str
    node_id: str


@dataclass(frozen=True)
class StructDefinition:
    name: str
    fields: tuple[StructField, ...]
    node_id: str

    def field_index(self, name: str) -> int | None:
        for index, field in enumerate(self.fields):
            if field.name == name:
                return index
        return None

    def field(self, name: str) -> StructField | None:
        index = self.field_index(name)
        return None if index is None else self.fields[index]


def array_type(element_type: str, length: int) -> str:
    return f"[{element_type}; {length}]"


def parse_array_type(type_name: str) -> tuple[str, int] | None:
    text = type_name.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return None
    inner = text[1:-1]
    depth = 0
    split_index: int | None = None
    for index, char in enumerate(inner):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        elif char == ";" and depth == 0:
            split_index = index
            break
    if split_index is None:
        return None
    element = inner[:split_index].strip()
    length_text = inner[split_index + 1 :].strip()
    if not element or not length_text.isdecimal():
        return None
    return element, int(length_text)


class TypeRegistry:
    def __init__(self) -> None:
        self.structs: dict[str, StructDefinition] = {}

    @classmethod
    def from_program(cls, program: Node) -> "TypeRegistry":
        registry = cls()
        for declaration in program.fields.get("structs", []):
            name = declaration.fields["name"]
            fields = tuple(
                StructField(
                    name=field.fields["name"],
                    type_name=field.fields["type_name"],
                    node_id=field.node_id,
                )
                for field in declaration.fields["fields"]
            )
            if name in registry.structs:
                raise ValueError(f"duplicate struct in valid program: {name}")
            registry.structs[name] = StructDefinition(name, fields, declaration.node_id)
        return registry

    def is_known(self, type_name: str) -> bool:
        if type_name in PRIMITIVE_TYPES or type_name in self.structs:
            return True
        array = parse_array_type(type_name)
        return array is not None and array[1] > 0 and self.is_known(array[0])

    def struct(self, type_name: str) -> StructDefinition | None:
        return self.structs.get(type_name)

    def array(self, type_name: str) -> tuple[str, int] | None:
        return parse_array_type(type_name)

    def validate_acyclic(self) -> list[list[str]]:
        cycles: list[list[str]] = []
        visiting: list[str] = []
        visited: set[str] = set()

        def contained_structs(type_name: str) -> list[str]:
            array = parse_array_type(type_name)
            if array is not None:
                return contained_structs(array[0])
            return [type_name] if type_name in self.structs else []

        def visit(name: str) -> None:
            if name in visited:
                return
            if name in visiting:
                start = visiting.index(name)
                cycles.append([*visiting[start:], name])
                return
            visiting.append(name)
            for field in self.structs[name].fields:
                for dependency in contained_structs(field.type_name):
                    visit(dependency)
            visiting.pop()
            visited.add(name)

        for name in sorted(self.structs):
            visit(name)
        return cycles
