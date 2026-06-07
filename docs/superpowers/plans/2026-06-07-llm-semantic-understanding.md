# LLM 语义理解重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 DeepSeek LLM 替代规则引擎，实现文章语义分析 + 总结 + SVG 图解 + 视频讲解生成。

**Architecture:** 两阶段 LLM 流水线：Stage 1 全文分析生成教学大纲，Stage 2 逐节展开生成讲解文案和 SVG 代码。LLM 输出映射到现有 Storyboard → Segment → 渲染/合成链路。LLM 调用失败时降级到 RulesTeachingPlanner。

**Tech Stack:** DeepSeek API (OpenAI 兼容), cairosvg, PIL, edge-tts, ffmpeg

---

### Task 1: Segment 增加 svg_code 字段 + renderer 处理

**Files:**
- Modify: `src/parser.py:15-34`
- Modify: `src/renderer.py:9-31`

- [ ] **Step 1: 在 Segment dataclass 增加 svg_code 字段**

`src/parser.py` 中 Segment 新增一行：

```python
@dataclass
class Segment:
    index: int
    title: str
    level: int
    type: str
    text: str
    duration: float = 0
    voice: str | None = None
    speed: str | None = None
    pitch: str | None = None
    image_path: str | None = None
    layout: str = "text-only"
    pause_before: float = 0.0
    pause_after: float = 0.0
    highlight: str | None = None
    bgm: str | None = None
    bgm_volume: float = 0.15
    transition: str = "none"
    table_data: list[list[str]] | None = None
    svg_code: str | None = None  # 新增
```

- [ ] **Step 2: 在 renderer.py 处理 svg_code，渲染 SVG 到图片**

在 `render_segment` 函数中，mermaid 处理之后、image resolution 之前插入 svg_code 处理：

```python
def render_segment(segment: Segment, config: dict, cache_dir: str) -> str:
    render_config = config["render"]
    cache_path = Path(cache_dir)

    if segment.type == "mermaid":
        from src.mermaid_renderer import render_mermaid

        mermaid_output = cache_path / f"mermaid_{segment.index:04d}.png"
        rendered = render_mermaid(_extract_code_from_text(segment.text), str(mermaid_output))
        if rendered:
            segment.image_path = rendered
            segment.layout = "image-below"

    if segment.svg_code:  # 新增
        from src.svg_renderer import render_svg_to_png

        svg_output = cache_path / f"svg_{segment.index:04d}.png"
        try:
            render_svg_to_png(segment.svg_code, str(svg_output))
            segment.image_path = str(svg_output)
            segment.layout = "image-below"
        except Exception:
            segment.svg_code = None  # 渲染失败，降级为 text-only

    if segment.image_path or segment.layout in {"image-right", "image-below", "image-full"}:
        resolved = resolve_image(segment, config, cache_path)
        if resolved:
            segment.image_path = resolved
        elif segment.layout != "text-only":
            segment.layout = "text-only"

    layout = LayoutFactory.create(segment.layout)
    return layout.render(segment, render_config, cache_path)
```

- [ ] **Step 3: 运行现有测试确认未破坏**

```bash
python -m pytest tests/ -x -q
```

- [ ] **Step 4: Commit**

```bash
git add src/parser.py src/renderer.py
git commit -m "feat: add svg_code field to Segment and renderer support"
```

---

### Task 2: 创建 LLM 客户端

**Files:**
- Create: `src/llm_client.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_llm_client.py
import json
import pytest
from unittest.mock import AsyncMock, patch
from src.llm_client import LLMClient


class TestLLMClient:
    def test_builds_messages_correctly(self):
        client = LLMClient({
            "llm": {
                "api_key": "sk-test",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
            }
        })
        assert client.model == "deepseek-chat"
        assert client.base_url == "https://api.deepseek.com"

    @pytest.mark.asyncio
    async def test_chat_returns_parsed_json(self):
        client = LLMClient({
            "llm": {
                "api_key": "sk-test",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
            }
        })
        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"title": "test", "sections": []}'
                }
            }]
        }
        with patch.object(client._client.chat.completions, "create",
                          AsyncMock(return_value=_mock_openai_response(mock_response))):
            result = await client.chat([
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Say hi."},
            ])
            assert result == {"title": "test", "sections": []}

    @pytest.mark.asyncio
    async def test_retries_on_json_parse_failure(self):
        client = LLMClient({
            "llm": {
                "api_key": "sk-test",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
            }
        })
        bad_response = {
            "choices": [{"message": {"content": "not json{{{["}}]}
        }
        good_response = {
            "choices": [{"message": {"content": '{"ok": true}'}}]
        }
        mock_create = AsyncMock(side_effect=[
            _mock_openai_response(bad_response),
            _mock_openai_response(good_response),
        ])
        with patch.object(client._client.chat.completions, "create", mock_create):
            result = await client.chat_with_retry([
                {"role": "user", "content": "test"},
            ])
            assert result == {"ok": True}
            assert mock_create.call_count == 2


def _mock_openai_response(data: dict):
    """构建模拟的 OpenAI 响应对象"""
    class MockMessage:
        content = data["choices"][0]["message"]["content"]
    class MockChoice:
        message = MockMessage()
    class MockResponse:
        choices = [MockChoice()]
    return MockResponse()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_llm_client.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 llm_client.py**

```python
# src/llm_client.py
from __future__ import annotations

