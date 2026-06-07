# tests/test_llm_teaching_pipeline.py
from unittest.mock import AsyncMock, patch

from src.teaching_pipeline import build_teaching_assets


class TestLLMTeachingPipeline:
    def test_llm_pipeline_produces_teaching_assets(self):
        """LLM pipeline should produce valid TeachingAssets."""
        mock_outline = {
            "title": "Test Article",
            "sections": [
                {
                    "heading": "Section 1",
                    "key_points": ["Point 1"],
                    "svg_types": ["flowchart"],
                    "svg_intent": "Show the flow",
                }
            ],
        }
        mock_scenes = [
            {
                "kind": "concept",
                "narration": "This is a concept explanation.",
                "svg_code": "",
                "duration_hint": 5.0,
                "layout": "text-only",
            },
            {
                "kind": "diagram",
                "narration": "Look at this flowchart.",
                "svg_code": "<svg viewBox=\"0 0 800 400\"><rect width=\"800\" height=\"400\" fill=\"#f0f0f0\"/></svg>",
                "duration_hint": 8.0,
                "layout": "image-below",
            },
            {
                "kind": "summary",
                "narration": "Summary of this section.",
                "svg_code": "",
                "duration_hint": 4.0,
                "layout": "text-only",
            },
        ]

        with patch("src.teaching_pipeline.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.chat_with_retry.side_effect = [mock_outline, mock_scenes]
            mock_client_class.return_value = mock_client

            config = {
                "llm": {
                    "api_key": "sk-test",
                    "model": "deepseek-chat",
                    "base_url": "https://api.deepseek.com",
                },
                "teaching_director": {
                    "enabled": True,
                    "planner": "llm",
                    "max_scenes_per_section": 6,
                },
            }
            assets = build_teaching_assets(
                "# Test Article\n\nThis is test content.",
                config,
            )
            assert assets is not None
            assert len(assets.segments) > 0
            assert assets.script.planner == "llm"
            assert assets.storyboard.planner == "llm"

    def test_llm_failure_falls_back_to_rules(self):
        """When LLM fails, fall back to RulesTeachingPlanner."""
        with patch("src.teaching_pipeline.LLMClient") as mock_client_class:
            mock_client_class.side_effect = Exception("API error")

            config = {
                "llm": {
                    "api_key": "sk-test",
                    "model": "deepseek-chat",
                    "base_url": "https://api.deepseek.com",
                },
                "teaching_director": {
                    "enabled": True,
                    "planner": "llm",
                    "max_scenes_per_section": 6,
                },
            }
            assets = build_teaching_assets(
                "# Test\n\nContent paragraph.\n\n## Section 2\n\nMore content.",
                config,
            )
            assert assets.script.planner == "rules"


class TestLLMPipelineIntegration:
    """Integration tests requiring a real DeepSeek API key."""

    def test_full_pipeline_dry_run_with_real_api(self):
        """End-to-end: markdown to TeachingAssets using real DeepSeek API."""
        import os
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            import pytest
            pytest.skip("DEEPSEEK_API_KEY not set")

        config = {
            "llm": {
                "api_key": api_key,
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
            },
            "teaching_director": {
                "enabled": True,
                "planner": "llm",
                "max_scenes_per_section": 6,
            },
        }

        markdown = """\
# Python Coroutines

## What Are Coroutines

Coroutines are functions that can pause and resume execution.
Unlike regular functions, coroutines yield control during I/O operations.

### Key Concepts

- Coroutines use async/await keywords
- Coroutines are scheduled by an event loop
- Coroutines are lighter than threads

## How to Use Coroutines

First import asyncio, then define async functions:

```python
import asyncio

async def fetch_data(url):
    await asyncio.sleep(1)
    return f"Data from {url}"
```

### Concurrent Execution

Use asyncio.gather to run multiple coroutines concurrently.
"""

        assets = build_teaching_assets(markdown, config)
        assert assets.script.planner == "llm"
        assert len(assets.segments) > 0

        svg_scenes = [
            s for s in assets.storyboard.scenes
            if s.visual.type == "svg"
        ]
        for scene in svg_scenes:
            assert scene.visual.payload
            assert "<svg" in scene.visual.payload
