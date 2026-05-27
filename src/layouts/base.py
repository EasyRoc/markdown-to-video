from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.parser import Segment


CJK_SAMPLE = "中文测试"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.strip().lstrip("#")
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


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    fill: tuple[int, int, int],
    y: int,
    width: int,
) -> int:
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


def _body_without_title(segment: Segment) -> str:
    text = segment.text
    if segment.title and text.startswith(segment.title):
        text = text[len(segment.title) :].strip()
    return text


def draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    current_index: int,
    total_segments: int,
    segment_durations: list[float],
    accent_color: tuple[int, int, int],
) -> None:
    bar_height = 6
    y = height - bar_height
    durations = segment_durations or [1.0] * max(total_segments, 1)
    total_duration = sum(durations) or 1.0

    x = 0
    for index, duration in enumerate(durations):
        segment_width = int((duration / total_duration) * width)
        if index <= current_index:
            draw.rectangle([x, y, x + segment_width, height], fill=accent_color)
        x += segment_width

    x = 0
    for index, duration in enumerate(durations):
        segment_width = int((duration / total_duration) * width)
        if index > 0:
            draw.line([(x, y), (x, height)], fill=(0, 0, 0), width=1)
        x += segment_width


def _fit_image(image: Image.Image, max_width: int, max_height: int, allow_upscale: bool = False) -> Image.Image:
    width, height = image.size
    scale = min(max_width / width, max_height / height)
    if not allow_upscale:
        scale = min(scale, 1.0)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size, Image.LANCZOS)


def _text_width(text: str, font) -> int:
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def _font_has_distinct_cjk_glyphs(font) -> bool:
    glyphs = {_glyph_bytes(font, char) for char in CJK_SAMPLE}
    return len(glyphs) == len(CJK_SAMPLE)


def _glyph_bytes(font, char: str) -> bytes:
    image = Image.new("L", (96, 96), 0)
    draw = ImageDraw.Draw(image)
    draw.text((12, 12), char, font=font, fill=255)
    return image.tobytes()


class BaseLayout(ABC):
    @abstractmethod
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        ...
