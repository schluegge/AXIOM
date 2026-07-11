from __future__ import annotations

from .model import Node


class DeclarationParserMixin:
    def parse_struct(self) -> Node:
        start = self.expect("struct", "expected struct declaration")
        name = self.expect("identifier", "expected struct name")
        self.expect("left_brace", "expected '{' after struct name")
        fields: list[Node] = []
        while not self.at("right_brace") and not self.at("eof"):
            field_name = self.expect("identifier", "expected struct field name")
            self.expect("colon", "expected ':' after struct field name")
            type_name, _, type_end = self.parse_type_name()
            fields.append(
                self.node(
                    "StructField",
                    field_name.span,
                    type_end,
                    name=field_name.lexeme,
                    type_name=type_name,
                )
            )
            if self.accept("comma") is None:
                break
        end = self.expect("right_brace", "expected '}' after struct fields")
        return self.node("StructDecl", start.span, end.span, name=name.lexeme, fields=fields)

    def parse_function(self) -> Node:
        start = self.expect("fn", "expected function declaration")
        name = self.expect("identifier", "expected function name")
        self.expect("left_paren", "expected '(' after function name")
        parameters: list[Node] = []
        if not self.at("right_paren"):
            while True:
                param_start = self.expect("identifier", "expected parameter name")
                self.expect("colon", "expected ':' after parameter name")
                type_name, _, type_end = self.parse_type_name()
                parameters.append(
                    self.node(
                        "Parameter",
                        param_start.span,
                        type_end,
                        name=param_start.lexeme,
                        type_name=type_name,
                    )
                )
                if self.accept("comma") is None:
                    break
        self.expect("right_paren", "expected ')' after parameters")
        return_type = "unit"
        if self.accept("arrow") is not None:
            return_type, _, _ = self.parse_type_name()
        body = self.parse_block()
        return self.node(
            "FunctionDecl",
            start.span,
            body.span,
            name=name.lexeme,
            parameters=parameters,
            return_type=return_type,
            body=body,
        )

