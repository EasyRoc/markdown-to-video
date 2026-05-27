# Markdown to Video Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that converts markdown files to video with AI voiceover (edge-tts) and template-driven visuals.

**Architecture:** Sequential pipeline — parse md → generate TTS audio per segment → render visual frames → compose final .mp4 via ffmpeg. Each module is independently testable with clear input/output boundaries.

**Tech Stack:** Python 3.13, mistune (md parsing), edge-tts (TTS), Pillow (image rendering), ffmpeg subprocess (video), pyyaml (config), pytest (testing)

---

### Task 1: Project setup — dependencies, config, and directory structure

**Files:**
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `config.yaml`
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write requirements.txt**

```text
mistune>=3.1
edge-tts>=6.1
Pillow>=11.0
pyyaml>=6.0
mutagen>=1.47
pytest>=8.0
```

- [ ] **Step 2: Install dependencies**

```bash
source .venv/bin/activate && pip install -r requirements.txt
```

- [ ] **Step 3: Create default config.yaml**

```yaml
tts:
  voice: "zh-CN-XiaoxiaoNeural"
  speed: "+0%"
  pitch: "+0Hz"
  retry: 1

render:
  width: 1920
  height: 1080
  font_family: "/System/Library/Fonts/PingFang.ttc"
  font_family_mono: "/System/Library/Fonts/SFNSMono.ttf"
  font_size_title: 72
  font_size_body: 40
  font_size_code: 34
  bg_color: "#f5f5f5"
  code_bg_color: "#1e1e1e"
  accent_color: "#4A90D9"
  text_color: "#333333"
  light_text_color: "#e0e0e0"
  max_chars_per_segment: 200

video:
  fps: 30
  codec: "libx264"
  audio_codec: "aac"
  audio_bitrate: "192k"
  output_dir: "./output"
```

- [ ] **Step 4: Write failing test for config loader**

Create `tests/test_config.py`:

```python
import pytest
from src.config import load_config, DEFAULT_CONFIG


def test_default_config_has_required_keys():
    for key in ("tts", "render", "video"):
        assert key in DEFAULT_CONFIG


def test_load_config_merges_yaml(tmp_path):
    custom_yaml = tmp_path / "custom.yaml"
    custom_yaml.write_text("tts:\n  voice: \"zh-CN-YunxiNeural\"\n")

    config = load_config(str(custom_yaml))

    assert config["tts"]["voice"] == "zh-CN-YunxiNeural"
    assert config["render"]["width"] == 1920  # from defaults


def test_load_config_cli_overrides():
    cli_overrides = {"tts": {"speed": "+20%"}}
    config = load_config(cli_overrides=cli_overrides)

    assert config["tts"]["speed"] == "+20%"
    assert config["tts"]["voice"] == "zh-CN-XiaoxiaoNeural"  # unchanged
```

- [ ] **Step 5: Run test to verify it fails**

```bash
source .venv/bin/activate && python -m pytest tests/test_config.py -v
```

Expected: FAIL with "No module named 'src.config'"

- [ ] **Step 6: Implement config loader**

Create `src/__init__.py` (empty file).

Create `src/config.py`:

```python
import yaml
import os
from copy import deepcopy

DEFAULT_CONFIG = {
    "tts": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "speed": "+0%",
        "pitch": "+0Hz",
        "retry": 1,
    },
    "render": {
        "width": 1920,
        "height": 1080,
        "font_family": "/System/Library/Fonts/PingFang.ttc",
        "font_family_mono": "/System/Library/Fonts/SFNSMono.ttf",
        "font_size_title": 72,
        "font_size_body": 40,
        "font_size_code": 34,
        "bg_color": "#f5f5f5",
        "code_bg_color": "#1e1e1e",
        "accent_color": "#4A90D9",
        "text_color": "#333333",
        "light_text_color": "#e0e0e0",
        "max_chars_per_segment": 200,
    },
    "video": {
        "fps": 30,
        "codec": "libx264",
        "audio_codec": "aac",
        "audio_bitrate": "192k",
        "output_dir": "./output",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str | None = None, cli_overrides: dict | None = None) -> dict:
    config = deepcopy(DEFAULT_CONFIG)

    if config_path:
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, file_config)

    if cli_overrides:
        config = _deep_merge(config, cli_overrides)

    return config
```

- [ ] **Step 7: Run test to verify it passes**

