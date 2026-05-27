from pathlib import Path

from PIL import Image

from src.parser import Segment
from src.renderer import _hex_to_rgb, render_segment


SAMPLE_CFG = {
    "render": {
        "width": 800,
        "height": 600,
        "font_family": "/System/Library/Fonts/STHeiti Medium.ttc",
        "font_family_mono": "/System/Library/Fonts/SFNSMono.ttf",
        "font_size_title": 48,
        "font_size_body": 28,
        "font_size_code": 22,
        "bg_color": "#f5f5f5",
        "code_bg_color": "#1e1e1e",
        "accent_color": "#4A90D9",
        "text_color": "#333333",
        "light_text_color": "#e0e0e0",
    }
}


def test_hex_to_rgb():
    assert _hex_to_rgb("#ff0000") == (255, 0, 0)
    assert _hex_to_rgb("#4A90D9") == (74, 144, 217)
    assert _hex_to_rgb("#1e1e1e") == (30, 30, 30)


def test_render_title_slide_uses_layout(tmp_path):
    seg = Segment(
        0,
        "Python Tutorial",
        1,
        "title_slide",
        "Python Tutorial\n\nAuthor: Test",
    )
    seg.layout = "text-only"

    path = render_segment(seg, SAMPLE_CFG, str(tmp_path))

    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_render_code_block_uses_layout(tmp_path):
    seg = Segment(
        1,
        "Example Code",
        2,
        "code_block",
        "Example Code\n\n```\nprint('hello')\n```",
    )
    seg.layout = "text-only"

    path = render_segment(seg, SAMPLE_CFG, str(tmp_path))

    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_render_list_uses_layout(tmp_path):
    seg = Segment(
        2,
        "Features",
        2,
        "list",
        "Features\n* Feature A\n* Feature B\n* Feature C",
    )
    seg.layout = "text-only"

    path = render_segment(seg, SAMPLE_CFG, str(tmp_path))

    assert Path(path).exists()


def test_render_falls_back_to_text_only_without_image(tmp_path):
    seg = Segment(0, "Title", 2, "section", "Title\n\nContent.")
    seg.layout = "image-right"
    seg.image_path = None

    path = render_segment(seg, SAMPLE_CFG, str(tmp_path))

    assert Path(path).exists()
    assert seg.layout == "text-only"
