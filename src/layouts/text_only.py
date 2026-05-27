from pathlib import Path

from PIL import Image, ImageDraw

from src.layouts.base import (
    BaseLayout,
    _body_without_title,
    _draw_centered_text,
    _get_font,
    _hex_to_rgb,
    _wrap_text,
    draw_progress_bar,
)
from src.parser import Segment
from src.syntax_highlighter import highlight_code as _highlight_code


class TextOnlyLayout(BaseLayout):
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"segment_{segment.index:04d}.png"
        width, height = cfg["width"], cfg["height"]

        if segment.type in {"code_block", "mermaid"}:
            return self._render_code_content(segment, cfg, output_path, width, height)
        if segment.type == "title_slide":
            return self._render_title_slide(segment, cfg, output_path, width, height)

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
        if segment.type == "list":
            self._draw_list(draw, body, body_font, text_color, accent, width, height, y)
        else:
            for line in _wrap_text(body, body_font, width - 200):
                if y > height - 90:
                    break
                if not line:
                    y += 28
                    continue
                y += _draw_centered_text(draw, line, body_font, text_color, y, width) + 18

        self._draw_progress(draw, width, height, segment, accent)
        image.save(output_path)
        return str(output_path)

    def _render_title_slide(self, segment, cfg, output_path, width, height):
        bg = _hex_to_rgb(cfg["bg_color"])
        accent = _hex_to_rgb(cfg["accent_color"])
        text_color = _hex_to_rgb(cfg["text_color"])
        image = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(image)
        for y in range(height):
            ratio = y / max(height - 1, 1)
            blend = ratio * 0.22
            color = tuple(int(bg[channel] * (1 - blend) + accent[channel] * blend) for channel in range(3))
            draw.line([(0, y), (width, y)], fill=color)

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
        title = segment.title or segment.text.splitlines()[0]
        body_lines = [
            line.strip()
            for line in segment.text.splitlines()
            if line.strip() and line.strip() != title
        ]

        y = height // 3
        for line in _wrap_text(title, title_font, width - 160)[:3]:
            y += _draw_centered_text(draw, line, title_font, text_color, y, width) + 18

        y += 30
        for line in body_lines[:3]:
            y += _draw_centered_text(draw, line, body_font, text_color, y, width) + 14

        draw.rectangle([0, height - 8, width, height], fill=accent)
        self._draw_progress(draw, width, height, segment, accent)
        image.save(output_path)
        return str(output_path)

    def _render_code_content(self, segment, cfg, output_path, width, height):
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

        description = _remove_prefix_title(_extract_non_code_text(segment.text), segment.title)
        for line in _wrap_text(description, body_font, width - 120)[:3]:
            if line:
                draw.text((60, y), line, font=body_font, fill=light_text)
                y += cfg["font_size_body"] + 18
        if description:
            y += 26

        language = _extract_code_language(segment.text)
        code = _extract_code_from_text(segment.text)
        highlighted = _highlight_code(code, language)
        for line_tokens in highlighted[:16]:
            if y > height - 70:
                break
            x = 80
            for color_hex, text in line_tokens:
                color = _hex_to_rgb(color_hex)
                draw.text((x, y), text, font=code_font, fill=color)
                bbox = draw.textbbox((0, 0), text, font=code_font)
                x += bbox[2] - bbox[0]
            y += cfg["font_size_code"] + 14

        self._draw_progress(draw, width, height, segment, accent)
        image.save(output_path)
        return str(output_path)

    def _draw_list(self, draw, body, font, text_color, accent, width, height, y):
        left = max(80, width // 5)
        for item in [line.strip().lstrip("*-• ").strip() for line in body.splitlines() if line.strip()]:
            if y > height - 90:
                break
            draw.ellipse([left - 34, y + 12, left - 18, y + 28], fill=accent)
            for line in _wrap_text(item, font, width - left - 90):
                draw.text((left, y), line, font=font, fill=text_color)
                y += 50
            y += 12

    def _draw_progress(self, draw, width, height, segment, accent):
        durations = [1.0] * (segment.index + 1)
        draw_progress_bar(
            draw,
            width,
            height,
            segment.index,
            segment.index + 1,
            durations,
            accent,
        )


def _extract_code_from_text(text: str) -> str:
    code_lines = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
    return "\n".join(code_lines) if code_lines else text


def _extract_code_language(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") and stripped != "```":
            return stripped[3:].strip() or "text"
    return "text"


def _extract_non_code_text(text: str) -> str:
    lines = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            lines.append(line)
    return "\n".join(lines).strip()


def _remove_prefix_title(text: str, title: str) -> str:
    if title and text.startswith(title):
        return text[len(title) :].strip()
    return text.strip()
