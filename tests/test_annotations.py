from src.annotations import apply_annotations, parse_annotations
from src.parser import Segment


def test_parse_single_line_annotation():
    text = '<!-- {"voice": "zh-CN-YunxiNeural"} -->\n\n## Title\n\nContent.'
    results = parse_annotations(text)

    assert len(results) == 1
    line_num, ann = results[0]
    assert line_num > 0
    assert ann["voice"] == "zh-CN-YunxiNeural"


def test_parse_multi_line_annotation():
    text = '<!--\n{"voice": "zh-CN-YunxiNeural",\n "speed": "-10%"}\n-->\n\nContent.'
    results = parse_annotations(text)

    assert len(results) == 1
    _, ann = results[0]
    assert ann["speed"] == "-10%"


def test_parse_multiple_annotations():
    text = (
        '<!-- {"voice": "A"} -->\n\n## Section 1\n\nContent 1.\n\n'
        '<!-- {"voice": "B"} -->\n\n## Section 2\n\nContent 2.'
    )
    results = parse_annotations(text)

    assert len(results) == 2


def test_non_json_comment_is_ignored():
    text = "<!-- just a regular comment -->\n\n## Title\n\nContent."
    results = parse_annotations(text)

    assert len(results) == 0


def test_no_annotations_returns_empty():
    text = "# Title\n\nJust content."
    results = parse_annotations(text)

    assert len(results) == 0


def test_apply_annotations_to_segments():
    segments = [
        Segment(0, "Title", 1, "title_slide", "Title\n\nContent"),
        Segment(1, "Section", 2, "section", "Section\n\nBody"),
    ]
    annotations = [(1, {"voice": "zh-CN-YunxiNeural"})]

    result = apply_annotations(segments, annotations, text="# markdown\n\n...")

    assert result[0].voice == "zh-CN-YunxiNeural"


def test_apply_annotations_with_defaults():
    segments = [Segment(0, "T", 1, "title_slide", "T")]
    annotations = [(1, {"layout": "image-right"})]

    result = apply_annotations(segments, annotations, text="# md\n\n...")

    assert result[0].layout == "image-right"
    assert result[0].transition == "none"
