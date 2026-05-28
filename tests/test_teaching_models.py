import json

from src.teaching_models import (
    CodeExplanation,
    DiagramCandidate,
    DocumentBlock,
    DocumentModel,
    DocumentSection,
    Scene,
    ScriptSection,
    Storyboard,
    TeachingScript,
    Timeline,
    TimelineScene,
    VisualInstruction,
)


def test_document_model_serializes_to_dict_and_json():
    block = DocumentBlock(
        kind="code",
        text="print(1)",
        language="python",
        source_segment_index=2,
    )
    section = DocumentSection(heading="Install", level=2, blocks=[block])
    model = DocumentModel(title="Demo", sections=[section])

    data = model.to_dict()
    assert data["title"] == "Demo"
    assert data["sections"][0]["blocks"][0]["language"] == "python"

    decoded = json.loads(model.to_json())
    assert decoded["sections"][0]["blocks"][0]["text"] == "print(1)"


def test_teaching_script_serializes_nested_explanations():
    script = TeachingScript(
        title="Async Python",
        sections=[
            ScriptSection(
                heading="Event Loop",
                objective="Understand the event loop.",
                key_points=["It schedules callbacks."],
                narration_blocks=["The event loop coordinates async work."],
                code_explanations=[
                    CodeExplanation(
                        language="python",
                        code="await fetch_data()",
                        overview="This snippet waits without blocking.",
                        focus_lines=[
                            {
                                "line_number": 1,
                                "code": "await fetch_data()",
                                "explanation": "await yields control until data is ready.",
                            }
                        ],
                        summary="await lets other tasks run.",
                    )
                ],
                diagram_candidates=[
                    DiagramCandidate(
                        title="Flow",
                        source_text="输入经过事件循环输出结果",
                        mermaid="graph LR\n  A[输入] --> B[事件循环]\n  B --> C[输出]",
                    )
                ],
                summary="The loop keeps work moving.",
            )
        ],
    )

    data = script.to_dict()
    assert data["sections"][0]["code_explanations"][0]["focus_lines"][0]["line_number"] == 1
    assert "事件循环" in script.to_json()


def test_storyboard_and_timeline_serialization():
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
                narration="This is the narration.",
                visual=VisualInstruction(
                    type="text",
                    title="Intro",
                    payload="This is the narration.",
                    highlights=["narration"],
                ),
                duration_hint=3.5,
                annotations={"voice": "zh-CN-XiaoxiaoNeural"},
            )
        ],
    )
    timeline = Timeline(
        scenes=[
            TimelineScene(
                scene_id="scene-001",
                start=0.0,
                duration=3.5,
                image_path="cache/frames/scene-001.png",
                audio_path="cache/audio/scene-001.mp3",
                transition="fade",
            )
        ],
        subtitles=[
            {
                "scene_id": "scene-001",
                "start": 0.0,
                "end": 3.5,
                "text": "This is the narration.",
            }
        ],
        assets=["cache/frames/scene-001.png"],
    )

    assert storyboard.to_dict()["scenes"][0]["visual"]["type"] == "text"
    assert timeline.to_dict()["subtitles"][0]["end"] == 3.5
