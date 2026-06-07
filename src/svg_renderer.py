from __future__ import annotations

import re
from io import BytesIO

from PIL import Image

CJK_FONT_FAMILY = (
    "PingFang SC, Hiragino Sans GB, STHeiti, Microsoft YaHei, "
    "Noto Sans CJK SC, Arial Unicode MS, sans-serif"
)


def render_svg_to_png(svg_code: str, output_path: str) -> None:
    """Render SVG code string to a PNG file."""
    import cairosvg
    svg_with_fonts = inject_cjk_font(svg_code)
    png_data = cairosvg.svg2png(bytestring=svg_with_fonts.encode("utf-8"))
    img = Image.open(BytesIO(png_data)).convert("RGB")
    img.save(output_path, "PNG")


def render_svg_to_image(svg_code: str) -> Image.Image:
    """Render SVG code string to a PIL Image (in-memory)."""
    import cairosvg
    svg_with_fonts = inject_cjk_font(svg_code)
    png_data = cairosvg.svg2png(bytestring=svg_with_fonts.encode("utf-8"))
    return Image.open(BytesIO(png_data)).convert("RGB")


def inject_cjk_font(svg_text: str) -> str:
    """Inject CJK font fallback into SVG so Chinese/Japanese/Korean text renders correctly."""
    replacement = f'font-family="{CJK_FONT_FAMILY}"'
    # Replace SVG attribute form: font-family="..."
    if re.search(r'font-family="[^"]*"', svg_text):
        svg_text = re.sub(r'font-family="[^"]*"', replacement, svg_text)
    else:
        svg_text = re.sub(r"<svg\b", f"<svg {replacement}", svg_text, count=1)
    # Replace CSS form: font-family: ...;
    svg_text = re.sub(
        r"font-family\s*:\s*[^;\"']+",
        f"font-family: {CJK_FONT_FAMILY}",
        svg_text,
    )
    return svg_text
