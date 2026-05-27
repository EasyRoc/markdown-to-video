from hashlib import md5
from pathlib import Path

from PIL import Image, ImageDraw

from src.layouts import LayoutFactory
from src.layouts.base import _get_font
from src.parser import Segment


SAMPLE_CFG = {
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


def test_factory_returns_text_only_layout():
    layout = LayoutFactory.create("text-only")
    from src.layouts.text_only import TextOnlyLayout

    assert isinstance(layout, TextOnlyLayout)


def test_factory_returns_image_right_layout():
    layout = LayoutFactory.create("image-right")
    from src.layouts.image_right import ImageRightLayout

    assert isinstance(layout, ImageRightLayout)


def test_factory_unknown_returns_text_only():
    layout = LayoutFactory.create("nonexistent")
    from src.layouts.text_only import TextOnlyLayout

    assert isinstance(layout, TextOnlyLayout)


def test_layout_font_fallback_supports_distinct_chinese_glyphs():
    font = _get_font("/missing/font.ttf", 48)

    hashes = {_glyph_hash(font, char) for char in "中文测试"}

    assert len(hashes) == 4


def test_text_only_renders(tmp_path):
    seg = Segment(
        0,
        "Section Title",
        2,
        "section",
        "Section Title\n\nThis is body content.",
    )
    seg.layout = "text-only"

    layout = LayoutFactory.create("text-only")
    path = layout.render(seg, SAMPLE_CFG, tmp_path / "frames")

    assert path.endswith(".png")
    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_text_only_draws_progress_bar(tmp_path):
    seg = Segment(1, "Progress", 2, "section", "Progress\n\nBody.")

    layout = LayoutFactory.create("text-only")
    path = layout.render(seg, SAMPLE_CFG, tmp_path / "frames")
    img = Image.open(path)

    assert img.getpixel((10, img.height - 2)) == (74, 144, 217)


def test_image_right_renders_with_image(tmp_path):
    img_path = tmp_path / "test_img.png"
    test_img = Image.new("RGB", (400, 300), color=(100, 150, 200))
    test_img.save(img_path)

    seg = Segment(
        0,
        "Diagram",
        2,
        "section",
        "Diagram\n\nHere is the architecture.",
    )
    seg.layout = "image-right"
    seg.image_path = str(img_path)

    layout = LayoutFactory.create("image-right")
    path = layout.render(seg, SAMPLE_CFG, tmp_path / "frames")

    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_factory_returns_image_below_layout():
    layout = LayoutFactory.create("image-below")
    from src.layouts.image_below import ImageBelowLayout

    assert isinstance(layout, ImageBelowLayout)


def test_factory_returns_image_full_layout():
    layout = LayoutFactory.create("image-full")
    from src.layouts.image_full import ImageFullLayout

    assert isinstance(layout, ImageFullLayout)


def test_image_below_renders(tmp_path):
    img_path = tmp_path / "test_img.png"
    Image.new("RGB", (600, 200), color=(100, 180, 100)).save(img_path)

    seg = Segment(0, "Chart", 2, "section", "Chart\n\nData analysis results.")
    seg.layout = "image-below"
    seg.image_path = str(img_path)

    layout = LayoutFactory.create("image-below")
    path = layout.render(seg, SAMPLE_CFG, tmp_path / "frames")

    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_image_full_renders(tmp_path):
    img_path = tmp_path / "bg_img.png"
    Image.new("RGB", (800, 600), color=(50, 50, 80)).save(img_path)

    seg = Segment(0, "Overview", 1, "title_slide", "Overview")
    seg.layout = "image-full"
    seg.image_path = str(img_path)

    layout = LayoutFactory.create("image-full")
    path = layout.render(seg, SAMPLE_CFG, tmp_path / "frames")

    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def _glyph_hash(font, char: str) -> str:
    image = Image.new("L", (80, 80), 0)
    draw = ImageDraw.Draw(image)
    draw.text((10, 10), char, font=font, fill=255)
    return md5(image.tobytes()).hexdigest()