```bash
source .venv/bin/activate && python -m pytest tests/test_config.py -v
```

Expected: 3 PASS

- [ ] **Step 8: Commit**

```bash
git add requirements.txt config.yaml src/__init__.py src/config.py tests/__init__.py tests/test_config.py
git commit -m "feat: add project setup with config loader"
```

---

### Task 2: Markdown parser — Segment dataclass and parse_markdown()

**Files:**
- Create: `src/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write failing tests for parser**

Create `tests/test_parser.py`:

```python
import pytest
from src.parser import Segment, parse_markdown


SIMPLE_MD = """# Hello World

Some intro text here.

## Installation

First install the package:

```
pip install something
```

## Features

- Feature one
- Feature two
- Feature three
"""


def test_parse_markdown_creates_segments():
    segments = parse_markdown(SIMPLE_MD)

    assert len(segments) >= 3


def test_first_segment_is_title_slide():
    segments = parse_markdown(SIMPLE_MD)

    assert segments[0].type == "title_slide"
    assert segments[0].title == "Hello World"
    assert segments[0].level == 1


def test_code_block_segment():
    segments = parse_markdown(SIMPLE_MD)

    code_segs = [s for s in segments if s.type == "code_block"]
    assert len(code_segs) == 1
    assert "pip install" in code_segs[0].text


def test_list_segment():
    segments = parse_markdown(SIMPLE_MD)

    list_segs = [s for s in segments if s.type == "list"]
    assert len(list_segs) == 1
    assert "Feature one" in list_segs[0].text


def test_segments_are_indexed():
    segments = parse_markdown(SIMPLE_MD)

    for i, seg in enumerate(segments):
        assert seg.index == i


def test_no_heading_markdown():
    md = "Just some text without any headings."

    segments = parse_markdown(md)

    assert len(segments) == 1
    assert segments[0].type == "section"
    assert segments[0].title == ""


def test_long_segment_is_split():
    sentences = ["这是第{}句话。".format(i) for i in range(20)]
    long_text = "\n\n".join(sentences)
    md = "## Long Section\n\n" + long_text

    segments = parse_markdown(md, max_chars_per_segment=50)

    assert len(segments) > 1


def test_empty_markdown():
    segments = parse_markdown("")

    assert len(segments) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_parser.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement Segment dataclass and parse_markdown()**

Create `src/parser.py`:

