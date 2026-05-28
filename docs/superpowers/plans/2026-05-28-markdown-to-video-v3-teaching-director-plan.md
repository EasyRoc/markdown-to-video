# Markdown to Video V3 Teaching Director Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an opt-in V3 teaching director that expands Markdown into a teaching script, storyboard, timeline, and renderable segments before reusing the existing V2 media pipeline.

**Architecture:** V3 adds a planning layer above the existing parser, renderer, TTS, and composer. The default rules planner works offline and converts structured Markdown into teaching scenes for objectives, concepts, diagrams, code overview, code focus, and summaries. The CLI exposes this through `--v3`, while the non-V3 path remains unchanged.

**Tech Stack:** Python 3.13, dataclasses, mistune AST, existing edge-tts/Pillow/ffmpeg pipeline, pytest.

---

## File Structure

New files:

```text
src/teaching_models.py       # Shared dataclasses and JSON serialization helpers
src/document_model.py        # Markdown -> DocumentModel adapter
src/teaching_planner.py      # RulesTeachingPlanner and planner selection
src/storyboard.py            # TeachingScript -> Storyboard scene expansion
src/timeline.py              # Storyboard -> Timeline timing and subtitles
src/storyboard_io.py         # Source hashing and JSON artifact writes
src/scene_adapter.py         # Storyboard scenes -> existing Segment objects
src/teaching_pipeline.py     # V3 orchestration used by CLI and tests

tests/test_teaching_models.py
tests/test_document_model.py
tests/test_teaching_planner.py
tests/test_storyboard.py
tests/test_timeline.py
tests/test_scene_adapter.py
tests/test_teaching_pipeline.py
```

Modified files:

```text
main.py                     # Add --v3 branch and reuse existing media loop
src/config.py               # Add teaching_director defaults
config.yaml                 # Document default V3 config values
tests/test_config.py        # Assert V3 config section exists
tests/test_main.py          # Add CLI V3 dry-run coverage
tests/test_integration.py   # Add V3 dry-run fixture coverage
README.md                   # Add short V3 usage and artifact notes
```

The implementation should keep these boundaries:

1. `teaching_models.py` contains data only. It should not import `parser`, `renderer`, TTS, or filesystem-heavy modules.
2. `document_model.py` can import `mistune`, `src.parser.parse_markdown`, and `src.annotations.strip_annotation_comments`.
3. `scene_adapter.py` is the only V3 module that constructs `src.parser.Segment`.
4. `teaching_pipeline.py` orchestrates V3 data flow, but does not call ffmpeg directly.
5. `main.py` chooses V2 or V3, then reuses the existing audio/render/compose loop.

---

### Task 1: Shared Teaching Models

**Files:**
- Create: `src/teaching_models.py`
- Create: `tests/test_teaching_models.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_teaching_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_teaching_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.teaching_models'`.

- [ ] **Step 3: Implement the models**

Create `src/teaching_models.py`:

```python
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
class ScriptSection(JsonModel):
    heading: str
    objective: str
    key_points: list[str] = field(default_factory=list)
    narration_blocks: list[str] = field(default_factory=list)
    code_explanations: list[CodeExplanation] = field(default_factory=list)
    diagram_candidates: list[DiagramCandidate] = field(default_factory=list)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_teaching_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/teaching_models.py tests/test_teaching_models.py
git commit -m "feat(v3): add teaching data models"
```

---

### Task 2: Markdown Document Model Adapter

**Files:**
- Create: `src/document_model.py`
- Create: `tests/test_document_model.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_document_model.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_document_model.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.document_model'`.

- [ ] **Step 3: Implement the adapter**

Create `src/document_model.py`:

