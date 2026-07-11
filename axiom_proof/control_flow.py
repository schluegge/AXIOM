from __future__ import annotations

from collections import deque
from typing import Any

from .model import Node


class FunctionCFGBuilder:
    def __init__(self, function: Node):
        self.function = function
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, str]] = []
        self.synthetic_counter = 0
        self.entry = self.synthetic("entry")
        self.exit = self.synthetic("exit")

    def synthetic(self, kind: str, owner: Node | None = None) -> str:
        self.synthetic_counter += 1
        owner_suffix = owner.node_id.removeprefix("n_")[:8] if owner is not None else "function"
        node_id = f"cfg_{kind}_{owner_suffix}_{self.synthetic_counter}"
        record: dict[str, Any] = {"id": node_id, "kind": kind, "synthetic": True}
        if owner is not None:
            record["owner_node_id"] = owner.node_id
            record["span"] = owner.span.to_dict()
        self.nodes[node_id] = record
        return node_id

    def statement_node(self, statement: Node) -> str:
        node_id = f"cfg_stmt_{statement.node_id.removeprefix('n_')}"
        self.nodes[node_id] = {
            "id": node_id,
            "kind": statement.kind,
            "synthetic": False,
            "owner_node_id": statement.node_id,
            "span": statement.span.to_dict(),
        }
        return node_id

    def edge(self, source: str, target: str, kind: str) -> None:
        self.edges.append({"from": source, "to": target, "kind": kind})

    def connect(self, predecessors: list[str], target: str, kind: str) -> None:
        for predecessor in predecessors:
            self.edge(predecessor, target, kind)

    def build_statements(
        self,
        statements: list[Node],
        predecessors: list[str],
        first_edge_kind: str = "next",
    ) -> list[str]:
        current = list(predecessors)
        edge_kind = first_edge_kind
        for statement in statements:
            statement_id = self.statement_node(statement)
            self.connect(current, statement_id, edge_kind)

            if statement.kind in {"LetStmt", "VarStmt", "AssignmentStmt", "ExprStmt"}:
                current = [statement_id]
            elif statement.kind == "ReturnStmt":
                self.edge(statement_id, self.exit, "return")
                current = []
            elif statement.kind == "IfStmt":
                then_statements = statement.fields["then_block"].fields["statements"]
                then_exits = self.build_statements(then_statements, [statement_id], "true")
                if not then_statements:
                    then_exits = [statement_id]

                else_block = statement.fields.get("else_block")
                if isinstance(else_block, Node):
                    else_statements = else_block.fields["statements"]
                    else_exits = self.build_statements(else_statements, [statement_id], "false")
                    if not else_statements:
                        else_exits = [statement_id]
                else:
                    else_exits = [statement_id]

                fallthroughs = [*then_exits, *else_exits]
                if fallthroughs:
                    join = self.synthetic("if_join", statement)
                    for predecessor in then_exits:
                        kind = "true_empty" if predecessor == statement_id else "next"
                        self.edge(predecessor, join, kind)
                    for predecessor in else_exits:
                        kind = "false" if predecessor == statement_id else "next"
                        self.edge(predecessor, join, kind)
                    current = [join]
                else:
                    current = []
            elif statement.kind == "WhileStmt":
                body_statements = statement.fields["body"].fields["statements"]
                after = self.synthetic("while_after", statement)
                self.edge(statement_id, after, "false")
                body_exits = self.build_statements(body_statements, [statement_id], "true")
                if not body_statements:
                    self.edge(statement_id, statement_id, "true_loop_back")
                else:
                    for predecessor in body_exits:
                        self.edge(predecessor, statement_id, "loop_back")
                current = [after]
            else:
                raise ValueError(f"unsupported CFG statement: {statement.kind}")
            edge_kind = "next"
        return current

    def reachable_nodes(self) -> set[str]:
        adjacency: dict[str, list[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge["from"], []).append(edge["to"])
        reachable = {self.entry}
        queue = deque([self.entry])
        while queue:
            source = queue.popleft()
            for target in adjacency.get(source, []):
                if target not in reachable:
                    reachable.add(target)
                    queue.append(target)
        return reachable

    def build(self) -> dict[str, Any]:
        fallthroughs = self.build_statements(
            self.function.fields["body"].fields["statements"],
            [self.entry],
        )
        for predecessor in fallthroughs:
            self.edge(predecessor, self.exit, "fallthrough")

        reachable = self.reachable_nodes()
        nodes = []
        for node_id, node in sorted(self.nodes.items()):
            nodes.append({**node, "reachable": node_id in reachable})
        edges = sorted(self.edges, key=lambda item: (item["from"], item["to"], item["kind"]))
        unreachable = sorted(node_id for node_id in self.nodes if node_id not in reachable)
        return {
            "name": self.function.fields["name"],
            "function_node_id": self.function.node_id,
            "entry": self.entry,
            "exit": self.exit,
            "nodes": nodes,
            "edges": edges,
            "unreachable_nodes": unreachable,
            "all_reachable_paths_terminate": not fallthroughs,
        }


def build_control_flow_document(program: Node) -> dict[str, Any]:
    return {
        "document_kind": "axiom.control-flow",
        "schema_version": "0.6.0",
        "functions": [FunctionCFGBuilder(function).build() for function in program.fields["functions"]],
    }
