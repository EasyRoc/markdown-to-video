from PIL import Image

from src.highlight import find_highlight_spans, render_highlighted_text


def test_find_highlight_spans():
    text = "协程不是线程——它运行在单线程中"
    spans = find_highlight_spans(text, "协程不是线程")

    assert len(spans) == 1
    start, end = spans[0]
    assert text[start:end] == "协程不是线程"


def test_no_highlight_returns_empty():
    spans = find_highlight_spans("普通文本", "不存在的关键词")

    assert len(spans) == 0


def test_render_highlighted_text_returns_image(tmp_path):
    cfg = {
        "width": 800,
        "height": 200,
        "font_family": "/System/Library/Fonts/STHeiti Medium.ttc",
        "font_size_body": 32,
        "bg_color": "#f5f5f5",
        "accent_color": "#4A90D9",
        "text_color": "#333333",
    }
    text = "这是关键结论：异步优于多线程"
    highlight_words = "异步优于多线程"

    img = render_highlighted_text(text, highlight_words, cfg)

    assert isinstance(img, Image.Image)
    assert img.size == (800, 200)
