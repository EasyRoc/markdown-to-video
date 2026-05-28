from io import BytesIO
from pathlib import Path
import re

from PIL import Image


CJK_FONT_FAMILY = (
    "PingFang SC, Hiragino Sans GB, STHeiti, Microsoft YaHei, "
    "Noto Sans CJK SC, Arial Unicode MS, sans-serif"
)


def load_image(path: str) -> Image.Image:
    image_path = Path(path)
    if image_path.suffix.lower() == ".svg":
        try:
            import cairosvg
        except ImportError as exc:
            raise RuntimeError("SVG images require cairosvg to render") from exc
        svg_text = image_path.read_text(encoding="utf-8")
        png_data = cairosvg.svg2png(
            bytestring=_svg_text_with_fallback_font(svg_text).encode("utf-8")
        )
        return Image.open(BytesIO(png_data)).convert("RGB")

    return Image.open(image_path).convert("RGB")


def _svg_text_with_fallback_font(svg_text: str) -> str:
    replacement = f'font-family="{CJK_FONT_FAMILY}"'
    if re.search(r'font-family="[^"]*"', svg_text):
        svg_text = re.sub(r'font-family="[^"]*"', replacement, svg_text)
    else:
        svg_text = re.sub(r"<svg\b", f"<svg {replacement}", svg_text, count=1)

    return re.sub(
        r"font-family\s*:\s*[^;\"']+",
        f"font-family: {CJK_FONT_FAMILY}",
        svg_text,
    )