```python
import hashlib
from typing import Any

import mistune

from src.annotations import strip_annotation_comments
from src.parser import Segment, parse_markdown
from src.teaching_models import DocumentBlock, DocumentModel, DocumentSection


def build_document_model(text: str) -> DocumentModel:
    clean_text = strip_annotation_comments(text)
    ast = mistune.create_markdown(renderer="ast")(clean_text)
    segments = parse_markdown(text, max_chars_per_segment=0)

    model = DocumentModel(
        title="",
        source_hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
    )
    current: DocumentSection | None = None

    for node in ast:
        node_type = node["type"]
        if node_type == "heading":
            heading = _extract_text(node).strip()
            level = node.get("attrs", {}).get("level", 0)
            segment = _find_segment_for_heading(heading, segments)
            annotations = _segment_annotations(segment)
            if level == 1 and not model.title:
                model.title = heading
            current = DocumentSection(
                heading=heading,
                level=level,
                source_segment_index=segment.index if segment else -1,
                annotations=annotations,
            )
            model.sections.append(current)
            continue

        block = _block_from_node(node, segments)
        if block is None:
            continue
        if current is None:
            current = DocumentSection(heading="", level=0)
            model.sections.append(current)
        if block.source_segment_index >= 0 and not current.annotations:
            segment = segments[block.source_segment_index]
            current.annotations = _segment_annotations(segment)
            current.source_segment_index = segment.index
        current.blocks.append(block)

    return model


def _block_from_node(node: dict[str, Any], segments: list[Segment]) -> DocumentBlock | None:
    node_type = node["type"]
    if node_type == "paragraph":
        text = _extract_text(node).strip()
        return _make_block("paragraph", text, segments)
    if node_type == "block_code":
        language = node.get("attrs", {}).get("info", "").strip()
        raw = node.get("raw", "").rstrip()
        kind = "mermaid" if language.lower() == "mermaid" else "code"
        return _make_block(kind, raw, segments, language=language)
    if node_type == "list":
        items = _extract_list_items(node)
        text = "\n".join(f"* {item}" for item in items)
        block = _make_block("list", text, segments)
        block.list_items = items
        return block
    if node_type == "block_quote":
        return _make_block("quote", _extract_text(node).strip(), segments)
    return None


def _make_block(
    kind: str,
    text: str,
    segments: list[Segment],
    language: str = "",
) -> DocumentBlock:
    segment = _find_segment_containing(text, segments)
    return DocumentBlock(
        kind=kind,
        text=text,
        language=language,
        source_segment_index=segment.index if segment else -1,
        annotations=_segment_annotations(segment),
    )


def _find_segment_for_heading(heading: str, segments: list[Segment]) -> Segment | None:
    for segment in segments:
        if segment.title == heading:
            return segment
    return None


def _find_segment_containing(text: str, segments: list[Segment]) -> Segment | None:
    if not text:
        return None
    needle = text.strip().splitlines()[0].strip()
    for segment in segments:
        if needle and needle in segment.text:
            return segment
    return None


def _segment_annotations(segment: Segment | None) -> dict:
    if segment is None:
        return {}
    values = {
        "voice": segment.voice,
        "speed": segment.speed,
        "pitch": segment.pitch,
        "image": segment.image_path,
        "layout": segment.layout,
        "pause_before": segment.pause_before,
        "pause_after": segment.pause_after,
        "highlight": segment.highlight,
        "bgm": segment.bgm,
        "bgm_volume": segment.bgm_volume,
        "transition": segment.transition,
    }
    return {
        key: value
        for key, value in values.items()
        if value not in (None, "", "text-only", 0.0, "none")
    }


def _extract_text(node: dict[str, Any]) -> str:
    if "raw" in node and "children" not in node:
        return node.get("raw", "")
    parts: list[str] = []
    for child in node.get("children", []) or []:
        child_type = child["type"]
        if child_type in {"text", "codespan"}:
            parts.append(child.get("raw", ""))
        elif child_type == "softbreak":
            parts.append(" ")
        elif child_type == "linebreak":
            parts.append("\n")
        elif child_type in {"emphasis", "strong", "link", "image", "block_text"}:
            parts.append(_extract_text(child))
        elif "children" in child:
            parts.append(_extract_text(child))
    return "".join(parts)


def _extract_list_items(node: dict[str, Any]) -> list[str]:
    items = []
    for item in node.get("children", []):
        text = " ".join(_extract_text(item).split())
        if text:
            items.append(text)
    return items
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_document_model.py tests/test_parser.py tests/test_annotations.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/document_model.py tests/test_document_model.py
git commit -m "feat(v3): build document model from markdown"
```

---

### Task 3: Rules Teaching Planner

**Files:**
- Create: `src/teaching_planner.py`
- Create: `tests/test_teaching_planner.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_teaching_planner.py`:

```python
from src.document_model import build_document_model
from src.teaching_planner import RulesTeachingPlanner, create_teaching_planner


def test_rules_planner_generates_objective_narration_and_summary():
    model = build_document_model(
        "## Event Loop\n\n"
        "The event loop receives tasks, schedules callbacks, and resumes coroutines."
    )

    script = RulesTeachingPlanner().plan(model)

    section = script.sections[0]
    assert script.planner == "rules"
    assert section.objective == "本节目标：理解 Event Loop。"
    assert "event loop" in section.narration_blocks[0].lower()
    assert section.summary == "小结：Event Loop 的核心是理解主要概念和使用场景。"


def test_rules_planner_extracts_code_explanation_focus_lines():
    model = build_document_model(
        "## Async Example\n\n"
        "```python\n"
        "async def main():\n"
        "    await fetch_data()\n"
        "    print('done')\n"
        "```"
    )

    script = RulesTeachingPlanner().plan(model)

    explanation = script.sections[0].code_explanations[0]
    assert explanation.language == "python"
    assert explanation.overview == "这段 python 代码展示了 Async Example 的一个实现片段。"
    assert explanation.focus_lines[0]["line_number"] == 1
    assert "async def main" in explanation.focus_lines[0]["code"]
    assert any("await" in item["code"] for item in explanation.focus_lines)


def test_rules_planner_creates_diagram_candidate_for_process_text():
    model = build_document_model(
        "## Pipeline\n\n"
        "输入内容会进入解析流程，然后调用渲染模块，最后输出视频。"
    )

    script = RulesTeachingPlanner().plan(model)

    candidate = script.sections[0].diagram_candidates[0]
    assert candidate.title == "Pipeline 流程图"
    assert "graph LR" in candidate.mermaid
    assert "输入" in candidate.mermaid


def test_create_teaching_planner_falls_back_to_rules_for_llm_config():
    planner = create_teaching_planner(
        {
            "teaching_director": {
                "planner": "llm",
                "llm": {"enabled": True},
            }
        }
    )

    assert isinstance(planner, RulesTeachingPlanner)


def test_rules_planner_respects_max_focus_lines_config():
    model = build_document_model(
        "## Example\n\n"
        "```python\n"
        "a = 1\n"
        "b = 2\n"
        "c = 3\n"
        "```"
    )
    planner = RulesTeachingPlanner(
        {"teaching_director": {"code_focus": {"max_focus_lines": 2}}}
    )

    script = planner.plan(model)

    assert len(script.sections[0].code_explanations[0].focus_lines) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_teaching_planner.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.teaching_planner'`.

