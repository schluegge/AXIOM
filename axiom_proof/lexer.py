from __future__ import annotations

from .model import Diagnostic, Position, Span, Token
from .source import SourceFile

KEYWORDS = {
    word: word
    for word in "profile import fn extern struct enum let var return while if else true false".split()
}

PAIRS = {
    "::": "colon_colon",
    "->": "arrow",
    "==": "equal_equal",
    "!=": "bang_equal",
    "<=": "less_equal",
    ">=": "greater_equal",
    "&&": "and_and",
    "||": "or_or",
}

SINGLES = {
    "(": "left_paren",
    ")": "right_paren",
    "{": "left_brace",
    "}": "right_brace",
    "[": "left_bracket",
    "]": "right_bracket",
    ",": "comma",
    ";": "semicolon",
    ":": "colon",
    "=": "equal",
    "!": "bang",
    "<": "less",
    ">": "greater",
    "+": "plus",
    "-": "minus",
    "*": "star",
    "/": "slash",
    "%": "percent",
    "&": "ampersand",
    ".": "dot",
}


class Lexer:
    def __init__(self, source: SourceFile):
        self.source = source
        self.text = source.text
        self.byte_offsets: list[int] = []
        byte = 0
        for char in self.text:
            self.byte_offsets.append(byte)
            byte += len(char.encode("utf-8"))
        self.byte_offsets.append(byte)
        self.index = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []
        self.diagnostics: list[Diagnostic] = []

    def marker(self) -> Position:
        return Position(self.byte_offsets[self.index], self.line, self.column)

    def peek(self, amount: int = 0) -> str | None:
        index = self.index + amount
        return self.text[index] if index < len(self.text) else None

    def advance(self) -> str | None:
        char = self.peek()
        if char is None:
            return None
        if char == "\r":
            self.index += 1
            if self.peek() == "\n":
                self.index += 1
            self.line += 1
            self.column = 1
            return "\n"
        self.index += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def span(self, start: Position) -> Span:
        end = self.marker()
        return Span(
            source_path=self.source.path,
            byte_start=start.byte,
            byte_end=end.byte,
            line_start=start.line,
            column_start=start.column,
            line_end=end.line,
            column_end=end.column,
        )

    def raw(self, start: Position) -> str:
        return self.source.data[start.byte : self.marker().byte].decode("utf-8")

    def add(self, kind: str, start: Position) -> None:
        self.tokens.append(Token(kind, self.raw(start), self.span(start)))

    def error(self, code: str, message: str, start: Position) -> None:
        self.diagnostics.append(Diagnostic(code, "error", message, self.span(start), "lexer"))

    def run(self) -> tuple[list[Token], list[Diagnostic]]:
        while self.peek() is not None:
            char = self.peek()
            assert char is not None
            if char.isspace():
                self.advance()
                continue
            start = self.marker()
            if char == "_" or char.isalpha():
                self.advance()
                while (next_char := self.peek()) is not None and (
                    next_char == "_" or next_char.isalpha() or next_char.isnumeric()
                ):
                    self.advance()
                raw = self.raw(start)
                self.add(KEYWORDS.get(raw, "identifier"), start)
                continue
            if char.isascii() and char.isdigit():
                self.advance()
                while (next_char := self.peek()) is not None and (
                    (next_char.isascii() and next_char.isdigit()) or next_char == "_"
                ):
                    self.advance()
                raw = self.raw(start)
                if raw.endswith("_") or "__" in raw:
                    self.error(
                        "AX-LEX-0002",
                        "integer separators must appear singly between decimal digits",
                        start,
                    )
                self.add("integer_literal", start)
                continue
            if char == '"':
                self.advance()
                closed = False
                while self.peek() is not None:
                    current = self.peek()
                    if current == '"':
                        self.advance()
                        closed = True
                        break
                    if current in ("\r", "\n"):
                        break
                    if current == "\\":
                        escape_start = self.marker()
                        self.advance()
                        escape = self.peek()
                        if escape is None or escape in ("\r", "\n"):
                            break
                        self.advance()
                        if escape not in ['"', "\\", "n", "r", "t", "0"]:
                            self.error(
                                "AX-LEX-0004",
                                f"unsupported string escape: \\{escape}",
                                escape_start,
                            )
                    else:
                        self.advance()
                if not closed:
                    self.error("AX-LEX-0003", "unterminated string literal", start)
                self.add("string_literal", start)
                continue
            if char == "/" and self.peek(1) == "/":
                self.advance()
                self.advance()
                while self.peek() is not None and self.peek() not in ("\r", "\n"):
                    self.advance()
                self.add("line_comment", start)
                continue
            if char == "/" and self.peek(1) == "*":
                self.advance()
                self.advance()
                depth = 1
                while self.peek() is not None and depth:
                    if self.peek() == "/" and self.peek(1) == "*":
                        self.advance()
                        self.advance()
                        depth += 1
                    elif self.peek() == "*" and self.peek(1) == "/":
                        self.advance()
                        self.advance()
                        depth -= 1
                    else:
                        self.advance()
                if depth:
                    self.error("AX-LEX-0006", "unterminated block comment", start)
                self.add("block_comment", start)
                continue
            pair = char + (self.peek(1) or "")
            if pair in PAIRS:
                self.advance()
                self.advance()
                self.add(PAIRS[pair], start)
                continue
            if char in SINGLES:
                self.advance()
                self.add(SINGLES[char], start)
                continue
            bad = self.advance()
            self.error("AX-LEX-0001", f"unexpected character: {bad!r}", start)
            self.add("invalid", start)
        end = self.marker()
        eof_span = Span(
            self.source.path,
            end.byte,
            end.byte,
            end.line,
            end.column,
            end.line,
            end.column,
        )
        self.tokens.append(Token("eof", "", eof_span))
        return self.tokens, self.diagnostics
