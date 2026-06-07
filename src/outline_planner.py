from __future__ import annotations

from dataclasses import dataclass, field
from src.llm_client import LLMClient

STAGE1_SYSTEM_PROMPT = """\
You are an educational content planner. Analyze the following markdown article and create a teaching outline.

Output STRICT JSON (no markdown code block markers):
{
  "title": "Video title (engaging, accurately summarizes the content)",
  "sections": [
    {
      "heading": "Section heading (preserve original structure)",
      "key_points": ["Key point 1", "Key point 2", "Key point 3"],
      "svg_types": ["flowchart"],
      "svg_intent": "What this diagram should show (describe in the article's language)"
    }
  ]
}

Rules:
- Preserve the article's section structure, but merge overly short sections
- key_points: 2-5 items per section, concise
- svg_types values: flowchart, timeline, comparison, architecture, none
- svg_intent: describe the core message the SVG should convey (in the article's language)
- Only suggest SVGs when visualization enhances understanding (flows, architectures, comparisons)
- Pure concept explanations and text-only content should use "none"
- Output in the same language as the article"""


@dataclass
class OutlineSection:
    heading: str
    key_points: list[str] = field(default_factory=list)
    svg_types: list[str] = field(default_factory=list)
    svg_intent: str = ""

    def has_svg(self) -> bool:
        return bool(self.svg_types) and "none" not in self.svg_types


@dataclass
class Outline:
    title: str
    sections: list[OutlineSection] = field(default_factory=list)


class OutlinePlanner:
    def __init__(self, client: LLMClient):
        self._client = client

    async def plan(self, text: str) -> Outline:
        messages = [
            {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]
        data = await self._client.chat_with_retry(messages)
        return _parse_outline(data)


def _parse_outline(data: dict) -> Outline:
    sections = []
    for s in data.get("sections", []):
        sections.append(OutlineSection(
            heading=s.get("heading", ""),
            key_points=s.get("key_points", []),
            svg_types=s.get("svg_types", ["none"]),
            svg_intent=s.get("svg_intent", ""),
        ))
    return Outline(
        title=data.get("title", "Video"),
        sections=sections,
    )
