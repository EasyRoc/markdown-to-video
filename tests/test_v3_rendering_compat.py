from pathlib import Path

from src.config import load_config
from src.renderer import render_segment
from src.teaching_pipeline import build_teaching_assets


def test_v3_segments_can_render_representative_frames(tmp_path):
    markdown = (
        "# Render Demo\n\n"
        "Intro paragraph.\n\n"
        "## Code\n\n"
        "```python\n"
        "def hello():\n"
        "    print('hi')\n"
        "```\n\n"
        "## Flow\n\n"
        "输入内容进入解析流程，最后输出视频。\n"
    )
    config = load_config()
    assets = build_teaching_assets(markdown, config)
    segments = [
        segment
        for segment in assets.segments
        if segment.type in {"title_slide", "section", "code_block"}
    ][:3]

    paths = [render_segment(segment, config, str(tmp_path)) for segment in segments]

    assert len(paths) == 3
    assert all(path.endswith(".png") for path in paths)
    assert all(Path(path).exists() for path in paths)