import json
import re

from openai import AsyncOpenAI


class LLMError(Exception):
    """LLM 调用失败时抛出。"""


class LLMClient:
    def __init__(self, config: dict):
        llm_config = config.get("llm", {})
        self.model = llm_config.get("model", "deepseek-chat")
        self.base_url = llm_config.get("base_url", "https://api.deepseek.com")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 4096)
        self.timeout = llm_config.get("timeout_seconds", 60)
        self._client = AsyncOpenAI(
            api_key=llm_config.get("api_key", ""),
            base_url=self.base_url,
            timeout=self.timeout,
        )

    async def chat(self, messages: list[dict]) -> dict:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        content = response.choices[0].message.content or ""
        return _parse_json(content)

    async def chat_with_retry(self, messages: list[dict], max_retries: int = 2) -> dict:
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                return await self.chat(messages)
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                if attempt < max_retries:
                    messages.append({
                        "role": "user",
                        "content": (
                            "Your previous response was not valid JSON. "
                            f"Error: {e}. "
                            "Please output ONLY valid JSON this time."
                        ),
                    })
        raise LLMError(f"LLM failed to return valid JSON after {max_retries + 1} attempts: {last_error}")


def _parse_json(content: str) -> dict:
    """从 LLM 响应中提取 JSON。先尝试直接解析，失败后尝试提取 markdown code block 中的 JSON。"""
    text = content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1).strip())
    raise ValueError(f"Cannot parse JSON from: {text[:200]}...")
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_llm_client.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm_client.py tests/test_llm_client.py
git commit -m "feat: add LLM client with DeepSeek API support and JSON retry"
```

---

### Task 3: 创建 SVG 渲染器

**Files:**
- Create: `src/svg_renderer.py`
- Test: `tests/test_svg_renderer.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_svg_renderer.py
import pytest
from pathlib import Path
from PIL import Image
from src.svg_renderer import render_svg_to_png, inject_cjk_font


