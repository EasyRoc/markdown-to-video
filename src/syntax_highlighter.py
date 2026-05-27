from pygments import highlight
from pygments.formatter import Formatter
from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer
from pygments.token import Token


TOKEN_COLORS = {
    Token.Keyword: "#F92672",
    Token.Keyword.Namespace: "#F92672",
    Token.Keyword.Type: "#66D9EF",
    Token.Name.Function: "#A6E22E",
    Token.Name.Class: "#A6E22E",
    Token.Name.Decorator: "#A6E22E",
    Token.String: "#E6DB74",
    Token.String.Doc: "#E6DB74",
    Token.String.Affix: "#E6DB74",
    Token.Number: "#AE81FF",
    Token.Number.Integer: "#AE81FF",
    Token.Number.Float: "#AE81FF",
    Token.Comment: "#75715E",
    Token.Comment.Single: "#75715E",
    Token.Comment.Multiline: "#75715E",
    Token.Operator: "#F92672",
    Token.Operator.Word: "#F92672",
    Token.Name.Builtin: "#66D9EF",
    Token.Name.Builtin.Pseudo: "#66D9EF",
    Token.Generic.Heading: "#A6E22E",
    Token.Generic.Subheading: "#A6E22E",
}


class _TokenCollector(Formatter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tokens: list[tuple[str, str]] = []

    def format(self, tokensource, outfile):
        for token_type, value in tokensource:
            self.tokens.append((_color_for_token(token_type), value))


def tokenize_code(code: str, language: str) -> list[tuple[str, str]]:
    if not code:
        return []

    try:
        lexer = get_lexer_by_name(language or "text", stripnl=False)
    except Exception:
        try:
            lexer = guess_lexer(code)
        except Exception:
            lexer = TextLexer(stripnl=False)

    collector = _TokenCollector()
    highlight(code, lexer, collector)
    return collector.tokens


def highlight_code(code: str, language: str) -> list[list[tuple[str, str]]]:
    if not code:
        return []

    tokens = tokenize_code(code, language)
    lines: list[list[tuple[str, str]]] = []
    current_line: list[tuple[str, str]] = []

    for color, text in tokens:
        parts = text.split("\n")
        for index, part in enumerate(parts):
            if index > 0:
                lines.append(current_line)
                current_line = []
            if part:
                current_line.append((color, part))

    if current_line:
        lines.append(current_line)
    return lines


def _color_for_token(token_type) -> str:
    for configured_type, color in TOKEN_COLORS.items():
        if token_type in configured_type:
            return color
    return "#F8F8F2"
