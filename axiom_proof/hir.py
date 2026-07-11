from __future__ import annotations

from typing import Any

from .model import Node


def lower_expr(node: Node, types: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "op": node.kind,
        "node_id": node.node_id,
        "type": types.get(node.node_id, "unit"),
    }
    if node.kind in {"IntegerLiteral", "BoolLiteral"}:
        result["value"] = node.fields["value"]
    elif node.kind == "NameExpr":
        result["name"] = node.fields["name"]
    elif node.kind == "CallExpr":
        result["callee"] = node.fields["callee"]
        result["arguments"] = [lower_expr(arg, types) for arg in node.fields["arguments"]]
    elif node.kind == "StructLiteral":
        result["type_name"] = node.fields["type_name"]
        result["fields"] = [
            {"name": field.fields["name"], "value": lower_expr(field.fields["value"], types)}
            for field in node.fields["fields"]
        ]
    elif node.kind == "ArrayLiteral":
        result["elements"] = [lower_expr(item, types) for item in node.fields["elements"]]
    elif node.kind == "FieldExpr":
        result["base"] = lower_expr(node.fields["base"], types)
        result["field"] = node.fields["field"]
    elif node.kind == "IndexExpr":
        result["base"] = lower_expr(node.fields["base"], types)
        result["index"] = lower_expr(node.fields["index"], types)
        result["bounds_check"] = node.fields["index"].kind != "IntegerLiteral"
    elif node.kind == "BorrowExpr":
        result["mutable"] = node.fields["mutable"]
        result["target"] = lower_expr(node.fields["target"], types)
    elif node.kind == "DerefExpr":
        result["reference"] = lower_expr(node.fields["reference"], types)
    elif node.kind == "BinaryExpr":
        result["operator"] = node.fields["operator"]
        result["left"] = lower_expr(node.fields["left"], types)
        result["right"] = lower_expr(node.fields["right"], types)
    else:
        raise ValueError(f"unsupported HIR expression: {node.kind}")
    return result


def lower_statement(node: Node, types: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {"op": node.kind, "node_id": node.node_id}
    if node.kind in {"LetStmt", "VarStmt"}:
        result.update(
            name=node.fields["name"],
            type=node.fields["type_name"],
            mutable=node.kind == "VarStmt",
            value=lower_expr(node.fields["value"], types),
        )
    elif node.kind == "AssignmentStmt":
        result["target"] = lower_expr(node.fields["target"], types)
        result["value"] = lower_expr(node.fields["value"], types)
    elif node.kind == "ReturnStmt":
        result["value"] = lower_expr(node.fields["value"], types)
    elif node.kind == "ExprStmt":
        result["expression"] = lower_expr(node.fields["expression"], types)
    elif node.kind == "IfStmt":
        result["condition"] = lower_expr(node.fields["condition"], types)
        result["then"] = [
            lower_statement(stmt, types) for stmt in node.fields["then_block"].fields["statements"]
        ]
        else_block = node.fields.get("else_block")
        result["else"] = (
            [lower_statement(stmt, types) for stmt in else_block.fields["statements"]]
            if isinstance(else_block, Node)
            else []
        )
    elif node.kind == "WhileStmt":
        result["condition"] = lower_expr(node.fields["condition"], types)
        result["body"] = [
            lower_statement(stmt, types) for stmt in node.fields["body"].fields["statements"]
        ]
    else:
        raise ValueError(f"unsupported HIR statement: {node.kind}")
    return result


def lower_program(program: Node, types: dict[str, str]) -> dict[str, Any]:
    structs = [
        {
            "name": declaration.fields["name"],
            "node_id": declaration.node_id,
            "fields": [
                {"name": field.fields["name"], "type": field.fields["type_name"]}
                for field in declaration.fields["fields"]
            ],
        }
        for declaration in program.fields.get("structs", [])
    ]
    functions = []
    for function in program.fields["functions"]:
        functions.append(
            {
                "name": function.fields["name"],
                "node_id": function.node_id,
                "parameters": [
                    {"name": parameter.fields["name"], "type": parameter.fields["type_name"]}
                    for parameter in function.fields["parameters"]
                ],
                "return_type": function.fields["return_type"],
                "body": [
                    lower_statement(statement, types)
                    for statement in function.fields["body"].fields["statements"]
                ],
            }
        )
    return {
        "document_kind": "axiom.hir",
        "schema_version": "0.7.0",
        "structs": structs,
        "functions": functions,
    }
