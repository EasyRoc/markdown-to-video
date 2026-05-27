from pathlib import Path
from hashlib import md5

from PIL import Image, ImageDraw

from src.parser import Segment
from src.renderer import _get_font, _hex_to_rgb, render_segment


def _render_config(width=800, height=600):
    return {
        "render": {
            "width": width,
            "height": height,
            "font_family": "/System/Library/Fonts/PingFang.ttc",
            "font_family_mono": "/System/Library/Fonts/SFNSMono.ttf",
            "font_size_title": 48,
            "font_size_body": 28,
            "font_size_code": 24,
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


def test_font_fallback_supports_distinct_chinese_glyphs():
    font = _get_font("/missing/font.ttf", 48)

    hashes = {_glyph_hash(font, char) for char in "中文测试"}

    assert len(hashes) == 4


def test_render_title_slide(tmp_path):
    seg = Segment(
        index=0,
        title="Python 入门教程",
        level=1,
        type="title_slide",
        text="Python 入门教程\n\n作者：测试",
    )

    path = render_segment(seg, _render_config(), str(tmp_path))

    assert path.endswith(".png")
    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_render_code_block(tmp_path):
    seg = Segment(
        index=1,
        title="示例代码",
        level=2,
        type="code_block",
        text="示例代码\n\n```\nprint('hello')\n```",
    )

    path = render_segment(seg, _render_config(), str(tmp_path))
    img = Image.open(path)

    pixels = list(img.getdata())
    dark_pixels = sum(1 for pixel in pixels if all(channel < 50 for channel in pixel))
    assert dark_pixels > len(pixels) * 0.3


def test_render_list(tmp_path):
    seg = Segment(
        index=2,
        title="功能列表",
        level=2,
        type="list",
        text="功能列表\n* 功能一\n* 功能二\n* 功能三",
    )

    path = render_segment(seg, _render_config(), str(tmp_path))

    assert Path(path).exists()


def _glyph_hash(font, char: str) -> str:
    image = Image.new("L", (80, 80), 0)
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), char, font=font, fill=255)
    return md5(image.tobytes()).hexdigest()
