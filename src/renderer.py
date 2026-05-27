from pathlib import Path

from src.image_provider import resolve_image
from src.layouts import LayoutFactory
from src.layouts.base import _hex_to_rgb
from src.parser import Segment


def render_segment(segment: Segment, config: dict, cache_dir: str) -> str:
    render_config = config["render"]

    if segment.image_path or segment.layout in {"image-right", "image-below", "image-full"}:
        resolved = resolve_image(segment, config, Path(cache_dir))
        if resolved:
            segment.image_path = resolved
        elif segment.layout != "text-only":
            segment.layout = "text-only"

    layout = LayoutFactory.create(segment.layout)
    return layout.render(segment, render_config, Path(cache_dir))