- [ ] **Step 3: Implement the rules planner**

Create `src/teaching_planner.py`:

```python
import re

from src.teaching_models import (
    CodeExplanation,
    DiagramCandidate,
    DocumentBlock,
    DocumentModel,
    ScriptSection,
    TeachingScript,
)


PROCESS_KEYWORDS = ("流程", "步骤", "架构", "调用", "队列", "输入", "输出", "pipeline", "flow")


class RulesTeachingPlanner:
    name = "rules"

    def __init__(self, config: dict | None = None):
        director_config = (config or {}).get("teaching_director", {})
        code_focus = director_config.get("code_focus", {})
        self.max_focus_lines = int(code_focus.get("max_focus_lines", 4))

    def plan(self, document: DocumentModel) -> TeachingScript:
        script = TeachingScript(
            title=document.title,
            planner=self.name,
            source_hash=document.source_hash,
        )
        for section in document.sections:
            script.sections.append(
                ScriptSection(
                    heading=section.heading,
                    objective=_objective_for_heading(section.heading),
                    key_points=_key_points_for_blocks(section.blocks),
                    narration_blocks=_narration_for_blocks(section.blocks),
                    code_explanations=[
                        _code_explanation(
                            section.heading,
                            block,
                            max_focus_lines=self.max_focus_lines,
                        )
                        for block in section.blocks
                        if block.kind == "code"
                    ],
                    diagram_candidates=[
                        _diagram_candidate(section.heading, block)
                        for block in section.blocks
                        if _is_diagram_candidate(block)
                    ],
                    summary=_summary_for_heading(section.heading),
                    annotations=section.annotations,
                )
            )
        return script


def create_teaching_planner(config: dict | None = None) -> RulesTeachingPlanner:
    return RulesTeachingPlanner(config)


def _objective_for_heading(heading: str) -> str:
    if heading:
        return f"本节目标：理解 {heading}。"
    return "本节目标：理解当前内容的核心概念。"


def _summary_for_heading(heading: str) -> str:
    name = heading or "当前内容"
    return f"小结：{name} 的核心是理解主要概念和使用场景。"


def _key_points_for_blocks(blocks: list[DocumentBlock]) -> list[str]:
    points: list[str] = []
    for block in blocks:
        if block.kind == "list":
            points.extend(block.list_items[:4])
        elif block.kind == "paragraph":
            first = _first_sentence(block.text)
            if first:
                points.append(first)
        if len(points) >= 4:
            break
    return points[:4]


def _narration_for_blocks(blocks: list[DocumentBlock]) -> list[str]:
    narration: list[str] = []
    for block in blocks:
        if block.kind == "paragraph" and block.text.strip():
            narration.append(_spoken_text(block.text))
        elif block.kind == "list" and block.list_items:
            narration.append("这里有几个重点：" + "；".join(block.list_items) + "。")
    return narration


def _code_explanation(
    heading: str,
    block: DocumentBlock,
    max_focus_lines: int,
) -> CodeExplanation:
    language = block.language or "code"
    title = heading or "当前主题"
    lines = [line for line in block.text.splitlines() if line.strip()]
    focus_lines = []
    for index, line in enumerate(lines[:max_focus_lines], start=1):
        focus_lines.append(
            {
                "line_number": index,
                "code": line,
                "explanation": _line_explanation(line),
            }
        )
    return CodeExplanation(
        language=language,
        code=block.text,
        overview=f"这段 {language} 代码展示了 {title} 的一个实现片段。",
        focus_lines=focus_lines,
        summary="这段代码的重点是看清执行顺序、关键调用和最终输出。",
    )


def _line_explanation(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith(("async def", "def ")):
        return "这一行定义了函数入口，是后续逻辑的起点。"
    if "await " in stripped:
        return "这一行会等待异步结果，同时把控制权交还给事件循环。"
    if "return " in stripped:
        return "这一行返回计算结果。"
    if "print(" in stripped:
        return "这一行把结果输出到终端。"
    return "这一行承载当前代码片段中的一个具体步骤。"


def _is_diagram_candidate(block: DocumentBlock) -> bool:
    if block.kind not in {"paragraph", "list"}:
        return False
    lowered = block.text.lower()
    return any(keyword in lowered for keyword in PROCESS_KEYWORDS)


def _diagram_candidate(heading: str, block: DocumentBlock) -> DiagramCandidate:
    title = f"{heading or '当前内容'} 流程图"
    return DiagramCandidate(
        title=title,
        source_text=block.text,
        mermaid="graph LR\n  A[输入] --> B[处理]\n  B --> C[输出]",
    )


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[。！？.!?])\s*", text.strip())
    return parts[0].strip() if parts and parts[0].strip() else text.strip()


def _spoken_text(text: str) -> str:
    stripped = " ".join(text.split())
    if stripped.endswith(("。", ".", "！", "!", "？", "?")):
        return stripped
    return stripped + "。"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_teaching_planner.py tests/test_document_model.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/teaching_planner.py tests/test_teaching_planner.py
git commit -m "feat(v3): add rules teaching planner"
```

---

### Task 4: Storyboard Scene Generation

**Files:**
- Create: `src/storyboard.py`
- Create: `tests/test_storyboard.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_storyboard.py`:

