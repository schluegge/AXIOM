from __future__ import annotations

from .model import Diagnostic, Node
from .parser_support import ParseFailure


class ExpressionParserMixin:
    def parse_expression(self) -> Node:
        return self.parse_comparison()

    def parse_comparison(self) -> Node:
        expression = self.parse_additive()
        while self.current().kind in {"less", "less_equal", "greater", "greater_equal", "equal_equal", "bang_equal"}:
            operator = self.take()
            right = self.parse_additive()
            expression = self.node(
                "BinaryExpr",
                expression.span,
                right.span,
                operator=operator.lexeme,
                left=expression,
                right=right,
            )
        return expression

    def parse_additive(self) -> Node:
        expression = self.parse_multiplicative()
        while self.current().kind in {"plus", "minus"}:
            operator = self.take()
            right = self.parse_multiplicative()
            expression = self.node(
                "BinaryExpr",
                expression.span,
                right.span,
                operator=operator.lexeme,
                left=expression,
                right=right,
            )
        return expression

    def parse_multiplicative(self) -> Node:
        expression = self.parse_postfix()
        while self.current().kind in {"star", "slash", "percent"}:
            operator = self.take()
            right = self.parse_postfix()
            expression = self.node(
                "BinaryExpr",
                expression.span,
                right.span,
                operator=operator.lexeme,
                left=expression,
                right=right,
            )
        return expression

    def parse_postfix(self) -> Node:
        expression = self.parse_atom()
        while True:
            if self.accept("dot") is not None:
                field = self.expect("identifier", "expected field name after '.'")
                expression = self.node(
                    "FieldExpr",
                    expression.span,
                    field.span,
                    base=expression,
                    field=field.lexeme,
                )
                continue
            if self.accept("left_bracket") is not None:
                index = self.parse_expression()
                end = self.expect("right_bracket", "expected ']' after array index")
                expression = self.node(
                    "IndexExpr",
                    expression.span,
                    end.span,
                    base=expression,
                    index=index,
                )
                continue
            break
        return expression

    def parse_atom(self) -> Node:
        token = self.current()
        if token.kind == "integer_literal":
            self.take()
            value = int(token.lexeme.replace("_", ""))
            return self.node("IntegerLiteral", token.span, token.span, value=value)
        if token.kind in {"true", "false"}:
            self.take()
            return self.node("BoolLiteral", token.span, token.span, value=token.kind == "true")
        if token.kind == "left_bracket":
            start = self.take()
            elements: list[Node] = []
            if not self.at("right_bracket"):
                while True:
                    elements.append(self.parse_expression())
                    if self.accept("comma") is None:
                        break
                    if self.at("right_bracket"):
                        break
            end = self.expect("right_bracket", "expected ']' after array literal")
            return self.node("ArrayLiteral", start.span, end.span, elements=elements)
        if token.kind == "identifier":
            self.take()
            if self.at("left_brace") and (
                self.peek_kind(1) == "right_brace"
                or (self.peek_kind(1) == "identifier" and self.peek_kind(2) == "colon")
            ):
                self.take()
                fields: list[Node] = []
                if not self.at("right_brace"):
                    while True:
                        field_name = self.expect("identifier", "expected struct literal field")
                        self.expect("colon", "expected ':' after struct literal field")
                        value = self.parse_expression()
                        fields.append(
                            self.node(
                                "FieldInit",
                                field_name.span,
                                value.span,
                                name=field_name.lexeme,
                                value=value,
                            )
                        )
                        if self.accept("comma") is None:
                            break
                        if self.at("right_brace"):
                            break
                end = self.expect("right_brace", "expected '}' after struct literal")
                return self.node(
                    "StructLiteral",
                    token.span,
                    end.span,
                    type_name=token.lexeme,
                    fields=fields,
                )
            if self.accept("left_paren") is not None:
                arguments: list[Node] = []
                if not self.at("right_paren"):
                    while True:
                        arguments.append(self.parse_expression())
                        if self.accept("comma") is None:
                            break
                end = self.expect("right_paren", "expected ')' after arguments")
                return self.node(
                    "CallExpr",
                    token.span,
                    end.span,
                    callee=token.lexeme,
                    arguments=arguments,
                )
            return self.node("NameExpr", token.span, token.span, name=token.lexeme)
        if self.accept("left_paren") is not None:
            expression = self.parse_expression()
            self.expect("right_paren", "expected ')' after expression")
            return expression
        self.diagnostics.append(
            Diagnostic("AX-PARSE-0002", "error", "expected expression", token.span, "parser")
        )
        raise ParseFailure("expected expression")
