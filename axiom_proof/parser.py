from __future__ import annotations

from .model import Diagnostic, Node, Span, Token, merge_span
from .type_system import array_type
from .parser_expressions import ExpressionParserMixin
from .parser_declarations import DeclarationParserMixin
from .parser_statements import StatementParserMixin
from .parser_support import ParseFailure

TRIVIA = {"line_comment", "block_comment"}


class Parser(DeclarationParserMixin, StatementParserMixin, ExpressionParserMixin):
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
            structs: list[Node] = []
            functions: list[Node] = []
            while not self.at("eof"):
                if self.at("struct"):
                    structs.append(self.parse_struct())
                else:
                    functions.append(self.parse_function())
            end = self.current().span
            return self.node(
                "Program",
                start,
                end,
                profile=profile,
                structs=structs,
                functions=functions,
            )
        except ParseFailure:
            return None

    def parse_profile(self) -> Node:
        start = self.expect("profile", "expected 'profile'")
        name = self.expect("identifier", "expected profile name")
        end = self.expect("semicolon", "expected ';' after profile declaration")
        return self.node("ProfileDecl", start.span, end.span, name=name.lexeme)

    def parse_type_name(self) -> tuple[str, Span, Span]:
        if self.at("identifier"):
            token = self.take()
            return token.lexeme, token.span, token.span
        start = self.expect("left_bracket", "expected type")
        element, _, _ = self.parse_type_name()
        self.expect("semicolon", "expected ';' between array element type and length")
        length = self.expect("integer_literal", "expected fixed array length")
        end = self.expect("right_bracket", "expected ']' after fixed array type")
        return array_type(element, int(length.lexeme.replace("_", ""))), start.span, end.span

