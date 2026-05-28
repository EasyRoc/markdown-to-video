from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


class JsonModel:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class DocumentBlock(JsonModel):
    kind: str
    text: str
    language: str = ""
    annotations: dict[str, Any] = field(default_factory=dict)
    source_segment_index: int = -1
    list_items: list[str] = field(default_factory=list)
    table_data: list[list[str]] = field(default_factory=list)


@dataclass
class DocumentSection(JsonModel):
    heading: str
    level: int
    blocks: list[DocumentBlock] = field(default_factory=list)
    source_segment_index: int = -1
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentModel(JsonModel):
    title: str
    sections: list[DocumentSection] = field(default_factory=list)
    source_hash: str = ""


@dataclass
class CodeExplanation(JsonModel):
    language: str
    code: str
    overview: str
    focus_lines: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""


@dataclass
class DiagramCandidate(JsonModel):
    title: str
    source_text: str
    mermaid: str


@dataclass
class TableVisual(JsonModel):
    title: str
    summary: str
    table_data: list[list[str]] = field(default_factory=list)


@dataclass
class ScriptSection(JsonModel):
    heading: str
    objective: str
    key_points: list[str] = field(default_factory=list)
    narration_blocks: list[str] = field(default_factory=list)
    code_explanations: list[CodeExplanation] = field(default_factory=list)
    diagram_candidates: list[DiagramCandidate] = field(default_factory=list)
    tables: list[TableVisual] = field(default_factory=list)
    summary: str = ""
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass
class TeachingScript(JsonModel):
    title: str
    sections: list[ScriptSection] = field(default_factory=list)
    planner: str = "rules"
    source_hash: str = ""


@dataclass
class VisualInstruction(JsonModel):
    type: str
    title: str
    payload: str
    highlights: list[str] = field(default_factory=list)
    language: str = ""


@dataclass
class Scene(JsonModel):
    id: str
    kind: str
    source_section: str
    source_block_index: int
    narration: str
    visual: VisualInstruction
    duration_hint: float
    annotations: dict[str, Any] = field(default_factory=dict)


@dataclass
class Storyboard(JsonModel):
    title: str
    planner: str
    source_hash: str
    scenes: list[Scene] = field(default_factory=list)


@dataclass
class TimelineScene(JsonModel):
    scene_id: str
    start: float
    duration: float
    image_path: str
    audio_path: str
    transition: str = "none"


@dataclass
class Timeline(JsonModel):
    scenes: list[TimelineScene] = field(default_factory=list)
    subtitles: list[dict[str, Any]] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
