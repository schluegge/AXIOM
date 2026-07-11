from __future__ import annotations

from .model import Diagnostic, Node, Span, Token, merge_span

TRIVIA = {"line_comment", "block_comment"}


class ParseFailure(Exception):
    pass


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = [token for token in tokens if token.kind not in TRIVIA]
        self.index = 0
        self.diagnostics: list[Diagnostic] = []

    def current(self) -> Token:
        return self.tokens[min(self.index, len(self.tokens) - 1)]

    def previous(self) -> Token:
        return self.tokens[max(0, self.index - 1)]

    def peek_kind(self, amount: int = 1) -> str:
        index = min(self.index + amount, len(self.tokens) - 1)
        return self.tokens[index].kind

    def at(self, kind: str) -> bool:
        return self.current().kind == kind

    def take(self) -> Token:
        token = self.current()
        if token.kind != "eof":
            self.index += 1
        return token

    def accept(self, kind: str) -> Token | None:
        if self.at(kind):
            return self.take()
        return None

    def expect(self, kind: str, message: str) -> Token:
        if self.at(kind):
            return self.take()
        token = self.current()
        self.diagnostics.append(Diagnostic("AX-PARSE-0001", "error", message, token.span, "parser"))
        raise ParseFailure(message)

    def node(self, kind: str, start: Span, end: Span, **fields: object) -> Node:
        result = Node(kind, merge_span(start, end), dict(fields))
        result.finalize_id()
        return result

    def parse(self) -> Node | None:
        try:
            start = self.current().span
            profile = None
            if self.at("profile"):
                profile = self.parse_profile()
            functions: list[Node] = []
            while not self.at("eof"):
                functions.append(self.parse_function())
            end = self.current().span
            return self.node("Program", start, end, profile=profile, functions=functions)
        except ParseFailure:
            return None

    def parse_profile(self) -> Node:
        start = self.expect("profile", "expected 'profile'")
        name = self.expect("identifier", "expected profile name")
        end = self.expect("semicolon", "expected ';' after profile declaration")
        return self.node("ProfileDecl", start.span, end.span, name=name.lexeme)

    def parse_function(self) -> Node:
        start = self.expect("fn", "expected function declaration")
        name = self.expect("identifier", "expected function name")
        self.expect("left_paren", "expected '(' after function name")
        parameters: list[Node] = []
        if not self.at("right_paren"):
            while True:
                param_start = self.expect("identifier", "expected parameter name")
                self.expect("colon", "expected ':' after parameter name")
                type_token = self.expect("identifier", "expected parameter type")
                parameters.append(
                    self.node(
                        "Parameter",
                        param_start.span,
                        type_token.span,
                        name=param_start.lexeme,
                        type_name=type_token.lexeme,
                    )
                )
                if self.accept("comma") is None:
                    break
        self.expect("right_paren", "expected ')' after parameters")
        return_type = "unit"
        if self.accept("arrow") is not None:
            return_type = self.expect("identifier", "expected return type").lexeme
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
        type_name = self.expect("identifier", "expected binding type")
        self.expect("equal", "expected '=' in binding")
        value = self.parse_expression()
        end = self.expect("semicolon", "expected ';' after binding")
        return self.node(
            "VarStmt" if mutable else "LetStmt",
            start.span,
            end.span,
            name=name.lexeme,
            type_name=type_name.lexeme,
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
        expression = self.parse_primary()
        while self.current().kind in {"star", "slash", "percent"}:
            operator = self.take()
            right = self.parse_primary()
            expression = self.node(
                "BinaryExpr",
                expression.span,
                right.span,
                operator=operator.lexeme,
                left=expression,
                right=right,
            )
        return expression

    def parse_primary(self) -> Node:
        token = self.current()
        if token.kind == "integer_literal":
            self.take()
            value = int(token.lexeme.replace("_", ""))
            return self.node("IntegerLiteral", token.span, token.span, value=value)
        if token.kind in {"true", "false"}:
            self.take()
            return self.node("BoolLiteral", token.span, token.span, value=token.kind == "true")
        if token.kind == "identifier":
            self.take()
            expression = self.node("NameExpr", token.span, token.span, name=token.lexeme)
            if self.accept("left_paren") is not None:
                arguments: list[Node] = []
                if not self.at("right_paren"):
                    while True:
                        arguments.append(self.parse_expression())
                        if self.accept("comma") is None:
                            break
                end = self.expect("right_paren", "expected ')' after arguments")
                expression = self.node(
                    "CallExpr",
                    token.span,
                    end.span,
                    callee=token.lexeme,
                    arguments=arguments,
                )
            return expression
        if self.accept("left_paren") is not None:
            expression = self.parse_expression()
            self.expect("right_paren", "expected ')' after expression")
            return expression
        self.diagnostics.append(
            Diagnostic("AX-PARSE-0002", "error", "expected expression", token.span, "parser")
        )
        raise ParseFailure("expected expression")
