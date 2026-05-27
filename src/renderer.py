from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.parser import Segment


CJK_SAMPLE = "中文测试"


def render_segment(segment: Segment, config: dict, cache_dir: str) -> str:
    render_config = config["render"]
    output_path = Path(cache_dir) / f"segment_{segment.index:04d}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if segment.type == "title_slide":
        _render_title_slide(segment, render_config, output_path)
    elif segment.type == "code_block":
        _render_code_page(segment, render_config, output_path)
    elif segment.type == "list":
        _render_list_page(segment, render_config, output_path)
    else:
        _render_section_page(segment, render_config, output_path)

    return str(output_path)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    return tuple(int(hex_color[index : index + 2], 16) for index in (0, 2, 4))


def _get_font(font_path: str, size: int):
    candidates = [
        font_path,
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    loaded_fonts = []
    for candidate in candidates:
        try:
            font = ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
        loaded_fonts.append(font)
        if _font_has_distinct_cjk_glyphs(font):
            return font

    if loaded_fonts:
        return loaded_fonts[0]
    return ImageFont.load_default()


def _font_has_distinct_cjk_glyphs(font) -> bool:
    glyphs = {_glyph_bytes(font, char) for char in CJK_SAMPLE}
    return len(glyphs) == len(CJK_SAMPLE)


def _glyph_bytes(font, char: str) -> bytes:
    image = Image.new("L", (96, 96), 0)
    draw = ImageDraw.Draw(image)
    draw.text((12, 12), char, font=font, fill=255)
    return image.tobytes()


def _render_title_slide(segment: Segment, cfg: dict, output_path: Path) -> None:
    width, height = cfg["width"], cfg["height"]
    bg = _hex_to_rgb(cfg["bg_color"])
    accent = _hex_to_rgb(cfg["accent_color"])
    text_color = _hex_to_rgb(cfg["text_color"])
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    _draw_soft_gradient(draw, width, height, bg, accent)

    title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
    body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
    title = segment.title or segment.text.splitlines()[0]
    body_lines = [
        line.strip()
        for line in segment.text.splitlines()
        if line.strip() and line.strip() != title
    ]

    y = height // 3
    title_lines = _wrap_text(title, title_font, width - 160)
    for line in title_lines[:3]:
        line_height = _draw_centered_text(draw, line, title_font, text_color, y, width)
        y += line_height + 18

    y += 30
    for line in body_lines[:3]:
        line_height = _draw_centered_text(draw, line, body_font, text_color, y, width)
        y += line_height + 14

    draw.rectangle([0, height - 8, width, height], fill=accent)
    image.save(output_path)


def _render_section_page(segment: Segment, cfg: dict, output_path: Path) -> None:
    width, height = cfg["width"], cfg["height"]
    bg = _hex_to_rgb(cfg["bg_color"])
    accent = _hex_to_rgb(cfg["accent_color"])
    text_color = _hex_to_rgb(cfg["text_color"])
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, width, 8], fill=accent)

    title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
    body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
    y = 80
    if segment.title:
        y += _draw_centered_text(draw, segment.title, title_font, text_color, y, width)
        y += 80

    body = _body_without_title(segment)
    for line in _wrap_text(body, body_font, width - 200):
        if y > height - 90:
            break
        if not line:
            y += 28
            continue
        line_height = _draw_centered_text(draw, line, body_font, text_color, y, width)
        y += line_height + 18

    image.save(output_path)


def _render_code_page(segment: Segment, cfg: dict, output_path: Path) -> None:
    width, height = cfg["width"], cfg["height"]
    code_bg = _hex_to_rgb(cfg["code_bg_color"])
    accent = _hex_to_rgb(cfg["accent_color"])
    light_text = _hex_to_rgb(cfg["light_text_color"])
    image = Image.new("RGB", (width, height), code_bg)
    draw = ImageDraw.Draw(image)

    for index, color in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        x = 40 + index * 32
        draw.ellipse([x, 30, x + 16, 46], fill=color)

    title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
    body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
    code_font = _get_font(cfg["font_family_mono"], cfg["font_size_code"])

    y = 80
    if segment.title:
        draw.text((60, y), segment.title, font=title_font, fill=accent)
        y += cfg["font_size_title"] + 50

    description = _extract_non_code_text(segment.text)
    description = _remove_prefix_title(description, segment.title)
    for line in _wrap_text(description, body_font, width - 120)[:3]:
        if line:
            draw.text((60, y), line, font=body_font, fill=light_text)
            y += cfg["font_size_body"] + 18
    if description:
        y += 26

    code = _extract_code_from_text(segment.text)
    for line in code.splitlines()[:16]:
        if y > height - 70:
            break
        draw.text((80, y), line.rstrip(), font=code_font, fill=light_text)
        y += cfg["font_size_code"] + 14

    image.save(output_path)


def _render_list_page(segment: Segment, cfg: dict, output_path: Path) -> None:
    width, height = cfg["width"], cfg["height"]
    bg = _hex_to_rgb(cfg["bg_color"])
    accent = _hex_to_rgb(cfg["accent_color"])
    text_color = _hex_to_rgb(cfg["text_color"])
    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, width, 8], fill=accent)

    title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
    body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
    y = 80
    if segment.title:
        y += _draw_centered_text(draw, segment.title, title_font, text_color, y, width)
        y += 80

    items = [
        line.strip().lstrip("*-• ").strip()
        for line in _body_without_title(segment).splitlines()
        if line.strip()
    ]
    left = max(80, width // 5)
    for item in items:
        if y > height - 90:
            break
        draw.ellipse([left - 34, y + 12, left - 18, y + 28], fill=accent)
        for line in _wrap_text(item, body_font, width - left - 90):
            draw.text((left, y), line, font=body_font, fill=text_color)
            y += cfg["font_size_body"] + 18
        y += 12

    image.save(output_path)


def _draw_soft_gradient(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    bg: tuple[int, int, int],
    accent: tuple[int, int, int],
) -> None:
    for y in range(height):
        ratio = y / max(height - 1, 1)
        blend = ratio * 0.22
        color = tuple(int(bg[channel] * (1 - blend) + accent[channel] * blend) for channel in range(3))
        draw.line([(0, y), (width, y)], fill=color)


def _draw_centered_text(draw, text: str, font, fill, y: int, width: int) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(((width - text_width) // 2, y), text, font=font, fill=fill)
    return text_height


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            candidate = current + char
            if _text_width(candidate, font) > max_width and current:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def _text_width(text: str, font) -> int:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _body_without_title(segment: Segment) -> str:
    return _remove_prefix_title(segment.text, segment.title)


def _remove_prefix_title(text: str, title: str) -> str:
    if title and text.startswith(title):
        return text[len(title) :].strip()
    return text.strip()


def _extract_code_from_text(text: str) -> str:
    code_lines: list[str] = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
    if code_lines:
        return "\n".join(code_lines)
    return text


def _extract_non_code_text(text: str) -> str:
    lines: list[str] = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            lines.append(line)
    return "\n".join(lines).strip()
