from pathlib import Path

from PIL import Image, ImageDraw

from src.image_loader import load_image
from src.layouts.base import (
    BaseLayout,
    _body_without_title,
    _draw_centered_text,
    _fit_image,
    _get_font,
    _hex_to_rgb,
    _wrap_text,
)
from src.parser import Segment


class ImageBelowLayout(BaseLayout):
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

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
        y = 80
        if segment.title:
            y += _draw_centered_text(draw, segment.title, title_font, text_color, y, width)
            y += 50

        body = _body_without_title(segment)
        for line in _wrap_text(body, body_font, width - 200)[:4]:
            if not line:
                y += 20
                continue
            y += _draw_centered_text(draw, line, body_font, text_color, y, width) + 14

        image_top = y + 30
        image_max_height = height - image_top - 20
        if segment.image_path and image_max_height > 100:
            try:
                source = load_image(segment.image_path)
                fitted = _fit_image(source, width - 120, image_max_height)
                image.paste(
                    fitted,
                    ((width - fitted.width) // 2, image_top + (image_max_height - fitted.height) // 2),
                )
            except Exception:
                pass

        image.save(output_path)
        return str(output_path)
