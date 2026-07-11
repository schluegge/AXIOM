from __future__ import annotations

from .model import Node


class Formatter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def format(self, program: Node) -> str:
        self.lines = []
        profile = program.fields.get("profile")
        if isinstance(profile, Node):
            self.lines.append(f"profile {profile.fields['name']};")
            self.lines.append("")

        structs = program.fields.get("structs", [])
        for index, declaration in enumerate(structs):
            self.format_struct(declaration)
            if index + 1 < len(structs) or program.fields["functions"]:
                self.lines.append("")

        functions = program.fields["functions"]
        for index, function in enumerate(functions):
            self.format_function(function)
            if index + 1 < len(functions):
                self.lines.append("")
        return "\n".join(self.lines) + "\n"

    def format_struct(self, declaration: Node) -> None:
        self.lines.append(f"struct {declaration.fields['name']} {{")
        for field in declaration.fields["fields"]:
            self.lines.append(f"    {field.fields['name']}: {field.fields['type_name']},")
        self.lines.append("}")

    def format_function(self, function: Node) -> None:
        parameters = ", ".join(
            f"{parameter.fields['name']}: {parameter.fields['type_name']}"
            for parameter in function.fields["parameters"]
        )
        self.lines.append(
            f"fn {function.fields['name']}({parameters}) -> {function.fields['return_type']} {{"
        )
        self.format_block(function.fields["body"], 1)
        self.lines.append("}")

    def format_block(self, block: Node, indent: int) -> None:
        prefix = "    " * indent
        for statement in block.fields["statements"]:
            kind = statement.kind
            if kind in {"LetStmt", "VarStmt"}:
                keyword = "var" if kind == "VarStmt" else "let"
                self.lines.append(
                    f"{prefix}{keyword} {statement.fields['name']}: {statement.fields['type_name']} = "
                    f"{self.format_expr(statement.fields['value'])};"
                )
            elif kind == "AssignmentStmt":
                self.lines.append(
                    f"{prefix}{self.format_expr(statement.fields['target'])} = {self.format_expr(statement.fields['value'])};"
                )
            elif kind == "ReturnStmt":
                self.lines.append(f"{prefix}return {self.format_expr(statement.fields['value'])};")
            elif kind == "ExprStmt":
                self.lines.append(f"{prefix}{self.format_expr(statement.fields['expression'])};")
            elif kind == "IfStmt":
                self.lines.append(f"{prefix}if {self.format_expr(statement.fields['condition'])} {{")
                self.format_block(statement.fields["then_block"], indent + 1)
                else_block = statement.fields.get("else_block")
                if isinstance(else_block, Node):
                    self.lines.append(f"{prefix}}} else {{")
                    self.format_block(else_block, indent + 1)
                self.lines.append(f"{prefix}}}")
            elif kind == "WhileStmt":
                self.lines.append(f"{prefix}while {self.format_expr(statement.fields['condition'])} {{")
                self.format_block(statement.fields["body"], indent + 1)
                self.lines.append(f"{prefix}}}")
            else:
                raise ValueError(f"unsupported statement for formatter: {kind}")

    def format_expr(self, expression: Node) -> str:
        if expression.kind == "IntegerLiteral":
            return str(expression.fields["value"])
        if expression.kind == "BoolLiteral":
            return "true" if expression.fields["value"] else "false"
        if expression.kind == "NameExpr":
            return str(expression.fields["name"])
        if expression.kind == "CallExpr":
            arguments = ", ".join(self.format_expr(arg) for arg in expression.fields["arguments"])
            return f"{expression.fields['callee']}({arguments})"
        if expression.kind == "StructLiteral":
            fields = ", ".join(
                f"{field.fields['name']}: {self.format_expr(field.fields['value'])}"
                for field in expression.fields["fields"]
            )
            return f"{expression.fields['type_name']} {{ {fields} }}"
        if expression.kind == "ArrayLiteral":
            return "[" + ", ".join(self.format_expr(item) for item in expression.fields["elements"]) + "]"
        if expression.kind == "FieldExpr":
            return f"{self.format_expr(expression.fields['base'])}.{expression.fields['field']}"
        if expression.kind == "IndexExpr":
            return f"{self.format_expr(expression.fields['base'])}[{self.format_expr(expression.fields['index'])}]"
        if expression.kind == "BinaryExpr":
            return (
                f"({self.format_expr(expression.fields['left'])} "
                f"{expression.fields['operator']} "
                f"{self.format_expr(expression.fields['right'])})"
            )
        raise ValueError(f"unsupported expression for formatter: {expression.kind}")
