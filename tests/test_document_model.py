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
