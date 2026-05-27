from pathlib import Path

from PIL import Image, ImageDraw

from src.layouts.base import (
    BaseLayout,
    _body_without_title,
    _fit_image,
    _get_font,
    _hex_to_rgb,
    _wrap_text,
)
from src.parser import Segment


class ImageRightLayout(BaseLayout):
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"segment_{segment.index:04d}.png"
        width, height = cfg["width"], cfg["height"]
        bg = _hex_to_rgb(cfg["bg_color"])
        accent = _hex_to_rgb(cfg["accent_color"])
        text_color = _hex_to_rgb(cfg["text_color"])

        image = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, width, 8], fill=accent)

        text_width = int(width * 0.58)
        image_left = text_width + 40
        image_width = width - image_left - 40
        image_top = 100
        image_height = height - 140

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        body_font = _get_font(cfg["font_family"], cfg["font_size_body"])

        y = 80
        if segment.title:
            draw.text((60, y), segment.title, font=title_font, fill=text_color)
            y += cfg["font_size_title"] + 60

        body = _body_without_title(segment)
        for line in _wrap_text(body, body_font, text_width - 80)[:12]:
            if y > height - 90:
                break
            if not line:
                y += 24
                continue
            draw.text((60, y), line, font=body_font, fill=text_color)
            y += cfg["font_size_body"] + 14

        if segment.image_path:
            try:
                source = Image.open(segment.image_path).convert("RGB")
                fitted = _fit_image(source, image_width, image_height)
                image.paste(
                    fitted,
                    (
                        image_left + (image_width - fitted.width) // 2,
                        image_top + (image_height - fitted.height) // 2,
                    ),
                )
            except Exception:
                pass

        image.save(output_path)
        return str(output_path)