```python
from dataclasses import dataclass, field
import re
import mistune


@dataclass
class Segment:
    index: int
    title: str
    level: int
    type: str  # title_slide | section | code_block | list
    text: str
    duration: float = 0


def _extract_text(node: dict) -> str:
    if "children" not in node or node["children"] is None:
        return node.get("raw", "")
    parts = []
    for child in node["children"]:
        if child["type"] == "text":
            parts.append(child.get("raw", ""))
        elif child["type"] == "codespan":
            parts.append(child.get("raw", ""))
        elif child["type"] == "softbreak":
            parts.append(" ")
        elif child["type"] == "linebreak":
            parts.append("\n")
        elif child["type"] == "link":
            text = "".join(c.get("raw", "") for c in child.get("children", []))
            parts.append(text)
        elif child["type"] == "image":
            alt = ""
            for c in child.get("children", []):
                alt += c.get("raw", "")
            parts.append(alt)
        elif child["type"] == "emphasis" or child["type"] == "strong":
            for c in child.get("children", []):
                parts.append(c.get("raw", ""))
        elif "children" in child:
            parts.append(_extract_text(child))
    return "".join(parts)


def _extract_list_text(node: dict) -> str:
    lines = []
    for item in node.get("children", []):
        if item["type"] == "list_item":
            text = _extract_text(item)
            text = " ".join(text.split())
            lines.append("• " + text)
    return "\n".join(lines)


def _segment_type_from_node(node: dict) -> str:
    if node["type"] == "heading":
        level = node["attrs"]["level"]
        return "title_slide" if level == 1 else "section"
    return "section"


def parse_markdown(text: str, max_chars_per_segment: int = 200) -> list[Segment]:
    if not text.strip():
        return []

    md = mistune.create_markdown(renderer=mistune.AstRenderer())
    ast = md(text)

    segments: list[Segment] = []
    current: Segment | None = None

    for node in ast:
        node_type = node["type"]

        if node_type == "heading":
            if current is not None:
                segments.append(current)
            title = _extract_text(node)
            level = node["attrs"]["level"]
            seg_type = "title_slide" if level == 1 else "section"
            current = Segment(
                index=len(segments),
                title=title,
                level=level,
                type=seg_type,
                text=title,
            )

        elif node_type == "paragraph":
            text_content = _extract_text(node)
            if current is not None:
                current.text += "\n\n" + text_content
            else:
                current = Segment(
                    index=len(segments),
                    title="",
                    level=0,
                    type="section",
                    text=text_content,
                )

        elif node_type == "block_code":
            code_text = node.get("raw", "")
            if current is not None:
                current.text += "\n" + code_text
                current.type = "code_block"
            else:
                current = Segment(
                    index=len(segments),
                    title="",
                    level=0,
                    type="code_block",
                    text=code_text,
                )

        elif node_type == "list":
            list_text = _extract_list_text(node)
            if current is not None:
                current.text += "\n" + list_text
                current.type = "list"
            else:
                current = Segment(
                    index=len(segments),
                    title="",
                    level=0,
                    type="list",
                    text=list_text,
                )

        elif node_type == "block_quote":
            quote_text = _extract_text(node)
            if current is not None:
                current.text += "\n" + quote_text
            else:
                current = Segment(
                    index=len(segments),
                    title="",
                    level=0,
                    type="section",
                    text=quote_text,
                )

        elif node_type == "thematic_break":
            if current is not None:
                segments.append(current)
                current = None

    if current is not None:
        segments.append(current)

    segments = _split_long_segments(segments, max_chars_per_segment)

    for i, seg in enumerate(segments):
        seg.index = i

    return segments


def _split_long_segments(segments: list[Segment], max_chars: int) -> list[Segment]:
    result = []
    for seg in segments:
        if len(seg.text) <= max_chars:
            result.append(seg)
            continue

        parts = re.split(r"(?<=[。！？.!?\n])", seg.text)
        chunk = seg.title + "\n\n" if seg.title else ""
        first = True

        for part in parts:
            if len(chunk) + len(part) > max_chars and chunk.strip():
                if first and seg.type == "title_slide":
                    chunk_seg = Segment(
                        index=0, title=seg.title, level=seg.level,
                        type=seg.type, text=chunk.strip()
                    )
                else:
                    chunk_seg = Segment(
                        index=0, title=seg.title, level=seg.level,
                        type=seg.type, text=chunk.strip()
                    )
                result.append(chunk_seg)
                chunk = seg.title + "\n\n" + part if seg.title else part
                first = False
            else:
                if first:
                    chunk = part
                    first = False
                else:
                    chunk += part

        if chunk.strip():
            chunk_seg = Segment(
                index=0, title=seg.title, level=seg.level,
                type=seg.type, text=chunk.strip()
            )
            result.append(chunk_seg)

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_parser.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/parser.py tests/test_parser.py
git commit -m "feat: add markdown parser with segment splitting"
```

---

### Task 3: TTS engine — edge-tts wrapper with caching

**Files:**
- Create: `src/tts.py`
- Create: `tests/test_tts.py`

- [ ] **Step 1: Write failing tests for TTS**

Create `tests/test_tts.py`:

```python
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from src.parser import Segment
from src.tts import tts_text_for_segment, generate_audio


def test_tts_text_for_code_block():
    seg = Segment(index=0, title="安装", level=2, type="code_block",
                  text="安装\n\n```\npip install x\n```")

    text = tts_text_for_segment(seg)

    assert "pip install" not in text
    assert "安装" in text


def test_tts_text_for_section():
    seg = Segment(index=0, title="介绍", level=2, type="section",
                  text="介绍\n\n这是正文内容。")

    text = tts_text_for_segment(seg)

    assert "这是正文内容" in text


def test_tts_text_for_list():
    seg = Segment(index=0, title="功能", level=2, type="list",
                  text="功能\n• 特性一\n• 特性二")

    text = tts_text_for_segment(seg)

    assert "特性一" in text
    assert "特性二" in text


def test_audio_cache_path():
    from src.tts import audio_cache_path

    path = audio_cache_path("hello world", "./cache/audio")
    path2 = audio_cache_path("hello world", "./cache/audio")

    assert path == path2
    assert path.endswith(".mp3")
    assert "cache/audio" in path


@pytest.mark.asyncio
async def test_generate_audio_cached(tmp_path):
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()

    # Pre-create a cached file
    from src.tts import audio_cache_path
    seg = Segment(index=0, title="测试", level=1, type="title_slide",
                  text="测试标题")
    cached_path = audio_cache_path("测试标题", str(cache_dir))
    cached_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a tiny valid mp3-like file (mutagen won't parse it, so mock)
    cached_path.write_bytes(b"fake mp3 data")

    with patch("src.tts._get_mp3_duration", return_value=3.5):
        duration = await generate_audio(seg, {"tts": {"retry": 1}}, str(cache_dir))

    assert duration == 3.5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_tts.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement TTS module**

Create `src/tts.py`:

```python
import hashlib
import asyncio
from pathlib import Path
from src.parser import Segment
from mutagen.mp3 import MP3


