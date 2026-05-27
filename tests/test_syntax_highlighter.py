from src.syntax_highlighter import highlight_code, tokenize_code


def test_tokenize_python_code():
    tokens = tokenize_code('print("hello")', "python")

    assert len(tokens) > 0
    assert any(token[0] for token in tokens)


def test_highlight_code_returns_colored_segments():
    result = highlight_code("def foo():\n    return 42\n", "python")

    assert len(result) > 0
    assert all(len(token) == 2 for line in result for token in line)


def test_unknown_language_falls_back():
    result = highlight_code("some code", "fakelang")

    assert len(result) > 0


def test_empty_code_returns_empty():
    result = highlight_code("", "python")

    assert result == []
