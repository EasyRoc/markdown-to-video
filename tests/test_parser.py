from src.parser import parse_markdown


SIMPLE_MD = """# Hello World

Some intro text here.

## Installation

First install the package:

```
pip install something
```

## Features

- Feature one
- Feature two
- Feature three
"""


def test_parse_markdown_creates_segments():
    segments = parse_markdown(SIMPLE_MD)

    assert len(segments) >= 3


def test_first_segment_is_title_slide():
    segments = parse_markdown(SIMPLE_MD)

    assert segments[0].type == "title_slide"
    assert segments[0].title == "Hello World"
    assert segments[0].level == 1


def test_code_block_segment():
    segments = parse_markdown(SIMPLE_MD)

    code_segs = [s for s in segments if s.type == "code_block"]
    assert len(code_segs) == 1
    assert "pip install" in code_segs[0].text


def test_list_segment():
    segments = parse_markdown(SIMPLE_MD)

    list_segs = [s for s in segments if s.type == "list"]
    assert len(list_segs) == 1
    assert "Feature one" in list_segs[0].text


def test_segments_are_indexed():
    segments = parse_markdown(SIMPLE_MD)

    for i, seg in enumerate(segments):
        assert seg.index == i


def test_no_heading_markdown():
    md = "Just some text without any headings."

    segments = parse_markdown(md)

    assert len(segments) == 1
    assert segments[0].type == "section"
    assert segments[0].title == ""


def test_long_segment_is_split():
    sentences = [f"这是第{i}句话。" for i in range(20)]
    long_text = "\n\n".join(sentences)
    md = "## Long Section\n\n" + long_text

    segments = parse_markdown(md, max_chars_per_segment=50)

    assert len(segments) > 1


def test_empty_markdown():
    segments = parse_markdown("")

    assert len(segments) == 0


def test_segment_has_v2_fields():
    from src.parser import Segment

    seg = Segment(0, "Test", 1, "section", "content")

    assert seg.voice is None
    assert seg.layout == "text-only"
    assert seg.image_path is None
    assert seg.transition == "none"


def test_mermaid_code_block_gets_mermaid_type():
    md = "## Diagram\n\n```mermaid\ngraph LR\n  A --> B\n```"

    segments = parse_markdown(md)

    assert segments[0].type == "mermaid"


def test_code_block_with_language_is_code_block():
    md = "## Code\n\n```python\nprint('hello')\n```"

    segments = parse_markdown(md)

    assert segments[0].type == "code_block"


def test_parse_markdown_with_annotations_extracts_them():
    md = '<!-- {"voice": "zh-CN-YunxiNeural"} -->\n\n# Hello\n\nWorld.'

    segments = parse_markdown(md)

    assert segments[0].voice == "zh-CN-YunxiNeural"
    assert "voice" not in segments[0].text


def test_inline_image_sets_image_path_and_layout():
    md = "## Screenshot\n\nHere is the result:\n\n![Result Image](assets/screenshot.png)"

    segments = parse_markdown(md)

    assert segments[0].image_path == "assets/screenshot.png"
    assert segments[0].layout == "image-below"


def test_inline_image_alt_text_preserved_for_tts():
    md = "![Architecture Diagram](diagrams/arch.png)"

    segments = parse_markdown(md)

    assert "Architecture Diagram" in segments[0].text


def test_paragraph_without_image_unchanged():
    md = "## Section\n\nJust plain text without images."

    segments = parse_markdown(md)

    assert segments[0].image_path is None
    assert segments[0].layout == "text-only"


def test_annotation_layout_overrides_image_layout():
    md = (
        '<!-- {"layout": "image-right"} -->\n'
        "## Diagram\n\n"
        "![diagram](img/diagram.png)"
    )

    segments = parse_markdown(md)

    assert segments[0].image_path == "img/diagram.png"
    assert segments[0].layout == "image-right"