def audio_cache_path(text: str, cache_dir: str) -> Path:
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    path = Path(cache_dir) / f"{text_hash}.mp3"
    return path


def tts_text_for_segment(segment: Segment) -> str:
    if segment.type == "code_block":
        lines = segment.text.split("\n")
        non_code_lines = []
        in_code = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if not in_code:
                non_code_lines.append(line)
        result = "\n".join(non_code_lines).strip()
        if not result:
            title = segment.title or "以下"
            return f"以下是{title}的示例代码"
        return result

    return segment.text


def _get_mp3_duration(filepath: str) -> float:
    audio = MP3(filepath)
    return audio.info.length


async def generate_audio(
    segment: Segment,
    config: dict,
    cache_dir: str = "./cache/audio",
) -> float:
    tts_config = config["tts"]
    text = tts_text_for_segment(segment)
    cache_path = audio_cache_path(text, cache_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        try:
            return _get_mp3_duration(str(cache_path))
        except Exception:
            cache_path.unlink()

    import edge_tts

    for attempt in range(tts_config.get("retry", 1) + 1):
        try:
            communicate = edge_tts.Communicate(
                text,
                tts_config["voice"],
                rate=tts_config["speed"],
                pitch=tts_config["pitch"],
            )
            await communicate.save(str(cache_path))
            return _get_mp3_duration(str(cache_path))
        except Exception:
            if attempt == tts_config.get("retry", 0):
                raise

    return 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_tts.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts.py tests/test_tts.py
git commit -m "feat: add TTS engine with edge-tts and audio caching"
```

---

### Task 4: Visual renderer — PIL-based template rendering

**Files:**
- Create: `src/renderer.py`
- Create: `tests/test_renderer.py`

- [ ] **Step 1: Write failing tests for renderer**

Create `tests/test_renderer.py`:

```python
import pytest
from pathlib import Path
from PIL import Image
from src.parser import Segment
from src.renderer import render_segment, _hex_to_rgb


def test_hex_to_rgb():
    assert _hex_to_rgb("#ff0000") == (255, 0, 0)
    assert _hex_to_rgb("#4A90D9") == (74, 144, 217)
    assert _hex_to_rgb("#1e1e1e") == (30, 30, 30)


def test_render_title_slide(tmp_path):
    seg = Segment(index=0, title="Python 入门教程", level=1,
                  type="title_slide", text="Python 入门教程\n\n作者：测试")

    config = {
        "render": {
            "width": 800,
            "height": 600,
            "font_family": "/System/Library/Fonts/PingFang.ttc",
            "font_family_mono": "/System/Library/Fonts/SFNSMono.ttf",
            "font_size_title": 48,
            "font_size_body": 28,
            "font_size_code": 24,
            "bg_color": "#f5f5f5",
            "code_bg_color": "#1e1e1e",
            "accent_color": "#4A90D9",
            "text_color": "#333333",
            "light_text_color": "#e0e0e0",
        }
    }

    path = render_segment(seg, config, str(tmp_path))

    assert path.endswith(".png")
    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_render_code_block(tmp_path):
    seg = Segment(index=1, title="示例代码", level=2,
                  type="code_block",
                  text="示例代码\n\n```\nprint('hello')\n```")

    config = {
        "render": {
            "width": 800,
            "height": 600,
            "font_family": "/System/Library/Fonts/PingFang.ttc",
            "font_family_mono": "/System/Library/Fonts/SFNSMono.ttf",
            "font_size_title": 48,
            "font_size_body": 28,
            "font_size_code": 24,
            "bg_color": "#f5f5f5",
            "code_bg_color": "#1e1e1e",
            "accent_color": "#4A90D9",
            "text_color": "#333333",
            "light_text_color": "#e0e0e0",
        }
    }

    path = render_segment(seg, config, str(tmp_path))
    img = Image.open(path)

    # Code block should have dark background
    pixels = list(img.getdata())
    dark_pixels = sum(1 for p in pixels if p[0] < 50 and p[1] < 50 and p[2] < 50)
    assert dark_pixels > len(pixels) * 0.3


def test_render_list(tmp_path):
    seg = Segment(index=2, title="功能列表", level=2,
                  type="list",
                  text="功能列表\n• 功能一\n• 功能二\n• 功能三")

    config = {
        "render": {
            "width": 800,
            "height": 600,
            "font_family": "/System/Library/Fonts/PingFang.ttc",
            "font_family_mono": "/System/Library/Fonts/SFNSMono.ttf",
            "font_size_title": 48,
            "font_size_body": 28,
            "font_size_code": 24,
            "bg_color": "#f5f5f5",
            "code_bg_color": "#1e1e1e",
            "accent_color": "#4A90D9",
            "text_color": "#333333",
            "light_text_color": "#e0e0e0",
        }
    }

    path = render_segment(seg, config, str(tmp_path))
    assert Path(path).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_renderer.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement renderer**

Create `src/renderer.py`:

```python
from pathlib import Path
import textwrap
from PIL import Image, ImageDraw, ImageFont
from src.parser import Segment


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _get_font(font_path: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(font_path, size=size, index=index)
    except Exception:
        return ImageFont.load_default()


def _draw_centered_text(
    draw: ImageDraw.Draw,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    y: int,
    width: int,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (width - text_w) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        current_line = ""
        for char in paragraph:
            test_line = current_line + char
            bbox = font.getbbox(test_line)
            if bbox[2] - bbox[0] > max_width:
                if current_line:
                    lines.append(current_line)
                current_line = char
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
    return lines


def _extract_code_from_text(text: str) -> str:
    lines = text.split("\n")
    code_lines = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
    if not code_lines:
        non_code = [l for l in lines if not l.strip().startswith("```")]
        return "\n".join(non_code)
    return "\n".join(code_lines)


def _extract_non_code_text(text: str) -> str:
    lines = text.split("\n")
    result = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            result.append(line)
    return "\n".join(result).strip()


def render_segment(segment: Segment, config: dict, cache_dir: str) -> str:
    render_cfg = config["render"]
    width = render_cfg["width"]
    height = render_cfg["height"]
    output_path = Path(cache_dir) / f"segment_{segment.index:04d}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if segment.type == "code_block":
        _render_code_page(segment, render_cfg, str(output_path))
    elif segment.type == "title_slide":
        _render_title_slide(segment, render_cfg, str(output_path))
    elif segment.type == "list":
        _render_list_page(segment, render_cfg, str(output_path))
    else:
        _render_section_page(segment, render_cfg, str(output_path))

    return str(output_path)


def _render_title_slide(segment: Segment, cfg: dict, output_path: str):
    width, height = cfg["width"], cfg["height"]
    img = Image.new("RGB", (width, height), _hex_to_rgb(cfg["bg_color"]))
    draw = ImageDraw.Draw(img)

    # Gradient background
    accent = _hex_to_rgb(cfg["accent_color"])
    for y in range(height):
        ratio = y / height
        r = int(accent[0] * 0.15 * ratio + 245 * (1 - ratio * 0.3))
        g = int(accent[1] * 0.15 * ratio + 245 * (1 - ratio * 0.3))
        b = int(accent[2] * 0.15 * ratio + 245 * (1 - ratio * 0.3))
        for x in range(width):
            img.putpixel((x, y), (r, g, b))

    title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
    body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
    text_color = _hex_to_rgb(cfg["text_color"])

    # Title
    title = segment.title or segment.text.split("\n")[0]
    _draw_centered_text(draw, title, title_font, text_color, height // 3, width)

    # Subtitle line
    lines = segment.text.split("\n")
    sub_lines = [l for l in lines if l.strip() and l.strip() != title]
    y = height // 2
    for line in sub_lines[:3]:
        _draw_centered_text(draw, line.strip(), body_font, text_color, y, width)
        y += 50

    # Accent bar at bottom
    bar_h = 6
    for y in range(height - bar_h, height):
        for x in range(width):
            img.putpixel((x, y), accent)

    img.save(output_path)


def _render_section_page(segment: Segment, cfg: dict, output_path: str):
    width, height = cfg["width"], cfg["height"]
    accent = _hex_to_rgb(cfg["accent_color"])
    bg = _hex_to_rgb(cfg["bg_color"])
    text_color = _hex_to_rgb(cfg["text_color"])

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    # Top accent bar
    for y in range(6):
        for x in range(width):
            img.putpixel((x, y), accent)

    title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
    body_font = _get_font(cfg["font_family"], cfg["font_size_body"])

    # Title
    y = 80
    if segment.title:
        _draw_centered_text(draw, segment.title, title_font, text_color, y, width)
        y += 120

    # Body text
    body_text = segment.text
    if segment.title and body_text.startswith(segment.title):
        body_text = body_text[len(segment.title):].strip()

    lines = _wrap_text(body_text, body_font, width - 200)
    y = max(y, height // 3)
    for line in lines:
        if y > height - 100:
            break
        if line == "":
            y += 30
            continue
        _draw_centered_text(draw, line, body_font, text_color, y, width)
        y += 55

    img.save(output_path)


def _render_code_page(segment: Segment, cfg: dict, output_path: str):
    width, height = cfg["width"], cfg["height"]
    code_bg = _hex_to_rgb(cfg["code_bg_color"])
    light_text = _hex_to_rgb(cfg["light_text_color"])
    accent = _hex_to_rgb(cfg["accent_color"])

    img = Image.new("RGB", (width, height), code_bg)
    draw = ImageDraw.Draw(img)

    # Window control dots
    dot_colors = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]
    for i, color in enumerate(dot_colors):
        x = 40 + i * 30
        draw.ellipse([x, 28, x + 16, 44], fill=color)

    title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
    code_font = _get_font(cfg["font_family_mono"], cfg["font_size_code"])
    body_font = _get_font(cfg["font_family"], cfg["font_size_body"])

    y = 70

    # Title bar
    if segment.title:
        draw.text((60, y), segment.title, font=title_font, fill=accent)
        y += 100

    # Description text (non-code)
    desc = _extract_non_code_text(segment.text)
    if desc:
        lines = _wrap_text(desc, body_font, width - 120)
        for line in lines[:3]:
            if not line:
                continue
            draw.text((60, y), line, font=body_font, fill=light_text)
            y += 45
        y += 30

    # Code content
    code = _extract_code_from_text(segment.text)
    if code:
        code_lines = code.split("\n")
        line_h = 42
        for line in code_lines[:15]:
            if y > height - 80:
                break
            draw.text((80, y), line.rstrip(), font=code_font, fill=light_text)
            y += line_h

    img.save(output_path)


def _render_list_page(segment: Segment, cfg: dict, output_path: str):
    width, height = cfg["width"], cfg["height"]
    accent = _hex_to_rgb(cfg["accent_color"])
    bg = _hex_to_rgb(cfg["bg_color"])
    text_color = _hex_to_rgb(cfg["text_color"])

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    # Top accent bar
    for y in range(6):
        for x in range(width):
            img.putpixel((x, y), accent)

    title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
    body_font = _get_font(cfg["font_family"], cfg["font_size_body"])

    # Title
    y = 80
    if segment.title:
        _draw_centered_text(draw, segment.title, title_font, text_color, y, width)
        y += 120

    # List items
    body_text = segment.text
    if segment.title and body_text.startswith(segment.title):
        body_text = body_text[len(segment.title):].strip()

    list_lines = body_text.split("\n")
    x_left = 200
    for line in list_lines:
        if y > height - 100:
            break
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("• "):
            stripped = stripped[2:]

        # Bullet dot
        dot_x = x_left - 30
        draw.ellipse([dot_x, y + 14, dot_x + 10, y + 24], fill=accent)

        wrapped = _wrap_text(stripped, body_font, width - 300)
        for wl in wrapped:
            draw.text((x_left, y), wl, font=body_font, fill=text_color)
            y += 50
        y += 10

    img.save(output_path)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_renderer.py -v
```

Expected: all tests PASS (font-dependent tests may need adjustment on macOS)

- [ ] **Step 5: Commit**

```bash
git add src/renderer.py tests/test_renderer.py
git commit -m "feat: add visual renderer with template system"
```

---

### Task 5: Video composer — ffmpeg-based video assembly

**Files:**
- Create: `src/composer.py`
- Create: `tests/test_composer.py`

- [ ] **Step 1: Write failing tests for composer**

Create `tests/test_composer.py`:

```python
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.parser import Segment
from src.composer import compose_video, _check_ffmpeg


def test_check_ffmpeg_found():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert _check_ffmpeg() is True


def test_check_ffmpeg_not_found():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        assert _check_ffmpeg() is False


def test_compose_video_calls_ffmpeg(tmp_path):
    segments = [
        Segment(index=0, title="Test", level=1, type="title_slide",
                text="Test", duration=3.0),
        Segment(index=1, title="Section", level=2, type="section",
                text="Content", duration=5.0),
    ]

    # Create fake frame files
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for i in range(2):
        (frames_dir / f"segment_{i:04d}.png").write_bytes(b"fake png")

    # Create fake audio files
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    from src.tts import audio_cache_path
    for seg in segments:
        p = audio_cache_path(seg.text, str(audio_dir))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fake mp3")

    output = tmp_path / "output.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("src.composer._check_ffmpeg", return_value=True):
            compose_video(
                segments,
                str(output),
                {"video": {"fps": 30, "codec": "libx264",
                 "audio_codec": "aac", "audio_bitrate": "192k"}},
                str(frames_dir),
                str(audio_dir),
            )

    assert mock_run.called


def test_compose_video_ffmpeg_missing_raises(tmp_path):
    with patch("src.composer._check_ffmpeg", return_value=False):
        with pytest.raises(SystemExit):
            compose_video([], str(tmp_path / "out.mp4"), {}, ".", ".")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_composer.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement composer**

Create `src/composer.py`:

```python
import subprocess
import sys
from pathlib import Path
from src.parser import Segment
from src.tts import audio_cache_path, tts_text_for_segment


def _check_ffmpeg() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def compose_video(
    segments: list[Segment],
    output_path: str,
    config: dict,
    frames_dir: str = "./cache/frames",
    audio_dir: str = "./cache/audio",
) -> None:
    if not _check_ffmpeg():
        print("Error: ffmpeg not found. Install it with: brew install ffmpeg")
        sys.exit(1)

    video_cfg = config["video"]
    fps = video_cfg["fps"]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Build concat file for ffmpeg
    concat_path = output.parent / ".concat_list.txt"
    with open(concat_path, "w") as f:
        for seg in segments:
            frame_path = Path(frames_dir) / f"segment_{seg.index:04d}.png"
            duration = max(seg.duration, 0.5)
            f.write(f"file '{frame_path.absolute()}'\n")
            f.write(f"duration {duration}\n")
        # Last frame needs to be repeated for concat demuxer
        last_frame = Path(frames_dir) / f"segment_{len(segments) - 1:04d}.png"
        f.write(f"file '{last_frame.absolute()}'\n")

    # Build audio filter complex
    audio_inputs = []
    filter_parts = []
    for seg in segments:
        tts_text = tts_text_for_segment(seg)
        apath = audio_cache_path(tts_text, audio_dir)
        audio_inputs.extend(["-i", str(apath)])
        filter_parts.append(f"[{len(audio_inputs) // 2}:a]")

    if audio_inputs:
        # Build concat filter: [0:a][1:a]concat=n=N:v=0:a=1[outa]
        concat_filter = "".join(filter_parts) + \
            f"concat=n={len(segments)}:v=0:a=1[outa]"

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_path),
            *audio_inputs,
            "-filter_complex", concat_filter,
            "-map", "0:v",
            "-map", "[outa]",
            "-c:v", video_cfg["codec"],
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            "-c:a", video_cfg["audio_codec"],
            "-b:a", video_cfg["audio_bitrate"],
            "-shortest",
            str(output),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_path),
            "-c:v", video_cfg["codec"],
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}")
        raise RuntimeError("ffmpeg composition failed")

    concat_path.unlink(missing_ok=True)
    print(f"Video saved to: {output}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_composer.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/composer.py tests/test_composer.py
git commit -m "feat: add ffmpeg-based video composer"
```

---

### Task 6: CLI entry — main.py integration

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing test for CLI**

Create `tests/test_main.py`:

```python
import pytest
import subprocess
import sys
from pathlib import Path


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "markdown" in result.stdout.lower()


def test_cli_file_not_found():
    result = subprocess.run(
        [sys.executable, "main.py", "nonexistent.md"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_cli_dry_run(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Hello\n\nThis is a test.\n\n## Code\n\n```\nprint(1)\n```\n")

    result = subprocess.run(
        [sys.executable, "main.py", str(md_file), "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Segment" in result.stdout or len(result.stdout) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_main.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement CLI**

Create `main.py`:

```python
#!/usr/bin/env python3
import argparse
import asyncio
import sys
from pathlib import Path

from src.config import load_config
from src.parser import parse_markdown
from src.tts import generate_audio
from src.renderer import render_segment
from src.composer import compose_video


async def main():
    parser = argparse.ArgumentParser(
        description="Convert markdown files to video with AI voiceover."
    )
    parser.add_argument("markdown", help="Path to markdown file")
    parser.add_argument("-c", "--config", help="Path to config YAML file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse only, show segments without generating")
    args = parser.parse_args()

    md_path = Path(args.markdown)
    if not md_path.exists():
        print(f"Error: file not found: {args.markdown}")
        sys.exit(1)

    text = md_path.read_text(encoding="utf-8")
    if not text.strip():
        print("Error: file has no content")
        sys.exit(1)

    config = load_config(args.config)
    max_chars = config["render"]["max_chars_per_segment"]

    segments = parse_markdown(text, max_chars_per_segment=max_chars)
    if not segments:
        print("Error: no valid content found in file")
        sys.exit(1)

    if args.dry_run:
        for seg in segments:
            print(f"[{seg.index}] ({seg.type}) {seg.title or '(no title)'} "
                  f"— {len(seg.text)} chars")
        return

    output_name = md_path.stem
    output_dir = config["video"]["output_dir"]
    output_path = str(Path(output_dir) / f"{output_name}.mp4")

    cache_audio = Path("./cache/audio")
    cache_frames = Path("./cache/frames")

    # Step 1: Generate TTS audio
    print(f"Generating audio for {len(segments)} segments...")
    for i, seg in enumerate(segments):
        print(f"  [{i+1}/{len(segments)}] {seg.title or 'segment ' + str(i)}")
        duration = await generate_audio(seg, config, str(cache_audio))
        seg.duration = duration

    # Step 2: Render frames
    print(f"Rendering {len(segments)} frames...")
    for i, seg in enumerate(segments):
        print(f"  [{i+1}/{len(segments)}] rendering...")
        render_segment(seg, config, str(cache_frames))

    # Step 3: Compose video
    print("Composing video...")
    compose_video(
        segments,
        output_path,
        config,
        str(cache_frames),
        str(cache_audio),
    )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_main.py -v
```

Expected: all tests PASS

- [ ] **Step 5: Run integration test — full pipeline with dry run**

```bash
source .venv/bin/activate && echo '# Test

This is a test document.

## Section 1

Some content here.

## Code Example

```python
print("hello world")
```

## Features

- Feature A
- Feature B
' > /tmp/test_md.md && python main.py /tmp/test_md.md --dry-run
```

Expected: shows segment list with indices, types, and character counts

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: add CLI entry point with full pipeline integration"
```

---

### Task 7: End-to-end integration test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_integration.py`:

```python
import pytest
import subprocess
import sys
from pathlib import Path


def test_full_pipeline_dry_run_on_fixture():
    fixture = Path("tests/fixtures/sample.md")
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("""# Getting Started with Python

Python is a versatile programming language.

## Installation

Download Python from python.org and install it:

```
brew install python
```

## Key Features

- Easy to learn syntax
- Rich standard library
- Cross-platform support

## Next Steps

Try writing your first script and run it from the terminal.
""")

    result = subprocess.run(
        [sys.executable, "main.py", str(fixture), "--dry-run"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Getting Started" in result.stdout
    assert "title_slide" in result.stdout
    assert "code_block" in result.stdout
    assert "list" in result.stdout
```

- [ ] **Step 2: Run integration test**

```bash
source .venv/bin/activate && python -m pytest tests/test_integration.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py tests/fixtures/sample.md
git commit -m "test: add end-to-end integration test"
```
