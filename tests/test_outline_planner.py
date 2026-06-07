import pytest
from unittest.mock import AsyncMock

from src.outline_planner import OutlinePlanner, Outline, OutlineSection


class TestOutlinePlanner:
    @pytest.mark.asyncio
    async def test_plan_parses_llm_response(self):
        mock_client = AsyncMock()
        mock_client.chat_with_retry.return_value = {
            "title": "Python Async Programming",
            "sections": [
                {
                    "heading": "What are Coroutines",
                    "key_points": ["Coroutines are pausable functions", "Use async/await"],
                    "svg_types": ["flowchart"],
                    "svg_intent": "Show coroutine execution flow",
                },
                {
                    "heading": "Event Loop",
                    "key_points": ["Event loop schedules coroutines"],
                    "svg_types": ["none"],
                    "svg_intent": "",
                },
            ],
        }
        planner = OutlinePlanner(mock_client)
        outline = await planner.plan("# Python Async\n\nCoroutines...")

        assert outline.title == "Python Async Programming"
        assert len(outline.sections) == 2
        assert outline.sections[0].heading == "What are Coroutines"
        assert outline.sections[0].svg_types == ["flowchart"]
        assert outline.sections[1].svg_types == ["none"]

    @pytest.mark.asyncio
    async def test_plan_empty_response_returns_default(self):
        mock_client = AsyncMock()
        mock_client.chat_with_retry.return_value = {
            "title": "Document",
            "sections": [],
        }
        planner = OutlinePlanner(mock_client)
        outline = await planner.plan("No structure here.")
        assert outline.title == "Document"
        assert len(outline.sections) == 0


class TestOutlineSection:
    def test_has_svg_returns_true_if_svg_requested(self):
        section = OutlineSection(
            heading="test",
            key_points=["point 1"],
            svg_types=["flowchart"],
            svg_intent="show flow",
        )
        assert section.has_svg() is True

    def test_has_svg_returns_false_for_none(self):
        section = OutlineSection(
            heading="test",
            key_points=["point 1"],
            svg_types=["none"],
            svg_intent="",
        )
        assert section.has_svg() is False
