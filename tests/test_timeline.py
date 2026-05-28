import json

from src.storyboard_io import source_hash, write_teaching_artifacts
from src.teaching_models import (
    Scene,
    Storyboard,
    TeachingScript,
    Timeline,
    VisualInstruction,
)
from src.timeline import build_timeline


def _storyboard():
    return Storyboard(
        title="Demo",
        planner="rules",
        source_hash="abc123",
        scenes=[
            Scene(
                id="scene-001",
                kind="concept",
                source_section="Intro",
                source_block_index=0,
                narration="Short narration.",
                visual=VisualInstruction("text", "Intro", "Short narration."),
                duration_hint=2.5,
            ),
            Scene(
                id="scene-002",
                kind="summary",
                source_section="Intro",
                source_block_index=0,
                narration="Longer narration for the summary.",
                visual=VisualInstruction("callout", "Summary", "Longer narration for the summary."),
                duration_hint=4.0,
            ),
        ],
    )


def test_build_timeline_uses_audio_duration_when_available():
    timeline = build_timeline(
        _storyboard(),
        audio_durations={"scene-001": 3.25},
    )

    assert timeline.scenes[0].start == 0.0
    assert timeline.scenes[0].duration == 3.25
    assert timeline.scenes[1].start == 3.25
    assert timeline.subtitles[0]["text"] == "Short narration."


def test_build_timeline_uses_duration_hint_without_audio():
    timeline = build_timeline(_storyboard())

    assert timeline.scenes[0].duration == 2.5
    assert timeline.scenes[1].start == 2.5
    assert timeline.assets == [
        "cache/frames/scene-001.png",
        "cache/frames/scene-002.png",
    ]


def test_source_hash_is_stable():
    assert source_hash("hello") == source_hash("hello")
    assert source_hash("hello") != source_hash("world")


def test_write_teaching_artifacts_writes_valid_json(tmp_path):
    script = TeachingScript(title="Demo", source_hash="abc123")
    storyboard = _storyboard()
    timeline = build_timeline(storyboard)

    paths = write_teaching_artifacts(tmp_path, script, storyboard, timeline)

    assert paths["script"].name == "abc123.json"
    assert paths["storyboard"].parent.name == "storyboard"
    assert json.loads(paths["storyboard"].read_text(encoding="utf-8"))["title"] == "Demo"
    assert json.loads(paths["timeline"].read_text(encoding="utf-8"))["scenes"][0]["scene_id"] == "scene-001"
