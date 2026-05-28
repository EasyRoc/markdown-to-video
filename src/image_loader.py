from io import BytesIO
from pathlib import Path

from PIL import Image


def load_image(path: str) -> Image.Image:
    image_path = Path(path)
    if image_path.suffix.lower() == ".svg":
        try:
            import cairosvg
        except ImportError as exc:
            raise RuntimeError("SVG images require cairosvg to render") from exc
        png_data = cairosvg.svg2png(url=str(image_path))
        return Image.open(BytesIO(png_data)).convert("RGB")

    return Image.open(image_path).convert("RGB")
