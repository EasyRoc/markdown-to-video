import subprocess
import sys


def test_v2_pipeline_with_annotations(tmp_path):
    md_file = tmp_path / "v2_test.md"
    md_file.write_text(
        '<!-- {"voice": "zh-CN-YunxiNeural", "layout": "image-right"} -->\n'
        "# V2 Test\n\n"
        "This is a V2 annotated document.\n\n"
        "## Code Section\n\n"
        "Here is the code:\n\n"
        "```python\n"
        "def hello():\n"
        '    print("Hello V2")\n'
        "```\n\n"
        "## Features\n\n"
        "- Annotation-driven rendering\n"
        "- Mixed layouts\n"
        "- Syntax highlighting\n\n"
        '<!-- {"highlight": "关键结论"} -->\n'
        "关键结论：V2 让创作者拥有导演级控制力。\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "main.py", str(md_file), "--dry-run"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "V2 Test" in result.stdout
    assert "voice=" in result.stdout or "layout=" in result.stdout
    assert "highlight=关键结论" in result.stdout


def test_v2_mermaid_detection():
    from src.parser import parse_markdown

    md = "## Diagram\n\n```mermaid\ngraph LR\n  A-->B\n```"
    segments = parse_markdown(md)
    mermaid_segments = [segment for segment in segments if segment.type == "mermaid"]

    assert len(mermaid_segments) >= 1


def test_v2_syntax_highlighting():
    from src.syntax_highlighter import highlight_code

    result = highlight_code('print("hello")', "python")

    assert len(result) > 0
    assert all(
        isinstance(token[0], str) and isinstance(token[1], str)
        for line in result
        for token in line
    )


def test_v2_layout_factory_all_types():
    from src.layouts import LayoutFactory

    for name in ("text-only", "image-right", "image-below", "image-full"):
        layout = LayoutFactory.create(name)
        assert layout is not None


def test_v2_annotation_parse_and_apply():
    from src.annotations import apply_annotations, parse_annotations
    from src.parser import Segment

    text = (
        '<!-- {"voice": "zh-CN-YunxiNeural", "layout": "image-right"} -->\n\n'
        "# Title\n\nContent."
    )
    annotations = parse_annotations(text)
    assert len(annotations) == 1

    segments = [Segment(0, "Title", 1, "title_slide", "Title\n\nContent")]
    result = apply_annotations(segments, annotations, text)

    assert result[0].voice == "zh-CN-YunxiNeural"
    assert result[0].layout == "image-right"