class TestInjectCJKFont:
    def test_adds_font_to_svg_tag(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"></svg>'
        result = inject_cjk_font(svg)
        assert 'font-family="PingFang SC' in result

    def test_replaces_existing_font_family(self):
        svg = '<svg font-family="Arial" viewBox="0 0 100 100"><text>hello</text></svg>'
        result = inject_cjk_font(svg)
        assert "Arial" not in result
        assert "PingFang SC" in result


class TestRenderSvgToPng:
    def test_renders_simple_svg(self, tmp_path):
        svg_code = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
            <rect width="200" height="100" fill="#4A90D9"/>
            <text x="100" y="55" text-anchor="middle" fill="white" font-size="16">Test</text>
        </svg>'''
        output = tmp_path / "test.png"
        render_svg_to_png(svg_code, str(output))
        assert output.exists()
        img = Image.open(output)
        assert img.size == (200, 100)

    def test_raises_on_broken_svg(self, tmp_path):
        output = tmp_path / "broken.png"
        with pytest.raises(Exception):
            render_svg_to_png("not svg at all <<<", str(output))
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_svg_renderer.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 svg_renderer.py**

```python
# src/svg_renderer.py
from __future__ import annotations

import re

from PIL import Image
from io import BytesIO

CJK_FONT_FAMILY = (
    "PingFang SC, Hiragino Sans GB, STHeiti, Microsoft YaHei, "
    "Noto Sans CJK SC, Arial Unicode MS, sans-serif"
)


def render_svg_to_png(svg_code: str, output_path: str) -> None:
    """将 SVG 代码字符串渲染为 PNG 文件。"""
    import cairosvg
    svg_with_fonts = inject_cjk_font(svg_code)
    png_data = cairosvg.svg2png(bytestring=svg_with_fonts.encode("utf-8"))
    img = Image.open(BytesIO(png_data)).convert("RGB")
    img.save(output_path, "PNG")


def render_svg_to_image(svg_code: str) -> Image.Image:
    """将 SVG 代码字符串渲染为 PIL Image（内存）。"""
    import cairosvg
    svg_with_fonts = inject_cjk_font(svg_code)
    png_data = cairosvg.svg2png(bytestring=svg_with_fonts.encode("utf-8"))
    return Image.open(BytesIO(png_data)).convert("RGB")


def inject_cjk_font(svg_text: str) -> str:
    """在 SVG 中注入 CJK 字体 fallback。"""
    replacement = f'font-family="{CJK_FONT_FAMILY}"'
    if re.search(r'font-family="[^"]*"', svg_text):
        svg_text = re.sub(r'font-family="[^"]*"', replacement, svg_text)
    else:
        svg_text = re.sub(r"<svg\b", f"<svg {replacement}", svg_text, count=1)
    svg_text = re.sub(
        r"font-family\s*:\s*[^;\"']+",
        f"font-family: {CJK_FONT_FAMILY}",
        svg_text,
    )
    return svg_text
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_svg_renderer.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/svg_renderer.py tests/test_svg_renderer.py
git commit -m "feat: add SVG code to PNG renderer with CJK font injection"
```

---

### Task 4: 创建 Outline Planner（Stage 1）

**Files:**
- Create: `src/outline_planner.py`
- Test: `tests/test_outline_planner.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_outline_planner.py
import pytest
from unittest.mock import AsyncMock

from src.outline_planner import OutlinePlanner, Outline, OutlineSection


class TestOutlinePlanner:
    @pytest.mark.asyncio
    async def test_plan_parses_llm_response(self):
        mock_client = AsyncMock()
        mock_client.chat_with_retry.return_value = {
            "title": "Python 异步编程",
            "sections": [
                {
                    "heading": "什么是协程",
                    "key_points": ["协程是可暂停的函数", "使用 async/await 关键字"],
                    "svg_types": ["flowchart"],
                    "svg_intent": "展示协程的执行流程",
                },
                {
                    "heading": "事件循环",
                    "key_points": ["事件循环调度协程"],
                    "svg_types": ["none"],
                    "svg_intent": "",
                },
            ],
        }
        planner = OutlinePlanner(mock_client)
        outline = await planner.plan("# Python 异步编程\n\n协程...")

        assert outline.title == "Python 异步编程"
        assert len(outline.sections) == 2
        assert outline.sections[0].heading == "什么是协程"
        assert outline.sections[0].svg_types == ["flowchart"]
        assert outline.sections[1].svg_types == ["none"]

    @pytest.mark.asyncio
    async def test_plan_empty_response_returns_default(self):
        mock_client = AsyncMock()
        mock_client.chat_with_retry.return_value = {
            "title": "文档",
            "sections": [],
        }
        planner = OutlinePlanner(mock_client)
        outline = await planner.plan("No structure here.")
        assert outline.title == "文档"
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_outline_planner.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 outline_planner.py**

```python
# src/outline_planner.py
from __future__ import annotations

from dataclasses import dataclass, field
from src.llm_client import LLMClient

STAGE1_SYSTEM_PROMPT = """\
你是一个教学大纲设计专家。分析下面的 Markdown 文章，设计一个视频教学大纲。

输出严格的 JSON 格式（不要带 markdown 代码块标记）：
{
  "title": "视频标题（吸引人、准确概括内容）",
  "sections": [
    {
      "heading": "本节标题（保留原文层级结构）",
      "key_points": ["核心要点1", "核心要点2", "核心要点3"],
      "svg_types": ["flowchart"],
      "svg_intent": "这张图要展示什么（中文描述）"
    }
  ]
}

规则：
- 保留原文的章节结构，但可以合并过短的节
- key_points 每节 2-5 条，简明扼要
- svg_types 取值：flowchart（流程图）、timeline（时间线）、comparison（对比图）、architecture（架构图）、none（不需要图）
- svg_intent 用中文描述 SVG 要传达的核心信息
- 只在视觉化能增强理解时建议 SVG（流程图、架构关系、对比等）
- 纯概念讲解、纯文字内容标记为 none"""


@dataclass
class OutlineSection:
    heading: str
    key_points: list[str] = field(default_factory=list)
    svg_types: list[str] = field(default_factory=list)
    svg_intent: str = ""

    def has_svg(self) -> bool:
        return bool(self.svg_types) and self.svg_types != ["none"]


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
        title=data.get("title", "视频讲解"),
        sections=sections,
    )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_outline_planner.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/outline_planner.py tests/test_outline_planner.py
git commit -m "feat: add Stage 1 outline planner with LLM semantic analysis"
```

---

### Task 5: 创建 Scene Generator（Stage 2）

**Files:**
- Create: `src/scene_generator.py`
- Test: `tests/test_scene_generator.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_scene_generator.py
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
                "narration": "协程是一种可以在执行过程中暂停和恢复的函数。",
                "svg_code": "",
                "duration_hint": 5.0,
                "layout": "text-only",
            },
            {
                "kind": "diagram",
                "narration": "从这张图可以看到，协程通过事件循环进行调度。",
                "svg_code": "<svg viewBox=\"0 0 800 400\"><rect/></svg>",
                "duration_hint": 8.0,
                "layout": "image-below",
            },
            {
                "kind": "summary",
                "narration": "总结一下，协程的核心优势是轻量级和高效调度。",
                "svg_code": "",
                "duration_hint": 4.0,
                "layout": "text-only",
            },
        ]
        generator = SceneGenerator(mock_client)
        section = OutlineSection(
            heading="什么是协程",
            key_points=["协程是可暂停的函数"],
            svg_types=["flowchart"],
            svg_intent="展示协程的执行流程",
        )
        scenes = await generator.generate(
            section=section,
            section_text="协程（Coroutine）是一种计算机程序组件...",
            full_text="# Python 异步编程\n\n协程...",
        )

        assert len(scenes) == 3
        assert scenes[0].kind == "concept"
        assert scenes[0].narration.startswith("协程是")
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
                "narration": "这个概念很简单。",
                "svg_code": "",
                "duration_hint": 4.0,
                "layout": "text-only",
            },
        ]
        generator = SceneGenerator(mock_client)
        section = OutlineSection(
            heading="简介",
            key_points=["简单的概念"],
            svg_types=["none"],
            svg_intent="",
        )
        scenes = await generator.generate(section, "简介内容...", "全文...")
        assert len(scenes) == 1
        assert scenes[0].svg_code == ""


class TestLLMScene:
    def test_to_dict(self):
        scene = LLMScene(
            kind="diagram",
            narration="讲解文案",
            svg_code="<svg></svg>",
            duration_hint=10.0,
            layout="image-below",
        )
        d = scene.to_dict()
        assert d["kind"] == "diagram"
        assert d["narration"] == "讲解文案"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_scene_generator.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 scene_generator.py**

```python
# src/scene_generator.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.llm_client import LLMClient
from src.outline_planner import OutlineSection

STAGE2_SYSTEM_PROMPT = """\
你是一个教学视频编导和 SVG 设计师。根据给定的章节大纲和原文，生成视频分镜脚本。

输出严格的 JSON 数组（不要带 markdown 代码块标记）：
[
  {
    "kind": "concept",
    "narration": "自然口语化讲解文案（中文）",
    "svg_code": "",
    "duration_hint": 6.0,
    "layout": "text-only"
  },
  {
    "kind": "diagram",
    "narration": "配合 SVG 图的讲解文案",
    "svg_code": "<svg viewBox=\\"0 0 800 500\\" xmlns=\\"http://www.w3.org/2000/svg\\">...</svg>",
    "duration_hint": 10.0,
    "layout": "image-below"
  },
  {
    "kind": "summary",
    "narration": "本节小结文案",
    "svg_code": "",
    "duration_hint": 4.0,
    "layout": "text-only"
  }
]

规则：
- 每个 section 生成 2-4 个场景：至少一个 concept + 一个 summary
- 如果大纲要求 SVG，且原文有流程/架构/关系型内容，生成 diagram 场景
- narration 用自然口语、适合 TTS 朗读，不要书面语
- SVG 代码必须完整可渲染：使用 viewBox，字体用 sans-serif，颜色清晰有对比
- SVG 设计原则：简洁、重点突出、颜色不超过 4 种
- duration_hint 估算：中文每字约 0.2 秒（即 narration 字数 / 5）"""


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

        user_prompt = f"""章节大纲：
{section_json}

本章节原文：
{section_text}

全文上下文（仅供参考，帮助理解整体结构）：
{full_text[:2000]}"""

        messages = [
            {"role": "system", "content": STAGE2_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        data = await self._client.chat_with_retry(messages)
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_scene_generator.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/scene_generator.py tests/test_scene_generator.py
git commit -m "feat: add Stage 2 scene generator with SVG+script output"
```

---

### Task 6: 创建 LLMTeachingPipeline + 更新 scene_adapter

**Files:**
- Modify: `src/teaching_pipeline.py`
- Modify: `src/scene_adapter.py`
- Test: `tests/test_llm_teaching_pipeline.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_llm_teaching_pipeline.py
import pytest
from unittest.mock import AsyncMock, patch

from src.teaching_pipeline import build_teaching_assets
from src.teaching_models import TeachingScript


class TestLLMTeachingPipeline:
    @pytest.mark.asyncio
    async def test_llm_pipeline_produces_teaching_assets(self):
        """LLM pipeline should produce valid TeachingAssets."""
        mock_outline = {
            "title": "测试文章",
            "sections": [
                {
                    "heading": "第一节",
                    "key_points": ["要点1"],
                    "svg_types": ["flowchart"],
                    "svg_intent": "展示流程",
                }
            ],
        }
        mock_scenes = [
            {
                "kind": "concept",
                "narration": "这是一个概念的讲解。",
                "svg_code": "",
                "duration_hint": 5.0,
                "layout": "text-only",
            },
            {
                "kind": "diagram",
                "narration": "请看这张流程图。",
                "svg_code": "<svg viewBox=\"0 0 800 400\"><rect width=\"800\" height=\"400\" fill=\"#f0f0f0\"/></svg>",
                "duration_hint": 8.0,
                "layout": "image-below",
            },
            {
                "kind": "summary",
                "narration": "本节的总结。",
                "svg_code": "",
                "duration_hint": 4.0,
                "layout": "text-only",
            },
        ]

        with patch("src.llm_client.LLMClient.chat_with_retry") as mock_chat:
            mock_chat.side_effect = [mock_outline, mock_scenes]

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
                "# 测试文章\n\n这是测试内容。",
                config,
            )
            assert assets is not None
            assert len(assets.segments) > 0

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_rules(self):
        """When LLM fails, fall back to RulesTeachingPlanner."""
        with patch("src.llm_client.LLMClient.chat_with_retry",
                   side_effect=Exception("API error")):
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
                "# 测试\n\n内容段落。\n\n## 第二节\n\n更多内容。",
                config,
            )
            assert assets.script.planner == "rules"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_llm_teaching_pipeline.py -v
```
Expected: FAIL

- [ ] **Step 3: 修改 scene_adapter.py 支持 svg visual type**

```python
# 在 _segment_type 函数中增加 svg 类型处理
def _segment_type(scene: Scene) -> str:
    if scene.kind == "title":
        return "title_slide"
    if scene.visual.type == "code":
        return "code_block"
    if scene.visual.type == "mermaid":
        return "mermaid"
    if scene.visual.type == "svg":  # 新增
        return "section"  # svg 作为普通 section 渲染，通过 svg_code 字段传递
    if scene.visual.type == "table":
        return "table"
    return "section"


# 在 _scene_to_segment 中处理 svg visual type
def _scene_to_segment(index: int, scene: Scene) -> Segment:
    # ... 现有代码 ...
    
    if visual.type == "svg":  # 新增
        segment.svg_code = visual.payload or None
        segment.layout = visual.payload and "image-below" or "text-only"
    
    if visual.type == "table":
        # ... 现有代码 ...
```

完整的 `_scene_to_segment` 修改后：

```python
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
    if visual.type == "svg":
        segment.svg_code = visual.payload or None
        if visual.payload:
            segment.layout = "image-below"
    if visual.type == "table":
        segment.layout = "table"
        segment.image_path = None
        segment.table_data = json.loads(visual.payload or "[]")
    return segment
```

- [ ] **Step 4: 修改 teaching_pipeline.py 增加 LLM 路径**

```python
# src/teaching_pipeline.py 新增 LLM 路径
from dataclasses import dataclass
from pathlib import Path

from src.document_model import build_document_model
from src.scene_adapter import storyboard_to_segments
from src.storyboard import build_storyboard
from src.storyboard_io import write_teaching_artifacts
from src.teaching_models import (
    DocumentModel,
    Scene,
    ScriptSection,
    Storyboard,
    TeachingScript,
    Timeline,
    VisualInstruction,
)
from src.teaching_planner import create_teaching_planner
from src.timeline import build_timeline


@dataclass
class TeachingAssets:
    document: DocumentModel
    script: TeachingScript
    storyboard: Storyboard
    timeline: Timeline
    segments: list


def build_teaching_assets(
    text: str,
    config: dict,
    source_dir: str | Path | None = None,
) -> TeachingAssets:
    planner = (config.get("teaching_director", {}).get("planner") or "rules")
    if planner == "llm":
        return _build_with_llm(text, config, source_dir)
    return _build_with_rules(text, config, source_dir)


def _build_with_rules(
    text: str,
    config: dict,
    source_dir: str | Path | None = None,
) -> TeachingAssets:
    document = build_document_model(text, source_dir=source_dir)
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


def _build_with_llm(
    text: str,
    config: dict,
    source_dir: str | Path | None = None,
) -> TeachingAssets:
    import asyncio
    from src.llm_client import LLMClient, LLMError
    from src.outline_planner import OutlinePlanner
    from src.scene_generator import SceneGenerator

    document = build_document_model(text, source_dir=source_dir)

    try:
        client = LLMClient(config)
        outline_planner = OutlinePlanner(client)
        scene_generator = SceneGenerator(client)

        outline = asyncio.run(outline_planner.plan(text))
        all_scenes: list[Scene] = []
        counter = 1

        if outline.title:
            all_scenes.append(Scene(
                id=f"scene-{counter:03d}",
                kind="title",
                source_section=outline.title,
                source_block_index=-1,
                narration=outline.title,
                visual=VisualInstruction("text", outline.title, outline.title),
                duration_hint=3.0,
                annotations={},
            ))
            counter += 1

        section_texts = _extract_section_texts(document, outline)

        for i, section in enumerate(outline.sections):
            section_text = section_texts[i] if i < len(section_texts) else section.heading
            try:
                llm_scenes = asyncio.run(
                    scene_generator.generate(section, section_text, text)
                )
            except LLMError:
                llm_scenes = []

            for ls in llm_scenes:
                visual_type = "svg" if ls.svg_code else "text"
                visual_payload = ls.svg_code or ls.narration
                all_scenes.append(Scene(
                    id=f"scene-{counter:03d}",
                    kind=ls.kind,
                    source_section=section.heading,
                    source_block_index=-1,
                    narration=ls.narration,
                    visual=VisualInstruction(
                        visual_type,
                        section.heading,
                        visual_payload,
                    ),
                    duration_hint=ls.duration_hint,
                    annotations={},
                ))
                counter += 1

        script = TeachingScript(
            title=outline.title,
            planner="llm",
            source_hash=document.source_hash,
        )
        storyboard = Storyboard(
            title=outline.title,
            planner="llm",
            source_hash=document.source_hash,
            scenes=all_scenes,
        )
        timeline = build_timeline(storyboard)
        segments = storyboard_to_segments(storyboard)
        return TeachingAssets(
            document=document,
            script=script,
            storyboard=storyboard,
            timeline=timeline,
            segments=segments,
        )

    except Exception:
        return _build_with_rules(text, config, source_dir)


def _extract_section_texts(document: DocumentModel, outline) -> list[str]:
    """尝试从 DocumentModel 中提取与 outline sections 对应的原文内容。"""
    result = []
    for ol_sec in outline.sections:
        # 匹配 document section by heading
        matched = ""
        for doc_sec in document.sections:
            if doc_sec.heading == ol_sec.heading or ol_sec.heading in doc_sec.heading:
                matched = "\n\n".join(
                    b.text for b in doc_sec.blocks if b.text.strip()
                )
                break
        if not matched:
            matched = ol_sec.heading
        result.append(matched)
    return result


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

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_llm_teaching_pipeline.py -v
```
Expected: PASS

- [ ] **Step 6: 运行全部测试确认未破坏**

```bash
python -m pytest tests/ -x -q
```

- [ ] **Step 7: Commit**

```bash
git add src/teaching_pipeline.py src/scene_adapter.py tests/test_llm_teaching_pipeline.py
git commit -m "feat: add LLM teaching pipeline with fallback to rules planner"
```

---

### Task 7: 更新配置和 CLI

**Files:**
- Modify: `config.yaml`
- Modify: `main.py`

- [ ] **Step 1: 在 config.yaml 增加 llm 配置段**

```yaml
# 在 config.yaml 末尾新增
llm:
  api_key: ""
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com"
  temperature: 0.7
  max_tokens: 4096
  timeout_seconds: 60
```

同时修改 `teaching_director` 部分，将 planner 改为 `llm`：

```yaml
teaching_director:
  enabled: false
  planner: "llm"
  cache_dir: "./cache"
  max_scenes_per_section: 6
  code_focus:
    enabled: true
    max_focus_lines: 4
  diagrams:
    enabled: true
    prefer_mermaid: true
  llm:
    enabled: true
    provider: "deepseek"
    model: "deepseek-chat"
    timeout_seconds: 60
```

- [ ] **Step 2: 在 main.py 增加 --llm flag**

在 `main.py` 的 argparse 部分新增：

```python
parser.add_argument(
    "--llm",
    action="store_true",
    help="Use LLM-powered semantic analysis (requires llm.api_key in config)",
)
```

在 `args.v3` 之后的逻辑中增加 llm 处理：

```python
if args.v3:
    config["teaching_director"]["planner"] = "llm" if args.llm else "rules"
    assets = build_teaching_assets(text, config, source_dir=md_path.parent)
    segments = assets.segments
```

完整修改后的关键部分：

```python
if args.v3:
    if args.llm:
        config["teaching_director"]["planner"] = "llm"
    assets = build_teaching_assets(text, config, source_dir=md_path.parent)
    segments = assets.segments
```

- [ ] **Step 3: 运行现有测试确认兼容**

```bash
python -m pytest tests/ -x -q
```

- [ ] **Step 4: Commit**

```bash
git add config.yaml main.py
git commit -m "feat: add --llm CLI flag and DeepSeek config section"
```

---

### Task 8: 集成测试 + 端到端校验

**Files:**
- Modify: `tests/test_llm_teaching_pipeline.py` (追加)

- [ ] **Step 1: 增加端到端集成测试（dry-run 模式）**

```python
# 追加到 tests/test_llm_teaching_pipeline.py
class TestLLMPipelineIntegration:
    """使用真实 API 的集成测试。需要设置 DEEPSEEK_API_KEY 环境变量。"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_pipeline_with_real_api(self):
        """端到端测试：从 markdown 到 TeachingAssets。"""
        import os
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
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
# Python 协程入门

## 什么是协程

协程（Coroutine）是一种可以在执行过程中暂停和恢复的函数。
与普通函数不同，协程可以在等待 I/O 操作时让出控制权。

### 核心概念

- 协程使用 async/await 关键字定义
- 协程通过事件循环调度
- 协程比线程更轻量

## 如何使用协程

首先导入 asyncio 模块，然后定义异步函数：

```python
import asyncio

async def fetch_data(url):
    await asyncio.sleep(1)
    return f"Data from {url}"
```

### 并发执行

使用 asyncio.gather 可以并发执行多个协程。
"""

        from src.teaching_pipeline import build_teaching_assets

        assets = build_teaching_assets(markdown, config)
        assert assets.script.planner == "llm"
        assert len(assets.segments) > 0

        # 检查是否有 SVG 场景
        svg_scenes = [
            s for s in assets.storyboard.scenes
            if s.visual.type == "svg"
        ]
        print(f"SVG scenes: {len(svg_scenes)}")
        for scene in svg_scenes:
            assert scene.visual.payload
            assert "<svg" in scene.visual.payload
```

- [ ] **Step 2: 运行 dry-run 模式验证输出**

```bash
python main.py tests/fixtures/sample.md --v3 --llm --dry-run
```

- [ ] **Step 3: 运行完整流水线生成视频（如有 API key）**

```bash
python main.py tests/fixtures/sample.md --v3 --llm
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_llm_teaching_pipeline.py
git commit -m "test: add integration test for LLM pipeline"
```

---

### 完成检查清单

- [ ] Task 1: Segment svg_code + renderer
- [ ] Task 2: LLM 客户端
- [ ] Task 3: SVG 渲染器
- [ ] Task 4: Outline Planner
- [ ] Task 5: Scene Generator
- [ ] Task 6: LLMTeachingPipeline + scene_adapter
- [ ] Task 7: 配置 + CLI
- [ ] Task 8: 集成测试