```python
from src.document_model import build_document_model
from src.storyboard import build_storyboard
from src.teaching_planner import RulesTeachingPlanner


def _script_from_markdown(markdown: str):
    return RulesTeachingPlanner().plan(build_document_model(markdown))


def test_storyboard_adds_title_objective_concept_and_summary_scenes():
    script = _script_from_markdown(
        "# Demo\n\n"
        "Intro text.\n\n"
        "## Install\n\n"
        "Install the package before running examples."
    )

    storyboard = build_storyboard(script)

    kinds = [scene.kind for scene in storyboard.scenes]
    assert kinds[0] == "title"
    assert "objective" in kinds
    assert "concept" in kinds
    assert "summary" in kinds
    assert storyboard.scenes[0].visual.title == "Demo"


def test_storyboard_expands_code_into_overview_focus_and_summary():
    script = _script_from_markdown(
        "## Async Example\n\n"
        "```python\n"
        "async def main():\n"
        "    await fetch_data()\n"
        "    print('done')\n"
        "```"
    )

    storyboard = build_storyboard(script)

    code_kinds = [scene.kind for scene in storyboard.scenes if scene.kind.startswith("code")]
    assert code_kinds == ["code_overview", "code_focus", "code_focus", "code_focus"]
    assert storyboard.scenes[1].visual.type == "code"
    assert "async def main" in storyboard.scenes[2].visual.payload


def test_storyboard_adds_diagram_scene_for_diagram_candidate():
    script = _script_from_markdown(
        "## Pipeline\n\n"
        "输入内容会进入解析流程，然后调用渲染模块，最后输出视频。"
    )

    storyboard = build_storyboard(script)

    diagram = [scene for scene in storyboard.scenes if scene.kind == "diagram"][0]
    assert diagram.visual.type == "mermaid"
    assert "graph LR" in diagram.visual.payload


def test_storyboard_respects_max_scenes_per_section():
    script = _script_from_markdown(
        "## Long Code\n\n"
        "```python\n"
        "a = 1\n"
        "b = 2\n"
        "c = 3\n"
        "d = 4\n"
        "e = 5\n"
        "```"
    )

    storyboard = build_storyboard(
        script,
        {"teaching_director": {"max_scenes_per_section": 3}},
    )

    section_scenes = [scene for scene in storyboard.scenes if scene.source_section == "Long Code"]
    assert len(section_scenes) == 3


def test_storyboard_can_disable_diagrams_and_code_focus():
    script = _script_from_markdown(
        "## Pipeline\n\n"
        "输入内容会进入解析流程，然后调用渲染模块，最后输出视频。\n\n"
        "```python\n"
        "a = 1\n"
        "b = 2\n"
        "```"
    )

    storyboard = build_storyboard(
        script,
        {
            "teaching_director": {
                "diagrams": {"enabled": False},
                "code_focus": {"enabled": False},
            }
        },
    )

    kinds = [scene.kind for scene in storyboard.scenes]
    assert "diagram" not in kinds
    assert "code_focus" not in kinds
    assert "code_overview" in kinds
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_storyboard.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.storyboard'`.

- [ ] **Step 3: Implement storyboard generation**

Create `src/storyboard.py`:

```python
from src.teaching_models import (
    Scene,
    ScriptSection,
    Storyboard,
    TeachingScript,
    VisualInstruction,
)


def build_storyboard(script: TeachingScript, config: dict | None = None) -> Storyboard:
    director_config = (config or {}).get("teaching_director", {})
    max_per_section = director_config.get("max_scenes_per_section", 6)
    diagrams_enabled = director_config.get("diagrams", {}).get("enabled", True)
    code_focus_enabled = director_config.get("code_focus", {}).get("enabled", True)
    storyboard = Storyboard(
        title=script.title,
        planner=script.planner,
        source_hash=script.source_hash,
    )
    counter = 1
    if script.title:
        storyboard.scenes.append(
            _scene(
                counter,
                "title",
                script.title,
                -1,
                script.title,
                VisualInstruction("text", script.title, script.title),
                3.0,
                {},
            )
        )
        counter += 1

    for section in script.sections:
        section_scenes = _section_scenes(
            section,
            counter,
            diagrams_enabled=diagrams_enabled,
            code_focus_enabled=code_focus_enabled,
        )
        section_scenes = section_scenes[:max_per_section]
        storyboard.scenes.extend(section_scenes)
        counter += len(section_scenes)
    return storyboard


def _section_scenes(
    section: ScriptSection,
    start_counter: int,
    diagrams_enabled: bool,
    code_focus_enabled: bool,
) -> list[Scene]:
    scenes: list[Scene] = []
    counter = start_counter

    scenes.append(
        _scene(
            counter,
            "objective",
            section.heading,
            0,
            section.objective,
            VisualInstruction("callout", section.heading or "本节目标", section.objective),
            4.0,
            section.annotations,
        )
    )
    counter += 1

    for index, narration in enumerate(section.narration_blocks):
        scenes.append(
            _scene(
                counter,
                "concept",
                section.heading,
                index,
                narration,
                VisualInstruction(
                    "text",
                    section.heading or "概念讲解",
                    narration,
                    highlights=section.key_points[:2],
                ),
                _duration_hint(narration),
                section.annotations,
            )
        )
        counter += 1

    if diagrams_enabled:
        for candidate in section.diagram_candidates:
            scenes.append(
                _scene(
                    counter,
                    "diagram",
                    section.heading,
                    0,
                    f"这张图展示 {section.heading or '当前内容'} 的流程关系。",
                    VisualInstruction("mermaid", candidate.title, candidate.mermaid),
                    5.0,
                    section.annotations,
                )
            )
            counter += 1

    for explanation in section.code_explanations:
        scenes.append(
            _scene(
                counter,
                "code_overview",
                section.heading,
                0,
                explanation.overview,
                VisualInstruction(
                    "code",
                    section.heading or "代码概览",
                    explanation.code,
                    language=explanation.language,
                ),
                5.0,
                section.annotations,
            )
        )
        counter += 1
        if code_focus_enabled:
            for focus in explanation.focus_lines:
                scenes.append(
                    _scene(
                        counter,
                        "code_focus",
                        section.heading,
                        int(focus["line_number"]),
                        str(focus["explanation"]),
                        VisualInstruction(
                            "code",
                            f"第 {focus['line_number']} 行",
                            explanation.code,
                            highlights=[str(focus["code"])],
                            language=explanation.language,
                        ),
                        4.5,
                        section.annotations,
                    )
                )
                counter += 1

    if section.summary:
        scenes.append(
            _scene(
                counter,
                "summary",
                section.heading,
                0,
                section.summary,
                VisualInstruction("callout", "小结", section.summary),
                4.0,
                section.annotations,
            )
        )
    return scenes


def _scene(
    counter: int,
    kind: str,
    source_section: str,
    source_block_index: int,
    narration: str,
    visual: VisualInstruction,
    duration_hint: float,
    annotations: dict,
) -> Scene:
    return Scene(
        id=f"scene-{counter:03d}",
        kind=kind,
        source_section=source_section,
        source_block_index=source_block_index,
        narration=narration,
        visual=visual,
        duration_hint=duration_hint,
        annotations=dict(annotations),
    )


def _duration_hint(text: str) -> float:
    return max(3.0, min(10.0, len(text) / 14))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_storyboard.py tests/test_teaching_planner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/storyboard.py tests/test_storyboard.py
git commit -m "feat(v3): generate teaching storyboard scenes"
```

