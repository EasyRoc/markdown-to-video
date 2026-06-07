import pytest
from unittest.mock import AsyncMock

from src.outline_planner import OutlineSection
from src.scene_generator import SceneGenerator, LLMScene


class TestSceneGenerator:
    @pytest.mark.asyncio
    async def test_generate_parses_llm_response(self):
        mock_client = AsyncMock()
        mock_client.chat_with_retry.return_value = [
            {
                "kind": "concept",
                "narration": "A coroutine is a function that can pause and resume.",
                "svg_code": "",
                "duration_hint": 5.0,
                "layout": "text-only",
            },
            {
                "kind": "diagram",
                "narration": "As shown in this diagram, coroutines are scheduled through the event loop.",
                "svg_code": "<svg viewBox=\"0 0 800 400\"><rect/></svg>",
                "duration_hint": 8.0,
                "layout": "image-below",
            },
            {
                "kind": "summary",
                "narration": "In summary, the key advantage of coroutines is lightweight scheduling.",
                "svg_code": "",
                "duration_hint": 4.0,
                "layout": "text-only",
            },
        ]
        generator = SceneGenerator(mock_client)
        section = OutlineSection(
            heading="What are Coroutines",
            key_points=["Coroutines are pausable functions"],
            svg_types=["flowchart"],
            svg_intent="Show coroutine execution flow",
        )
        scenes = await generator.generate(
            section=section,
            section_text="Coroutines are computer program components...",
            full_text="# Python Async\n\nCoroutines...",
        )

        assert len(scenes) == 3
        assert scenes[0].kind == "concept"
        assert scenes[0].narration.startswith("A coroutine")
        assert scenes[0].layout == "text-only"
        assert scenes[1].kind == "diagram"
        assert scenes[1].svg_code is not None
        assert "<svg" in scenes[1].svg_code
        assert scenes[2].kind == "summary"

    @pytest.mark.asyncio
    async def test_generate_handles_no_diagram_section(self):
        mock_client = AsyncMock()
        mock_client.chat_with_retry.return_value = [
            {
                "kind": "concept",
                "narration": "This concept is simple.",
                "svg_code": "",
                "duration_hint": 4.0,
                "layout": "text-only",
            },
        ]
        generator = SceneGenerator(mock_client)
        section = OutlineSection(
            heading="Introduction",
            key_points=["A simple concept"],
            svg_types=["none"],
            svg_intent="",
        )
        scenes = await generator.generate(section, "Intro content...", "Full text...")
        assert len(scenes) == 1
        assert scenes[0].svg_code is None


class TestLLMScene:
    def test_to_dict(self):
        scene = LLMScene(
            kind="diagram",
            narration="Narration text",
            svg_code="<svg></svg>",
            duration_hint=10.0,
            layout="image-below",
        )
        d = scene.to_dict()
        assert d["kind"] == "diagram"
        assert d["narration"] == "Narration text"
        assert d["svg_code"] == "<svg></svg>"
