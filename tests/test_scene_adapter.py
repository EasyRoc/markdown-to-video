from src.scene_adapter import storyboard_to_segments
from src.teaching_models import Scene, Storyboard, VisualInstruction


def test_text_scene_becomes_section_segment_with_narration():
    storyboard = Storyboard(
        title="Demo",
        planner="rules",
        source_hash="abc123",
        scenes=[
            Scene(
                id="scene-001",
                kind="concept",
                source_section="Intro",
                source_block_index=0,
                narration="This is spoken.",
                visual=VisualInstruction("text", "Intro", "This is visual text."),
                duration_hint=3.0,
                annotations={"voice": "zh-CN-YunxiNeural", "highlight": "spoken"},
            )
        ],
    )

    segments = storyboard_to_segments(storyboard)

    assert len(segments) == 1
    assert segments[0].index == 0
    assert segments[0].type == "section"
    assert segments[0].title == "Intro"
    assert "This is spoken." in segments[0].text
    assert segments[0].voice == "zh-CN-YunxiNeural"
    assert segments[0].highlight == "spoken"


def test_title_scene_becomes_title_slide():
    storyboard = Storyboard(
        title="Demo",
        planner="rules",
        source_hash="abc123",
        scenes=[
            Scene(
                id="scene-001",
                kind="title",
                source_section="Demo",
                source_block_index=-1,
                narration="Demo",
                visual=VisualInstruction("text", "Demo", "Demo"),
                duration_hint=3.0,
            )
        ],
    )

    segment = storyboard_to_segments(storyboard)[0]

    assert segment.type == "title_slide"
    assert segment.text == "Demo"


def test_code_scene_becomes_code_block_segment():
    storyboard = Storyboard(
        title="Demo",
        planner="rules",
        source_hash="abc123",
        scenes=[
            Scene(
                id="scene-001",
                kind="code_focus",
                source_section="Code",
                source_block_index=1,
                narration="This line waits for data.",
                visual=VisualInstruction(
                    "code",
                    "第 2 行",
                    "async def main():\n    await fetch_data()",
                    highlights=["await fetch_data()"],
                    language="python",
                ),
                duration_hint=4.0,
            )
        ],
    )

    segment = storyboard_to_segments(storyboard)[0]

    assert segment.type == "code_block"
    assert "```python" in segment.text
    assert "This line waits for data." in segment.text
    assert segment.highlight == "await fetch_data()"


def test_mermaid_scene_becomes_mermaid_segment():
    storyboard = Storyboard(
        title="Demo",
        planner="rules",
        source_hash="abc123",
        scenes=[
            Scene(
                id="scene-001",
                kind="diagram",
                source_section="Flow",
                source_block_index=0,
                narration="This diagram shows the flow.",
                visual=VisualInstruction("mermaid", "Flow", "graph LR\n  A --> B"),
                duration_hint=5.0,
            )
        ],
    )

    segment = storyboard_to_segments(storyboard)[0]

    assert segment.type == "mermaid"
    assert "```mermaid" in segment.text
    assert "graph LR" in segment.text