---

### Task 5: Timeline And JSON Artifacts

**Files:**
- Create: `src/timeline.py`
- Create: `src/storyboard_io.py`
- Create: `tests/test_timeline.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_timeline.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_timeline.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `src.timeline` or `src.storyboard_io`.

- [ ] **Step 3: Implement timeline**

Create `src/timeline.py`:

```python
from src.teaching_models import Storyboard, Timeline, TimelineScene


def build_timeline(
    storyboard: Storyboard,
    audio_durations: dict[str, float] | None = None,
) -> Timeline:
    durations = audio_durations or {}
    timeline = Timeline()
    cursor = 0.0
    for scene in storyboard.scenes:
        duration = float(durations.get(scene.id, scene.duration_hint))
        frame_path = f"cache/frames/{scene.id}.png"
        audio_path = f"cache/audio/{scene.id}.mp3"
        timeline.scenes.append(
            TimelineScene(
                scene_id=scene.id,
                start=round(cursor, 3),
                duration=round(duration, 3),
                image_path=frame_path,
                audio_path=audio_path,
                transition=scene.annotations.get("transition", "none"),
            )
        )
        timeline.subtitles.append(
            {
                "scene_id": scene.id,
                "start": round(cursor, 3),
                "end": round(cursor + duration, 3),
                "text": scene.narration,
            }
        )
        timeline.assets.append(frame_path)
        cursor += duration
    return timeline
```

- [ ] **Step 4: Implement JSON artifact writes**

Create `src/storyboard_io.py`:

```python
import hashlib
from pathlib import Path

