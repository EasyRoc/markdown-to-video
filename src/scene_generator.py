from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.llm_client import LLMClient
from src.outline_planner import OutlineSection

STAGE2_SYSTEM_PROMPT = """\
You are an educational video scriptwriter and SVG designer. Given a section outline and its original text, generate video scene scripts.

Output a strict JSON array (no markdown code block markers):
[
  {
    "kind": "concept",
    "narration": "Natural spoken narration",
    "svg_code": "",
    "duration_hint": 6.0,
    "layout": "text-only"
  },
  {
    "kind": "diagram",
    "narration": "Narration that accompanies the SVG diagram",
    "svg_code": "<svg viewBox=\\"0 0 800 500\\" xmlns=\\"http://www.w3.org/2000/svg\\">...</svg>",
    "duration_hint": 10.0,
    "layout": "image-below"
  },
  {
    "kind": "summary",
    "narration": "Section summary narration",
    "svg_code": "",
    "duration_hint": 4.0,
    "layout": "text-only"
  }
]

Rules:
- Generate 2-4 scenes per section: at least one concept + one summary
- If the outline requests SVG diagrams AND the original text has flow/architecture/relationship content, generate a diagram scene
- narration: natural spoken style suitable for TTS reading, not written text
- SVG code must be complete and renderable: use viewBox, fonts as sans-serif, clear contrasting colors
- SVG design: simple, focused, no more than 4 colors
- duration_hint: roughly narration character count / 5 (Chinese: ~5 chars per second)
- Output in the same language as the article"""


@dataclass
class LLMScene:
    kind: str
    narration: str
    svg_code: str | None
    duration_hint: float
    layout: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "narration": self.narration,
            "svg_code": self.svg_code or "",
            "duration_hint": self.duration_hint,
            "layout": self.layout,
        }


class SceneGenerator:
    def __init__(self, client: LLMClient):
        self._client = client

    async def generate(
        self,
        section: OutlineSection,
        section_text: str,
        full_text: str,
    ) -> list[LLMScene]:
        section_json = json.dumps({
            "heading": section.heading,
            "key_points": section.key_points,
            "svg_types": section.svg_types,
            "svg_intent": section.svg_intent,
        }, ensure_ascii=False, indent=2)

        user_prompt = f"""Section Outline:
{section_json}

Section Original Text:
{section_text}

Full Article Context (for reference only):
{full_text[:2000]}"""

        messages = [
            {"role": "system", "content": STAGE2_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        data = await self._client.chat_with_retry(messages)
        if not isinstance(data, list):
            raise TypeError(f"Expected JSON array from LLM, got {type(data).__name__}")
        return _parse_scenes(data)


def _parse_scenes(data: list[dict]) -> list[LLMScene]:
    scenes = []
    for item in data:
        svg_code = item.get("svg_code", "") or ""
        scenes.append(LLMScene(
            kind=item.get("kind", "concept"),
            narration=item.get("narration", ""),
            svg_code=svg_code if svg_code.strip() else None,
            duration_hint=float(item.get("duration_hint", 5.0)),
            layout=item.get("layout", "text-only"),
        ))
    return scenes
