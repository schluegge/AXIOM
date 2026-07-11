from __future__ import annotations

from .model import Node


class StatementParserMixin:
    def parse_block(self) -> Node:
        start = self.expect("left_brace", "expected '{'")
        statements: list[Node] = []
        while not self.at("right_brace") and not self.at("eof"):
            statements.append(self.parse_statement())
        end = self.expect("right_brace", "expected '}'")
        return self.node("Block", start.span, end.span, statements=statements)

    def parse_statement(self) -> Node:
        if self.at("let"):
            return self.parse_binding(mutable=False)
        if self.at("var"):
            return self.parse_binding(mutable=True)
        if self.at("return"):
            return self.parse_return()
        if self.at("while"):
            return self.parse_while()
        if self.at("if"):
            return self.parse_if()
        if self.at("identifier") and self.peek_kind() == "equal":
            return self.parse_assignment()
        expression = self.parse_expression()
        end = self.expect("semicolon", "expected ';' after expression")
        return self.node("ExprStmt", expression.span, end.span, expression=expression)

    def parse_binding(self, mutable: bool) -> Node:
        start = self.take()
        name = self.expect("identifier", "expected binding name")
        self.expect("colon", "vertical proof requires an explicit type annotation")
        type_name, _, _ = self.parse_type_name()
        self.expect("equal", "expected '=' in binding")
        value = self.parse_expression()
        end = self.expect("semicolon", "expected ';' after binding")
        return self.node(
            "VarStmt" if mutable else "LetStmt",
            start.span,
            end.span,
            name=name.lexeme,
            type_name=type_name,
            value=value,
            mutable=mutable,
        )

    def parse_assignment(self) -> Node:
        target = self.expect("identifier", "expected assignment target")
        self.expect("equal", "expected '=' in assignment")
        value = self.parse_expression()
        end = self.expect("semicolon", "expected ';' after assignment")
        return self.node(
            "AssignmentStmt",
            target.span,
            end.span,
            target=target.lexeme,
            value=value,
        )

    def parse_return(self) -> Node:
        start = self.take()
        value = self.parse_expression()
        end = self.expect("semicolon", "expected ';' after return")
        return self.node("ReturnStmt", start.span, end.span, value=value)

    def parse_while(self) -> Node:
        start = self.take()
        condition = self.parse_expression()
        body = self.parse_block()
        return self.node("WhileStmt", start.span, body.span, condition=condition, body=body)

    def parse_if(self) -> Node:
        start = self.take()
        condition = self.parse_expression()
        then_block = self.parse_block()
        else_block = None
        if self.accept("else") is not None:
            else_block = self.parse_block()
            end = else_block.span
        else:
            end = then_block.span
        return self.node(
            "IfStmt",
            start.span,
            end,
            condition=condition,
            then_block=then_block,
            else_block=else_block,
        )

