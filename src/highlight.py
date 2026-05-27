from PIL import Image, ImageDraw

from src.layouts.base import _get_font, _hex_to_rgb


def find_highlight_spans(text: str, keyword: str) -> list[tuple[int, int]]:
    if not keyword:
        return []

    spans = []
    start = 0
    while True:
        index = text.find(keyword, start)
        if index == -1:
            break
        spans.append((index, index + len(keyword)))
        start = index + 1
    return spans


def render_highlighted_text(text: str, keyword: str, cfg: dict) -> Image.Image | None:
    if not find_highlight_spans(text, keyword):
        return None

    width = cfg["width"]
    height = cfg.get("height", 200)
    bg = _hex_to_rgb(cfg["bg_color"])
    accent = _hex_to_rgb(cfg["accent_color"])
    text_color = _hex_to_rgb(cfg["text_color"])

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    font_normal = _get_font(cfg["font_family"], cfg["font_size_body"])
    font_highlight = _get_font(
        cfg["font_family"],
        int(cfg["font_size_body"] * 1.15),
    )

    x = 60
    y = 60
    last_end = 0
    for start, end in find_highlight_spans(text, keyword):
        normal_part = text[last_end:start]
        if normal_part:
            draw.text((x, y), normal_part, font=font_normal, fill=text_color)
            x += _text_width(draw, normal_part, font_normal)

        highlighted_part = text[start:end]
        draw.text((x, y), highlighted_part, font=font_highlight, fill=accent)
        x += _text_width(draw, highlighted_part, font_highlight)
        last_end = end

    remaining = text[last_end:]
    if remaining:
        draw.text((x, y), remaining, font=font_normal, fill=text_color)

    return image


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]
