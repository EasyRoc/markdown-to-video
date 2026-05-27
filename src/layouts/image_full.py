from pathlib import Path

from PIL import Image, ImageDraw

from src.layouts.base import BaseLayout, _draw_centered_text, _get_font, _hex_to_rgb
from src.parser import Segment


class ImageFullLayout(BaseLayout):
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"segment_{segment.index:04d}.png"
        width, height = cfg["width"], cfg["height"]

        background = self._load_background(segment, cfg, width, height)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 100))
        background = Image.alpha_composite(background.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(background)

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
        light_text = _hex_to_rgb(cfg["light_text_color"])

        y = height // 3
        if segment.title:
            for line in segment.title.splitlines():
                y += _draw_centered_text(draw, line, title_font, light_text, y, width) + 18

        body_lines = [
            line.strip()
            for line in segment.text.splitlines()
            if line.strip() and line.strip() != segment.title
        ]
        y += 30
        for line in body_lines[:4]:
            y += _draw_centered_text(draw, line, body_font, light_text, y, width) + 12

        background.save(output_path)
        return str(output_path)

    def _load_background(self, segment: Segment, cfg: dict, width: int, height: int) -> Image.Image:
        if segment.image_path:
            try:
                return Image.open(segment.image_path).convert("RGB").resize(
                    (width, height),
                    Image.LANCZOS,
                )
            except Exception:
                pass
        return Image.new("RGB", (width, height), _hex_to_rgb(cfg["bg_color"]))
