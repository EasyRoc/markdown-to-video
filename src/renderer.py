from pathlib import Path

from src.image_provider import resolve_image
from src.layouts import LayoutFactory
from src.layouts.base import _hex_to_rgb
from src.parser import Segment


def render_segment(segment: Segment, config: dict, cache_dir: str) -> str:
    render_config = config["render"]
    cache_path = Path(cache_dir)

    if segment.type == "mermaid":
        from src.mermaid_renderer import render_mermaid

        mermaid_output = cache_path / f"mermaid_{segment.index:04d}.png"
        rendered = render_mermaid(_extract_code_from_text(segment.text), str(mermaid_output))
        if rendered:
            segment.image_path = rendered
            segment.layout = "image-below"

    if segment.image_path or segment.layout in {"image-right", "image-below", "image-full"}:
        resolved = resolve_image(segment, config, cache_path)
        if resolved:
            segment.image_path = resolved
        elif segment.layout != "text-only":
            segment.layout = "text-only"

    layout = LayoutFactory.create(segment.layout)
    return layout.render(segment, render_config, cache_path)


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
