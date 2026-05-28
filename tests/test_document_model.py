from src.document_model import build_document_model


def test_build_document_model_groups_blocks_under_headings():
    md = (
        "# Demo\n\n"
        "Intro paragraph.\n\n"
        "## Install\n\n"
        "Run this command:\n\n"
        "```shell\n"
        "brew install python\n"
        "```\n\n"
        "- Easy syntax\n"
        "- Rich library\n"
    )

    model = build_document_model(md)

    assert model.title == "Demo"
    assert [section.heading for section in model.sections] == ["Demo", "Install"]
    assert model.sections[0].blocks[0].kind == "paragraph"
    assert model.sections[1].blocks[1].kind == "code"
    assert model.sections[1].blocks[1].language == "shell"
    assert model.sections[1].blocks[2].kind == "list"
    assert model.sections[1].blocks[2].list_items == ["Easy syntax", "Rich library"]


def test_mermaid_block_is_preserved_as_mermaid_kind():
    md = "## Flow\n\n```mermaid\ngraph LR\n  A --> B\n```"

    model = build_document_model(md)

    block = model.sections[0].blocks[0]
    assert block.kind == "mermaid"
    assert "graph LR" in block.text
    assert block.language == "mermaid"


def test_annotations_reach_matching_section_and_block():
    md = (
        '<!-- {"voice": "zh-CN-YunxiNeural", "layout": "image-right"} -->\n'
        "# Demo\n\n"
        "Content."
    )

    model = build_document_model(md)

    assert model.sections[0].annotations["voice"] == "zh-CN-YunxiNeural"
    assert model.sections[0].blocks[0].annotations["layout"] == "image-right"


def test_no_heading_document_gets_content_section():
    model = build_document_model("Just content without a heading.")

    assert model.title == ""
    assert len(model.sections) == 1
    assert model.sections[0].heading == ""
    assert model.sections[0].blocks[0].kind == "paragraph"


def test_duplicate_headings_and_repeated_text_match_later_segments_monotonically():
    md = (
        "# Repeat\n\n"
        "Same content.\n\n"
        "# Repeat\n\n"
        "Same content.\n"
    )

    model = build_document_model(md)

    assert [section.source_segment_index for section in model.sections] == [0, 1]
    assert [section.blocks[0].source_segment_index for section in model.sections] == [0, 1]


def test_unannotated_document_has_empty_annotations():
    model = build_document_model("# Demo\n\nContent.")

    assert model.sections[0].annotations == {}
    assert model.sections[0].blocks[0].annotations == {}


def test_code_fence_info_uses_first_token_as_language():
    md = "```python linenums\nprint('hello')\n```"

    model = build_document_model(md)

    assert model.sections[0].blocks[0].kind == "code"
    assert model.sections[0].blocks[0].language == "python"


def test_mermaid_fence_info_with_extra_tokens_stays_mermaid():
    md = "```mermaid something\ngraph LR\n  A --> B\n```"

    model = build_document_model(md)

    assert model.sections[0].blocks[0].kind == "mermaid"
    assert model.sections[0].blocks[0].language == "mermaid"