from src.teaching_models import Storyboard, TeachingScript, Timeline


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def write_teaching_artifacts(
    cache_root: str | Path,
    script: TeachingScript,
    storyboard: Storyboard,
    timeline: Timeline,
) -> dict[str, Path]:
    root = Path(cache_root)
    identifier = storyboard.source_hash or script.source_hash or "storyboard"
    paths = {
        "script": root / "script" / f"{identifier}.json",
        "storyboard": root / "storyboard" / f"{identifier}.json",
        "timeline": root / "timeline" / f"{identifier}.json",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    paths["script"].write_text(script.to_json(), encoding="utf-8")
    paths["storyboard"].write_text(storyboard.to_json(), encoding="utf-8")
    paths["timeline"].write_text(timeline.to_json(), encoding="utf-8")
    return paths
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_timeline.py tests/test_teaching_models.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/timeline.py src/storyboard_io.py tests/test_timeline.py
git commit -m "feat(v3): add timeline and storyboard artifacts"
```

---

### Task 6: Storyboard To Segment Adapter

**Files:**
- Create: `src/scene_adapter.py`
- Create: `tests/test_scene_adapter.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scene_adapter.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_scene_adapter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.scene_adapter'`.

- [ ] **Step 3: Implement scene adapter**

Create `src/scene_adapter.py`:

```python
from src.parser import Segment
from src.teaching_models import Scene, Storyboard


def storyboard_to_segments(storyboard: Storyboard) -> list[Segment]:
    segments = []
    for index, scene in enumerate(storyboard.scenes):
        segment = _scene_to_segment(index, scene)
        segments.append(segment)
    return segments


def _scene_to_segment(index: int, scene: Scene) -> Segment:
    visual = scene.visual
    title = visual.title or scene.source_section
    segment_type = _segment_type(scene)
    text = _segment_text(scene)
    segment = Segment(
        index=index,
        title=title,
        level=1 if scene.kind == "title" else 2,
        type=segment_type,
        text=text,
        duration=scene.duration_hint,
    )
    _apply_scene_annotations(segment, scene)
    return segment


def _segment_type(scene: Scene) -> str:
    if scene.kind == "title":
        return "title_slide"
    if scene.visual.type == "code":
        return "code_block"
    if scene.visual.type == "mermaid":
        return "mermaid"
    return "section"


def _segment_text(scene: Scene) -> str:
    visual = scene.visual
    if scene.kind == "title":
        return visual.payload or scene.narration
    if visual.type == "code":
        language = visual.language or ""
        fence = f"```{language}".rstrip()
        return f"{visual.title}\n\n{scene.narration}\n\n{fence}\n{visual.payload}\n```"
    if visual.type == "mermaid":
        return f"{visual.title}\n\n{scene.narration}\n\n```mermaid\n{visual.payload}\n```"
    return f"{visual.title}\n\n{scene.narration}\n\n{visual.payload}".strip()


def _apply_scene_annotations(segment: Segment, scene: Scene) -> None:
    annotations = dict(scene.annotations)
    if scene.visual.highlights and not annotations.get("highlight"):
        annotations["highlight"] = ", ".join(scene.visual.highlights)
    mapping = {
        "voice": "voice",
        "speed": "speed",
        "pitch": "pitch",
        "image": "image_path",
        "layout": "layout",
        "pause_before": "pause_before",
        "pause_after": "pause_after",
        "highlight": "highlight",
        "bgm": "bgm",
        "bgm_volume": "bgm_volume",
        "transition": "transition",
    }
    for key, attr in mapping.items():
        if key in annotations and annotations[key] is not None:
            setattr(segment, attr, annotations[key])
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_scene_adapter.py tests/test_tts.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/scene_adapter.py tests/test_scene_adapter.py
git commit -m "feat(v3): adapt storyboard scenes to segments"
```

---

### Task 7: V3 Pipeline Orchestration And Config

**Files:**
- Create: `src/teaching_pipeline.py`
- Create: `tests/test_teaching_pipeline.py`
- Modify: `src/config.py`
- Modify: `config.yaml`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing pipeline tests**

Create `tests/test_teaching_pipeline.py`:

```python
import json

from src.config import load_config
from src.teaching_pipeline import build_teaching_assets, dry_run_summary, write_dry_run_artifacts


def test_build_teaching_assets_expands_sample_into_storyboard_and_segments():
    markdown = (
        "# Python Tutorial\n\n"
        "Python is useful for automation.\n\n"
        "## Installation\n\n"
        "输入源码经过解析流程，最后输出视频。\n\n"
        "```shell\n"
        "brew install python\n"
        "```"
    )

    assets = build_teaching_assets(markdown, load_config())

    assert assets.document.title == "Python Tutorial"
    assert len(assets.storyboard.scenes) > len(assets.document.sections)
    assert len(assets.segments) == len(assets.storyboard.scenes)
    assert any(scene.kind == "diagram" for scene in assets.storyboard.scenes)
    assert any(segment.type == "code_block" for segment in assets.segments)


def test_dry_run_summary_lists_storyboard_scenes():
    assets = build_teaching_assets(
        "## Intro\n\nA short explanation.",
        load_config(),
    )

    summary = dry_run_summary(assets)

    assert "V3 Storyboard" in summary
    assert "Scene 001" in summary
    assert "kind=objective" in summary


def test_write_dry_run_artifacts_uses_configured_cache_dir(tmp_path):
    config = load_config(
        cli_overrides={
            "teaching_director": {
                "cache_dir": str(tmp_path),
            }
        }
    )
    assets = build_teaching_assets("## Intro\n\nContent.", config)

    paths = write_dry_run_artifacts(assets, config)

    assert paths["storyboard"].exists()
    data = json.loads(paths["storyboard"].read_text(encoding="utf-8"))
    assert data["planner"] == "rules"
```

- [ ] **Step 2: Add config tests before implementation**

Append to `tests/test_config.py`:

```python

def test_v3_teaching_director_config_exists():
    config = load_config()

    assert config["teaching_director"]["enabled"] is False
    assert config["teaching_director"]["planner"] == "rules"
    assert config["teaching_director"]["max_scenes_per_section"] == 6
    assert config["teaching_director"]["code_focus"]["enabled"] is True
    assert config["teaching_director"]["diagrams"]["enabled"] is True
    assert config["teaching_director"]["cache_dir"] == "./cache"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_teaching_pipeline.py tests/test_config.py::test_v3_teaching_director_config_exists -v
```

Expected: FAIL because `src.teaching_pipeline` and `teaching_director` config do not exist.

- [ ] **Step 4: Add config defaults**

Modify `src/config.py` by adding this key inside `DEFAULT_CONFIG`:

```python
    "teaching_director": {
        "enabled": False,
        "planner": "rules",
        "cache_dir": "./cache",
        "max_scenes_per_section": 6,
        "code_focus": {
            "enabled": True,
            "max_focus_lines": 4,
        },
        "diagrams": {
            "enabled": True,
            "prefer_mermaid": True,
        },
        "llm": {
            "enabled": False,
            "provider": "openai",
            "model": "",
            "timeout_seconds": 30,
        },
    },
```

Modify `config.yaml` by adding this top-level section:

```yaml
teaching_director:
  enabled: false
  planner: "rules"
  cache_dir: "./cache"
  max_scenes_per_section: 6
  code_focus:
    enabled: true
    max_focus_lines: 4
  diagrams:
    enabled: true
    prefer_mermaid: true
  llm:
    enabled: false
    provider: "openai"
    model: ""
    timeout_seconds: 30
```

- [ ] **Step 5: Implement pipeline orchestration**

Create `src/teaching_pipeline.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from src.document_model import build_document_model
from src.scene_adapter import storyboard_to_segments
from src.storyboard import build_storyboard
from src.storyboard_io import write_teaching_artifacts
from src.teaching_models import DocumentModel, Storyboard, TeachingScript, Timeline
from src.teaching_planner import create_teaching_planner
from src.timeline import build_timeline


@dataclass
class TeachingAssets:
    document: DocumentModel
    script: TeachingScript
    storyboard: Storyboard
    timeline: Timeline
    segments: list


def build_teaching_assets(text: str, config: dict) -> TeachingAssets:
    document = build_document_model(text)
    planner = create_teaching_planner(config)
    script = planner.plan(document)
    storyboard = build_storyboard(script, config)
    timeline = build_timeline(storyboard)
    segments = storyboard_to_segments(storyboard)
    return TeachingAssets(
        document=document,
        script=script,
        storyboard=storyboard,
        timeline=timeline,
        segments=segments,
    )


def dry_run_summary(assets: TeachingAssets) -> str:
    lines = [
        f"V3 Storyboard: title={assets.storyboard.title or '(no title)'}, "
        f"planner={assets.storyboard.planner}, scenes={len(assets.storyboard.scenes)}"
    ]
    for scene in assets.storyboard.scenes:
        title = scene.visual.title or scene.source_section or "(no title)"
        lines.append(
            f"Scene {scene.id.removeprefix('scene-')}: "
            f"kind={scene.kind}, title={title}, chars={len(scene.narration)}"
        )
    return "\n".join(lines)


def write_dry_run_artifacts(assets: TeachingAssets, config: dict) -> dict[str, Path]:
    cache_dir = config.get("teaching_director", {}).get("cache_dir", "./cache")
    return write_teaching_artifacts(
        cache_dir,
        assets.script,
        assets.storyboard,
        assets.timeline,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_teaching_pipeline.py tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/teaching_pipeline.py src/config.py config.yaml tests/test_teaching_pipeline.py tests/test_config.py
git commit -m "feat(v3): add teaching pipeline orchestration"
```

---

### Task 8: CLI V3 Dry-Run And Full Pipeline Branch

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main.py`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/test_main.py`:

```python

def test_cli_v3_dry_run_writes_storyboard_artifacts(tmp_path):
    md_file = tmp_path / "v3.md"
    cache_dir = tmp_path / "cache"
    config_file = tmp_path / "config.yaml"
    md_file.write_text(
        "# V3 Demo\n\n"
        "Intro.\n\n"
        "## Pipeline\n\n"
        "输入 Markdown 进入解析流程，最后输出视频。\n",
        encoding="utf-8",
    )
    config_file.write_text(
        "teaching_director:\n"
        f"  cache_dir: \"{cache_dir}\"\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "main.py",
            str(md_file),
            "--v3",
            "--dry-run",
            "-c",
            str(config_file),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "V3 Storyboard" in result.stdout
    assert "kind=diagram" in result.stdout
    assert list((cache_dir / "storyboard").glob("*.json"))
    assert list((cache_dir / "timeline").glob("*.json"))
```

Append to `tests/test_integration.py`:

```python

def test_v3_dry_run_on_fixture_expands_storyboard(tmp_path):
    fixture = Path("tests/fixtures/sample.md")
    cache_dir = tmp_path / "cache"
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "teaching_director:\n"
        f"  cache_dir: \"{cache_dir}\"\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "main.py",
            str(fixture),
            "--v3",
            "--dry-run",
            "-c",
            str(config_file),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "V3 Storyboard" in result.stdout
    assert "Scene" in result.stdout
    assert result.stdout.count("Scene") > 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_main.py::test_cli_v3_dry_run_writes_storyboard_artifacts tests/test_integration.py::test_v3_dry_run_on_fixture_expands_storyboard -v
```

Expected: FAIL because `main.py` does not accept `--v3`.

- [ ] **Step 3: Wire `--v3` into the CLI**

Modify `main.py` imports:

```python
from src.teaching_pipeline import (
    build_teaching_assets,
    dry_run_summary,
    write_dry_run_artifacts,
)
```

Add this parser argument after the existing `--dry-run` argument:

```python
    parser.add_argument(
        "--v3",
        action="store_true",
        help="Use the V3 teaching director before rendering",
    )
```

Replace the current segment parsing and dry-run block with:

```python
    config = load_config(args.config)
    max_chars = config["render"]["max_chars_per_segment"]
    assets = None

    if args.v3:
        assets = build_teaching_assets(text, config)
        segments = assets.segments
    else:
        segments = parse_markdown(text, max_chars_per_segment=max_chars)

    if not segments:
        print("Error: no valid content found in file", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        if args.v3:
            print(dry_run_summary(assets))
            paths = write_dry_run_artifacts(assets, config)
            print(f"Artifacts written to: {paths['storyboard'].parent.parent}")
            return
        else:
            for segment in segments:
                title = segment.title or "(no title)"
                extra = []
                if segment.voice:
                    extra.append(f"voice={segment.voice}")
                if segment.layout != "text-only":
                    extra.append(f"layout={segment.layout}")
                if segment.image_path:
                    extra.append(f"image={segment.image_path}")
                if segment.highlight:
                    extra.append(f"highlight={segment.highlight}")
                extra_text = ", " + ", ".join(extra) if extra else ""
                print(
                    f"Segment {segment.index}: "
                    f"type={segment.type}, title={title}, chars={len(segment.text)}"
                    f"{extra_text}"
                )
            return
```

The existing audio/render/compose loops below should use the selected `segments` list for both V2 and V3.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_main.py tests/test_integration.py -v
```

Expected: PASS.

- [ ] **Step 5: Run a manual V3 dry-run**

Run:

```bash
source .venv/bin/activate && python main.py tests/fixtures/sample.md --v3 --dry-run
```

Expected output contains:

```text
V3 Storyboard
Scene 001
kind=title
kind=objective
```

- [ ] **Step 6: Commit**

Run:

```bash
git add main.py tests/test_main.py tests/test_integration.py
git commit -m "feat(v3): add teaching director CLI mode"
```

---

### Task 9: Rendering Compatibility And Documentation

**Files:**
- Modify: `README.md`
- Create: `tests/test_v3_rendering_compat.py`

- [ ] **Step 1: Write compatibility tests**

Create `tests/test_v3_rendering_compat.py`:

```python
from pathlib import Path

from src.config import load_config
from src.renderer import render_segment
from src.teaching_pipeline import build_teaching_assets


def test_v3_segments_can_render_representative_frames(tmp_path):
    markdown = (
        "# Render Demo\n\n"
        "Intro paragraph.\n\n"
        "## Code\n\n"
        "```python\n"
        "def hello():\n"
        "    print('hi')\n"
        "```\n\n"
        "## Flow\n\n"
        "输入内容进入解析流程，最后输出视频。\n"
    )
    config = load_config()
    assets = build_teaching_assets(markdown, config)
    segments = [
        segment
        for segment in assets.segments
        if segment.type in {"title_slide", "section", "code_block"}
    ][:3]

    paths = [render_segment(segment, config, str(tmp_path)) for segment in segments]

    assert len(paths) == 3
    assert all(path.endswith(".png") for path in paths)
    assert all(Path(path).exists() for path in paths)
```

- [ ] **Step 2: Run compatibility test to verify current adapter behavior**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_v3_rendering_compat.py -v
```

Expected: PASS after Tasks 1 through 8.

- [ ] **Step 3: Update README usage**

Add this section after the existing usage examples in `README.md`:

````markdown
### V3 教学导演模式

V3 会先把 Markdown 转成教学讲稿、分镜和时间线，再复用现有渲染与合成流程：

```bash
python main.py my-tutorial.md --v3
python main.py my-tutorial.md --v3 --dry-run
```

`--v3 --dry-run` 会输出 storyboard 摘要，并写入这些调试文件：

- `cache/script/<source-hash>.json`
- `cache/storyboard/<source-hash>.json`
- `cache/timeline/<source-hash>.json`

默认情况下，不加 `--v3` 仍然使用原有 V2 分段渲染流程。
````

- [ ] **Step 4: Run focused docs-adjacent tests**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/test_v3_rendering_compat.py tests/test_main.py::test_cli_help -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add README.md tests/test_v3_rendering_compat.py
git commit -m "docs(v3): document teaching director mode"
```

---

### Task 10: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run the full test suite**

Run:

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

Expected: PASS.

- [ ] **Step 2: Run Python compile check**

Run:

```bash
source .venv/bin/activate && python -m compileall main.py src tests
```

Expected: command exits with code 0.

- [ ] **Step 3: Run V2 dry-run regression**

Run:

```bash
source .venv/bin/activate && python main.py tests/fixtures/sample.md --dry-run
```

Expected output contains:

```text
Segment 0
title_slide
code_block
list
```

- [ ] **Step 4: Run V3 dry-run acceptance check**

Run:

```bash
source .venv/bin/activate && python main.py tests/fixtures/sample.md --v3 --dry-run
```

Expected output contains:

```text
V3 Storyboard
Scene 001
kind=title
kind=objective
kind=code_overview
```

Also verify these files exist:

```bash
ls cache/script cache/storyboard cache/timeline
```

Expected: each directory contains at least one `.json` file.

- [ ] **Step 5: Review git status**

Run:

```bash
git status --short
```

Expected: clean working tree, or only generated cache files that are already ignored by `.gitignore`.

---

## Self-Review Notes

Spec coverage:

1. DocumentModel is implemented in Task 2.
2. TeachingScript and rules planning are implemented in Task 3.
3. Storyboard scenes are implemented in Task 4.
4. Timeline and subtitles are implemented in Task 5.
5. JSON dry-run artifacts are implemented in Tasks 5 and 7.
6. Existing V2 renderer/composer reuse is implemented through Task 6 and Task 8.
7. `--v3` opt-in CLI behavior is implemented in Task 8.
8. Backward compatibility is tested in Task 8 and Task 10.
9. LLM remains optional by config shape and rules fallback in Task 3 and Task 7.

Scope check:

This plan implements the V3 MVP only. It does not implement network LLM calls, AI image generation, new animation templates, or a full Markdown AST rewrite.
