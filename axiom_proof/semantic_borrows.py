from __future__ import annotations

from .model import Node
from .semantic_model import BorrowRecord, LocalBinding
from .type_system import parse_reference_type, reference_type


class SemanticBorrowMixin:
    def active_borrows(self, binding: LocalBinding) -> list[BorrowRecord]:
        return [
            record
            for scope in self.borrow_scopes
            for record in scope
            if record.root_node_id == binding.node_id
        ]

    def check_root_read(self, binding: LocalBinding, node: Node) -> None:
        mutable = [record for record in self.active_borrows(binding) if record.mutable]
        if mutable:
            self.error(
                "AX-BORROW-0004",
                f"cannot read {binding.name} while it is mutably borrowed",
                node,
                "borrow_checker",
            )

    def check_root_write(self, binding: LocalBinding, node: Node) -> None:
        active = self.active_borrows(binding)
        if not active:
            return
        if any(record.mutable for record in active):
            message = f"cannot write {binding.name} while it is mutably borrowed"
        else:
            message = f"cannot write {binding.name} while shared borrows are live"
        self.error("AX-BORROW-0005", message, node, "borrow_checker")

    def register_borrow(
        self,
        binding: LocalBinding,
        *,
        mutable: bool,
        borrow_node: Node,
        holder_node: Node,
        temporary: bool,
    ) -> BorrowRecord | None:
        active = self.active_borrows(binding)
        if mutable:
            if not binding.mutable:
                self.error(
                    "AX-BORROW-0001",
                    f"cannot mutably borrow immutable binding: {binding.name}",
                    borrow_node,
                    "borrow_checker",
                )
                return None
            if active:
                self.error(
                    "AX-BORROW-0003",
                    f"cannot mutably borrow {binding.name} while another borrow is live",
                    borrow_node,
                    "borrow_checker",
                )
                return None
        elif any(record.mutable for record in active):
            self.error(
                "AX-BORROW-0002",
                f"cannot shared-borrow {binding.name} while a mutable borrow is live",
                borrow_node,
                "borrow_checker",
            )
            return None

        record = BorrowRecord(
            root_node_id=binding.node_id,
            root_name=binding.name,
            mutable=mutable,
            holder_node_id=holder_node.node_id,
            borrow_node_id=borrow_node.node_id,
            temporary=temporary,
        )
        self.borrow_scopes[-1].append(record)
        self.borrow_events.append(
            {
                "root_node_id": binding.node_id,
                "root_name": binding.name,
                "mutable": mutable,
                "holder_node_id": holder_node.node_id,
                "borrow_node_id": borrow_node.node_id,
                "temporary": temporary,
            }
        )
        key = "mutable_borrows" if mutable else "shared_borrows"
        self.function_facts[self.current_function_name][key] += 1
        return record

    def release_temporary_borrows(self, records: list[BorrowRecord]) -> None:
        for record in reversed(records):
            for scope in reversed(self.borrow_scopes):
                if record in scope:
                    scope.remove(record)
                    break

    def type_borrow_expr(
        self,
        expression: Node,
        scopes: list[dict[str, LocalBinding]],
        function_name: str,
        *,
        holder_node: Node,
        temporary: bool,
    ) -> tuple[str, BorrowRecord | None]:
        target = expression.fields["target"]
        info = self.type_lvalue(target, scopes, function_name, purpose="borrow")
        if info.type_name == "error":
            return "error", None
        if info.via_reference or info.root_binding is None:
            self.error(
                "AX-BORROW-0007",
                "reborrowing through a reference is outside the v0.7 scoped-reference subset",
                target,
                "borrow_checker",
            )
            return "error", None
        mutable = bool(expression.fields["mutable"])
        record = self.register_borrow(
            info.root_binding,
            mutable=mutable,
            borrow_node=expression,
            holder_node=holder_node,
            temporary=temporary,
        )
        if record is None:
            return "error", None
        result = reference_type(info.type_name, mutable)
        self.node_types[expression.node_id] = result
        self.references.append(
            {
                "node_id": expression.node_id,
                "name": info.root_binding.name,
                "kind": "mutable_borrow" if mutable else "shared_borrow",
                "target_node_id": info.root_binding.node_id,
            }
        )
        return result, record

    def type_deref_expr(
        self,
        expression: Node,
        scopes: list[dict[str, LocalBinding]],
        function_name: str,
    ) -> str:
        reference = expression.fields["reference"]
        reference_type_name = self.type_expr(reference, scopes, function_name)
        parsed = parse_reference_type(reference_type_name)
        if parsed is None:
            if reference_type_name != "error":
                self.error(
                    "AX-REF-0006",
                    f"dereference requires a reference, found {reference_type_name}",
                    expression,
                    "type_checker",
                )
            return "error"
        self.function_facts[function_name]["deref_reads"] += 1
        self.references.append(
            {
                "node_id": expression.node_id,
                "name": "*",
                "kind": "dereference_read",
                "target_node_id": reference.node_id,
            }
        )
        return parsed[0]
