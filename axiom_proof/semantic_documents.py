from __future__ import annotations

from typing import Any

from .model import Node
from .semantic_model import LocalBinding
from .type_system import parse_array_type
from .layout import LayoutEngine


class SemanticDocumentMixin:
    def symbol_document(self) -> dict[str, Any]:
        return {
            "document_kind": "axiom.symbols",
            "schema_version": "0.7.0",
            "structs": [
                {
                    "name": definition.name,
                    "node_id": definition.node_id,
                    "fields": [
                        {"name": field.name, "type": field.type_name, "node_id": field.node_id}
                        for field in definition.fields
                    ],
                }
                for definition in sorted(self.registry.structs.values(), key=lambda item: item.name)
            ],
            "functions": [
                {
                    "name": signature.name,
                    "node_id": signature.node_id,
                    "parameter_types": list(signature.parameter_types),
                    "return_type": signature.return_type,
                }
                for signature in sorted(self.functions.values(), key=lambda item: item.name)
            ],
            "references": sorted(self.references, key=lambda item: (item["node_id"], item["name"], item["kind"])),
            "call_graph": {name: sorted(set(calls)) for name, calls in sorted(self.call_graph.items())},
        }

    def type_document(self) -> dict[str, Any]:
        return {
            "document_kind": "axiom.types",
            "schema_version": "0.7.0",
            "node_types": dict(sorted(self.node_types.items())),
        }

    def effect_document(self) -> dict[str, Any]:
        return {
            "document_kind": "axiom.effects",
            "schema_version": "0.7.0",
            "functions": [
                {
                    "name": name,
                    "effects": (["panic"] if self.function_facts[name]["panic_sites"] else []),
                    "local_facts": self.function_facts[name],
                    "proof": (
                        "checked_operations_may_panic"
                        if self.function_facts[name]["panic_sites"]
                        else "no_external_effects_in_reference_subset"
                    ),
                }
                for name in sorted(self.functions)
            ],
        }

    def ownership_document(self) -> dict[str, Any]:
        mutable_bindings = sum(facts["mutable_bindings"] for facts in self.function_facts.values())
        assignments = sum(facts["assignments"] for facts in self.function_facts.values())
        field_writes = sum(facts["field_writes"] for facts in self.function_facts.values())
        index_writes = sum(facts["index_writes"] for facts in self.function_facts.values())
        return {
            "document_kind": "axiom.ownership",
            "schema_version": "0.7.0",
            "mode": "copy_values_with_scoped_non_escaping_references",
            "borrows": sorted(
                self.borrow_events,
                key=lambda item: (item["borrow_node_id"], item["root_name"], item["mutable"]),
            ),
            "moves": [],
            "mutable_bindings": mutable_bindings,
            "assignments": assignments,
            "field_writes": field_writes,
            "index_writes": index_writes,
            "structured_lvalues": True,
            "reference_policy": {
                "non_null": True,
                "lexical_scope": True,
                "root_granularity": "whole local root",
                "reference_returns": False,
                "reference_aggregate_storage": False,
                "reborrowing": False,
            },
            "aggregate_semantics": "deep value copies with direct borrowed subobject access",
            "proof": "scoped references cannot escape the implemented local/call subset",
        }

    def layout_document(self, type_name: str, target: str = "x86_64-unknown-linux-gnu") -> dict[str, Any]:
        return LayoutEngine(self.registry, target).document(type_name)
