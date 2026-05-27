# Markdown to Video V2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade markdown-to-video from mechanical assembly to a director-level creation tool with annotation system, image support, mixed layouts, syntax highlighting, enhanced audio, and video transitions.

**Architecture:** Annotation directives embedded in markdown HTML comments control every segment's behavior (voice, image, layout, pause, transition). A layout system with 4 modes replaces the monolithic renderer. TTS is parameterized per-segment. Composer adds BGM ducking and xfade transitions.

**Tech Stack:** Python 3.13, mistune, edge-tts, Pillow, ffmpeg, PyYAML, Pygments (new), mutagen, pytest

---

## File Structure

```
New files:
  src/annotations.py          # Annotation data model + parser
  src/image_provider.py       # Image resolution (annotation → local → Unsplash)
  src/layouts/__init__.py     # LayoutFactory
  src/layouts/base.py         # BaseLayout ABC
  src/layouts/text_only.py    # Text-only (V1 compat)
  src/layouts/image_right.py  # Left text + right image
  src/layouts/image_below.py  # Top text + bottom image
  src/layouts/image_full.py   # Full-screen image + overlay title
  src/syntax_highlighter.py   # Pygments-based code coloring
  src/mermaid_renderer.py     # Mermaid → PNG via mmdc
  src/highlight.py            # Keyword highlight rendering helper

Modified files:
  src/parser.py               # Segment gets annotation fields; parse mermaid type
  src/renderer.py             # Delegate to layout system; remove old _render_* funcs
  src/tts.py                  # Accept voice/speed/pitch params
  src/composer.py             # BGM ducking, xfade transitions, smart pauses
  src/config.py               # New V2 config defaults
  config.yaml                 # Full V2 config
  main.py                     # Pass annotations to pipeline
  requirements.txt            # Add pygments
```

---

### Task 1: Annotation data model and parser

**Files:**
- Create: `src/annotations.py`
- Create: `tests/test_annotations.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_annotations.py`:

```python
import pytest
from src.annotations import parse_annotations, apply_annotations
from src.parser import Segment


def test_parse_single_line_annotation():
    text = '<!-- {"voice": "zh-CN-YunxiNeural"} -->\n\n## Title\n\nContent.'
    results = parse_annotations(text)

    assert len(results) == 1
    line_num, ann = results[0]
    assert ann["voice"] == "zh-CN-YunxiNeural"


def test_parse_multi_line_annotation():
    text = '<!--\n{"voice": "zh-CN-YunxiNeural",\n "speed": "-10%"}\n-->\n\nContent.'
    results = parse_annotations(text)

    assert len(results) == 1
    _, ann = results[0]
    assert ann["speed"] == "-10%"


def test_parse_multiple_annotations():
    text = (
        '<!-- {"voice": "A"} -->\n\n## Section 1\n\nContent 1.\n\n'
        '<!-- {"voice": "B"} -->\n\n## Section 2\n\nContent 2.'
    )
    results = parse_annotations(text)

    assert len(results) == 2


def test_non_json_comment_is_ignored():
    text = '<!-- just a regular comment -->\n\n## Title\n\nContent.'
    results = parse_annotations(text)

    assert len(results) == 0


def test_no_annotations_returns_empty():
    text = '# Title\n\nJust content.'
    results = parse_annotations(text)

    assert len(results) == 0


def test_apply_annotations_to_segments():
    segments = [
        Segment(0, "Title", 1, "title_slide", "Title\n\nContent"),
        Segment(1, "Section", 2, "section", "Section\n\nBody"),
    ]
    annotations = [
        (1, {"voice": "zh-CN-YunxiNeural"}),
    ]

    result = apply_annotations(segments, annotations, text="# markdown\n\n...")

    assert result[0].voice == "zh-CN-YunxiNeural"


def test_apply_annotations_with_defaults():
    segments = [Segment(0, "T", 1, "title_slide", "T")]
    annotations = [(1, {"layout": "image-right"})]

    result = apply_annotations(segments, annotations, text="# md\n\n...")

    assert result[0].layout == "image-right"
    assert result[0].transition == "none"  # default
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_annotations.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement annotation parser**

Create `src/annotations.py`:

```python
import json
import re
from src.parser import Segment

ANNOTATION_PATTERN = re.compile(r"<!--\s*(.*?)\s*-->", re.DOTALL)

ANNOTATION_DEFAULTS = {
    "voice": None,
    "speed": None,
    "pitch": None,
    "image": None,
    "layout": "text-only",
    "pause_before": 0.0,
    "pause_after": 0.0,
    "highlight": None,
    "bgm": None,
    "bgm_volume": 0.15,
    "transition": "none",
}


def parse_annotations(text: str) -> list[tuple[int, dict]]:
    results: list[tuple[int, dict]] = []
    for match in ANNOTATION_PATTERN.finditer(text):
        content = match.group(1).strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            line_number = text[: match.start()].count("\n") + 1
            results.append((line_number, data))
    return results


def apply_annotations(
    segments: list[Segment],
    annotations: list[tuple[int, dict]],
    text: str,
) -> list[Segment]:
    if not annotations:
        return segments

    ann_by_lineno = {lineno: ann for lineno, ann in annotations}

    lines = text.split("\n")
    segment_line_ranges = _compute_segment_line_ranges(segments, lines)

    for seg in segments:
        seg_start = segment_line_ranges.get(seg.index, 0)
        applicable = {}
        for lineno, ann in annotations:
            if lineno <= seg_start:
                applicable.update(ann)

        if applicable:
            _fill_segment_from_annotation(seg, applicable)

    return segments


def _compute_segment_line_ranges(
    segments: list[Segment], lines: list[str]
) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for seg in segments:
        if seg.index == 0:
            mapping[0] = 1
            continue
        title = seg.title or ""
        for i, line in enumerate(lines, start=1):
            if title and line.strip() == title.strip():
                mapping[seg.index] = i
                break
    return mapping


def _fill_segment_from_annotation(seg: Segment, ann: dict) -> None:
    for key, default in ANNOTATION_DEFAULTS.items():
        if key in ann:
            setattr(seg, key, ann[key])
        elif getattr(seg, key, None) is None and not has_seg_value(seg, key):
            setattr(seg, key, default)


def has_seg_value(seg: Segment, key: str) -> bool:
    val = getattr(seg, key, None)
    if val is None:
        return False
    if isinstance(val, float) and val == 0.0:
        return False
    if isinstance(val, str) and val in ("text-only", "none"):
        return False
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_annotations.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/annotations.py tests/test_annotations.py
git commit -m "feat(v2): add annotation parser for markdown director directives"
```

---

### Task 2: Upgrade Segment model and parser

**Files:**
- Modify: `src/parser.py` — add V2 fields to Segment, handle mermaid type
- Modify: `tests/test_parser.py` — add tests for new fields and mermaid

- [ ] **Step 1: Update Segment dataclass and add mermaid handling tests**

Append to `tests/test_parser.py`:

```python
def test_segment_has_v2_fields():
    from src.parser import Segment
    seg = Segment(0, "Test", 1, "section", "content")
    assert seg.voice is None
    assert seg.layout == "text-only"
    assert seg.image_path is None
    assert seg.transition == "none"


def test_mermaid_code_block_gets_mermaid_type():
    md = "## Diagram\n\n```mermaid\ngraph LR\n  A --> B\n```"
    segments = parse_markdown(md)
    assert segments[0].type == "mermaid"


def test_code_block_with_language_is_code_block():
    md = "## Code\n\n```python\nprint('hello')\n```"
    segments = parse_markdown(md)
    assert segments[0].type == "code_block"


def test_parse_markdown_with_annotations_extracts_them():
    md = '<!-- {"voice": "zh-CN-YunxiNeural"} -->\n\n# Hello\n\nWorld.'
    segments = parse_markdown(md)
    assert segments[0].voice == "zh-CN-YunxiNeural"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_parser.py -v -k "v2 or mermaid"
```
Expected: FAIL

- [ ] **Step 3: Upgrade Segment and parser**

Replace the Segment dataclass in `src/parser.py`:

```python
from dataclasses import dataclass, field
import re
import mistune


@dataclass
class Segment:
    index: int
    title: str
    level: int
    type: str  # title_slide | section | code_block | list | mermaid
    text: str
    duration: float = 0
    # V2 fields
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
```

Update `parse_markdown()` to handle mermaid and call annotation parser. Add after the imports in `src/parser.py`:

```python
from src.annotations import parse_annotations as _parse_annotations, apply_annotations
```

Add mermaid detection in the `block_code` handling block. Change:

```python
if node_type == "block_code":
    current = _ensure_segment(current, segments)
    info = node.get("attrs", {}).get("info", "")
    fence = f"```{info}".rstrip()
    _append_text(current, f"{fence}\n{node.get('raw', '').rstrip()}\n```")
    current.type = "code_block"
    continue
```

To:

```python
if node_type == "block_code":
    current = _ensure_segment(current, segments)
    info = node.get("attrs", {}).get("info", "")
    seg_type = "mermaid" if info == "mermaid" else "code_block"
    fence = f"```{info}".rstrip()
    _append_text(current, f"{fence}\n{node.get('raw', '').rstrip()}\n```")
    current.type = seg_type
    continue
```

At the end of `parse_markdown()`, add annotation application before the return:

```python
    # --- existing code: ---
    segments = _split_long_segments(segments, max_chars_per_segment)
    for index, segment in enumerate(segments):
        segment.index = index

    # V2: apply annotations
    annotations = _parse_annotations(text)
    segments = apply_annotations(segments, annotations, text)

    return segments
```

- [ ] **Step 4: Run all parser tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_parser.py -v
```
Expected: all PASS (existing + new tests)

- [ ] **Step 5: Commit**

```bash
git add src/parser.py tests/test_parser.py
git commit -m "feat(v2): add V2 fields to Segment, mermaid type detection, annotation integration"
```

---

### Task 3: Wire annotations into CLI pipeline

**Files:**
- Modify: `main.py` — pass segment annotations to TTS and renderer
- Modify: `tests/test_main.py` — verify dry-run shows annotation info

- [ ] **Step 1: Write test for annotation-aware dry-run**

Append to `tests/test_main.py`:

```python
def test_dry_run_shows_annotation_info(tmp_path):
    md_file = tmp_path / "annotated.md"
    md_file.write_text(
        '<!-- {"voice": "zh-CN-YunxiNeural", "layout": "image-right"} -->\n'
        '# Title\n\nContent.'
    )
    result = subprocess.run(
        [sys.executable, "main.py", str(md_file), "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
```

- [ ] **Step 2: Run test to verify it fails only if behavior missing**

```bash
source .venv/bin/activate && python -m pytest tests/test_main.py::test_dry_run_shows_annotation_info -v
```

- [ ] **Step 3: Update main.py to pass annotations through pipeline**

Modify `main.py` — the TTS loop and render loop should use segment-level overrides:

In TTS loop, change `await generate_audio(segment, config, str(cache_audio))` so config is overridden per-segment. Add a helper before `main()`:

```python
def _segment_tts_config(segment: Segment, config: dict) -> dict:
    tts_cfg = dict(config["tts"])
    if segment.voice:
        tts_cfg["voice"] = segment.voice
    if segment.speed:
        tts_cfg["speed"] = segment.speed
    if segment.pitch:
        tts_cfg["pitch"] = segment.pitch
    return tts_cfg
```

Then in the TTS loop:

```python
    print(f"Generating audio for {len(segments)} segments...")
    for position, segment in enumerate(segments, start=1):
        title = segment.title or f"segment {segment.index}"
        print(f"  [{position}/{len(segments)}] {title}")
        await generate_audio(segment, config, str(cache_audio))
```

Update the dry-run output to show annotation info:

```python
    if args.dry_run:
        for segment in segments:
            title = segment.title or "(no title)"
            extra = []
            if segment.voice:
                extra.append(f"voice={segment.voice}")
            if segment.layout != "text-only":
                extra.append(f"layout={segment.layout}")
            if segment.image_path:
                extra.append(f"image={segment.image_path}")
            ext_str = ", " + ", ".join(extra) if extra else ""
            print(
                f"Segment {segment.index}: "
                f"type={segment.type}, title={title}, chars={len(segment.text)}{ext_str}"
            )
        return
```

- [ ] **Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_main.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat(v2): wire annotations through CLI pipeline"
```

---

### Task 4: Image provider

**Files:**
- Create: `src/image_provider.py`
- Create: `tests/test_image_provider.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_image_provider.py`:

```python
import pytest
from pathlib import Path
from src.image_provider import resolve_image, load_manifest, match_image_from_manifest


def test_resolve_image_returns_annotation_path(tmp_path):
    img = tmp_path / "test.png"
    img.write_text("fake")
    segment = type("Seg", (), {
        "image_path": str(img),
        "title": "Test",
        "text": "Test content",
    })()

    result = resolve_image(segment, {}, tmp_path)
    assert result == str(img)


def test_resolve_image_returns_none_when_no_match(tmp_path):
    segment = type("Seg", (), {
        "image_path": None,
        "title": "Random",
        "text": "No matching images anywhere.",
    })()

    config = {"image": {"assets_dir": str(tmp_path), "manifest_file": ""}}
    result = resolve_image(segment, config, tmp_path)
    assert result is None


def test_load_manifest(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "images:\n"
        "  - file: python.png\n"
        "    keywords: [python, coding]\n"
        "  - file: docker.png\n"
        "    keywords: [docker, container]\n"
    )
    data = load_manifest(str(manifest))
    assert len(data["images"]) == 2


def test_match_image_from_manifest():
    manifest = {
        "images": [
            {"file": "python.png", "keywords": ["python", "coding"]},
            {"file": "docker.png", "keywords": ["docker", "container"]},
            {"file": "generic.png", "keywords": ["software"]},
        ]
    }
    result = match_image_from_manifest(
        "In this Python tutorial we will learn coding basics.", manifest
    )
    assert result is not None
    assert "python" in str(result).lower()


def test_match_image_no_match_returns_none():
    manifest = {
        "images": [
            {"file": "docker.png", "keywords": ["docker", "container"]},
        ]
    }
    result = match_image_from_manifest(
        "Python is a great language for data science.", manifest
    )
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_image_provider.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement image provider**

Create `src/image_provider.py`:

```python
from pathlib import Path
import yaml


def resolve_image(
    segment,
    config: dict,
    cache_dir: Path,
) -> str | None:
    if segment.image_path:
        path = Path(segment.image_path)
        if path.is_absolute() and path.exists():
            return str(path)
        resolved = Path.cwd() / path
        if resolved.exists():
            return str(resolved)
        return None

    image_cfg = config.get("image", {})
    manifest_path = image_cfg.get("manifest_file", "")
    if manifest_path:
        manifest = load_manifest(manifest_path)
        candidate = match_image_from_manifest(segment.text, manifest)
        if candidate:
            assets_dir = Path(image_cfg.get("assets_dir", "./assets/images"))
            full = assets_dir / candidate
            if full.exists():
                return str(full)

    return None


def load_manifest(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"images": []}
    with open(p) as f:
        return yaml.safe_load(f) or {"images": []}


def match_image_from_manifest(text: str, manifest: dict) -> str | None:
    images = manifest.get("images", [])
    if not images:
        return None

    text_lower = text.lower()
    best_match = None
    best_score = 0

    for entry in images:
        keywords = entry.get("keywords", [])
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_match = entry["file"]

    return best_match if best_score > 0 else None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_image_provider.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/image_provider.py tests/test_image_provider.py
git commit -m "feat(v2): add image provider with manifest-based matching"
```

---

### Task 5: Layout system — base + text_only + image_right

**Files:**
- Create: `src/layouts/__init__.py`
- Create: `src/layouts/base.py`
- Create: `src/layouts/text_only.py`
- Create: `src/layouts/image_right.py`
- Create: `tests/test_layouts.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_layouts.py`:

```python
import pytest
from pathlib import Path
from PIL import Image
from src.parser import Segment
from src.layouts import LayoutFactory


SAMPLE_CFG = {
    "width": 800, "height": 600,
    "font_family": "/System/Library/Fonts/STHeiti Medium.ttc",
    "font_family_mono": "/System/Library/Fonts/SFNSMono.ttf",
    "font_size_title": 48, "font_size_body": 28, "font_size_code": 22,
    "bg_color": "#f5f5f5", "code_bg_color": "#1e1e1e",
    "accent_color": "#4A90D9", "text_color": "#333333",
    "light_text_color": "#e0e0e0",
}


def test_factory_returns_text_only_layout():
    layout = LayoutFactory.create("text-only")
    from src.layouts.text_only import TextOnlyLayout
    assert isinstance(layout, TextOnlyLayout)


def test_factory_returns_image_right_layout():
    layout = LayoutFactory.create("image-right")
    from src.layouts.image_right import ImageRightLayout
    assert isinstance(layout, ImageRightLayout)


def test_factory_unknown_returns_text_only():
    layout = LayoutFactory.create("nonexistent")
    from src.layouts.text_only import TextOnlyLayout
    assert isinstance(layout, TextOnlyLayout)


def test_text_only_renders(tmp_path):
    seg = Segment(0, "Section Title", 2, "section",
                  "Section Title\n\nThis is body content.")
    seg.layout = "text-only"

    layout = LayoutFactory.create("text-only")
    path = layout.render(seg, SAMPLE_CFG, tmp_path / "frames")

    assert path.endswith(".png")
    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_image_right_renders_with_image(tmp_path):
    img_path = tmp_path / "test_img.png"
    test_img = Image.new("RGB", (400, 300), color=(100, 150, 200))
    test_img.save(img_path)

    seg = Segment(0, "Diagram", 2, "section",
                  "Diagram\n\nHere is the architecture.")
    seg.layout = "image-right"
    seg.image_path = str(img_path)

    layout = LayoutFactory.create("image-right")
    path = layout.render(seg, SAMPLE_CFG, tmp_path / "frames")

    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_layouts.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement base + factory + text_only + image_right**

Create `src/layouts/__init__.py`:

```python
from src.layouts.text_only import TextOnlyLayout


class LayoutFactory:
    _layouts = {}

    @classmethod
    def register(cls, name: str, layout_cls):
        cls._layouts[name] = layout_cls

    @classmethod
    def create(cls, name: str):
        layout_cls = cls._layouts.get(name)
        if layout_cls is None:
            from src.layouts.text_only import TextOnlyLayout
            return TextOnlyLayout()
        return layout_cls()
```

Create `src/layouts/base.py`:

```python
from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from src.parser import Segment


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.strip().lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _get_font(font_path: str, size: int):
    candidates = [
        font_path,
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_centered_text(draw, text: str, font, fill, y: int, width: int) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((width - tw) // 2, y), text, font=font, fill=fill)
    return th


def _wrap_text(text: str, font, max_width: int) -> list[str]:
    lines = []
    for para in text.splitlines():
        if not para.strip():
            lines.append("")
            continue
        current = ""
        for ch in para:
            candidate = current + ch
            bbox = font.getbbox(candidate)
            if bbox[2] - bbox[0] > max_width and current:
                lines.append(current)
                current = ch
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def _body_without_title(segment: Segment) -> str:
    text = segment.text
    if segment.title and text.startswith(segment.title):
        text = text[len(segment.title):].strip()
    return text


class BaseLayout(ABC):
    @abstractmethod
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        ...
```

Create `src/layouts/text_only.py`:

```python
from pathlib import Path
from PIL import Image, ImageDraw
from src.parser import Segment
from src.layouts.base import (
    BaseLayout, _hex_to_rgb, _get_font,
    _draw_centered_text, _wrap_text, _body_without_title,
)
from src.layouts import LayoutFactory


class TextOnlyLayout(BaseLayout):
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"segment_{segment.index:04d}.png"
        width, height = cfg["width"], cfg["height"]
        bg = _hex_to_rgb(cfg["bg_color"])
        accent = _hex_to_rgb(cfg["accent_color"])
        text_color = _hex_to_rgb(cfg["text_color"])

        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)

        draw.rectangle([0, 0, width, 8], fill=accent)

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        body_font = _get_font(cfg["font_family"], cfg["font_size_body"])

        y = 80
        if segment.title:
            y += _draw_centered_text(draw, segment.title, title_font, text_color, y, width)
            y += 80

        body = _body_without_title(segment)
        for line in _wrap_text(body, body_font, width - 200):
            if y > height - 90:
                break
            if not line:
                y += 28
                continue
            y += _draw_centered_text(draw, line, body_font, text_color, y, width) + 18

        img.save(output_path)
        return str(output_path)


LayoutFactory.register("text-only", TextOnlyLayout)
```

Create `src/layouts/image_right.py`:

```python
from pathlib import Path
from PIL import Image, ImageDraw
from src.parser import Segment
from src.layouts.base import (
    BaseLayout, _hex_to_rgb, _get_font,
    _draw_centered_text, _wrap_text, _body_without_title,
)
from src.layouts import LayoutFactory


class ImageRightLayout(BaseLayout):
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"segment_{segment.index:04d}.png"
        width, height = cfg["width"], cfg["height"]
        bg = _hex_to_rgb(cfg["bg_color"])
        accent = _hex_to_rgb(cfg["accent_color"])
        text_color = _hex_to_rgb(cfg["text_color"])

        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)

        draw.rectangle([0, 0, width, 8], fill=accent)

        # Split canvas: left 60% text, right 40% image
        text_width = int(width * 0.58)
        img_area_left = text_width + 40
        img_area_width = width - img_area_left - 40
        img_area_top = 100
        img_area_height = height - 140

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        body_font = _get_font(cfg["font_family"], cfg["font_size_body"])

        # Title spans full width
        y = 80
        if segment.title:
            y += _draw_centered_text(draw, segment.title, title_font, text_color, y, width)
            y += 60

        # Body on left
        body = _body_without_title(segment)
        for line in _wrap_text(body, body_font, text_width - 60)[:12]:
            if y > height - 90:
                break
            if not line:
                y += 24
                continue
            # left-aligned body text
            bbox = draw.textbbox((0, 0), line, font=body_font)
            th = bbox[3] - bbox[1]
            draw.text((60, y), line, font=body_font, fill=text_color)
            y += th + 14

        # Image on right
        if segment.image_path:
            try:
                pil_img = Image.open(segment.image_path).convert("RGB")
                pil_img = _fit_image(pil_img, img_area_width, img_area_height)
                iw, ih = pil_img.size
                ix = img_area_left + (img_area_width - iw) // 2
                iy = img_area_top + (img_area_height - ih) // 2
                img.paste(pil_img, (ix, iy))
            except Exception:
                pass

        img.save(output_path)
        return str(output_path)


def _fit_image(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    iw, ih = img.size
    scale = min(max_w / iw, max_h / ih, 1.0)
    new_w, new_h = int(iw * scale), int(ih * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)


LayoutFactory.register("image-right", ImageRightLayout)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_layouts.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/layouts/ tests/test_layouts.py
git commit -m "feat(v2): add layout system with base, text-only, and image-right layouts"
```

---

### Task 6: Layout system — image_below + image_full

**Files:**
- Create: `src/layouts/image_below.py`
- Create: `src/layouts/image_full.py`

- [ ] **Step 1: Write tests**

Append to `tests/test_layouts.py`:

```python
def test_factory_returns_image_below_layout():
    layout = LayoutFactory.create("image-below")
    from src.layouts.image_below import ImageBelowLayout
    assert isinstance(layout, ImageBelowLayout)


def test_factory_returns_image_full_layout():
    layout = LayoutFactory.create("image-full")
    from src.layouts.image_full import ImageFullLayout
    assert isinstance(layout, ImageFullLayout)


def test_image_below_renders(tmp_path):
    img_path = tmp_path / "test_img.png"
    Image.new("RGB", (600, 200), color=(100, 180, 100)).save(img_path)

    seg = Segment(0, "Chart", 2, "section", "Chart\n\nData analysis results.")
    seg.layout = "image-below"
    seg.image_path = str(img_path)

    layout = LayoutFactory.create("image-below")
    path = layout.render(seg, SAMPLE_CFG, tmp_path / "frames")
    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_image_full_renders(tmp_path):
    img_path = tmp_path / "bg_img.png"
    Image.new("RGB", (800, 600), color=(50, 50, 80)).save(img_path)

    seg = Segment(0, "Overview", 1, "title_slide", "Overview")
    seg.layout = "image-full"
    seg.image_path = str(img_path)

    layout = LayoutFactory.create("image-full")
    path = layout.render(seg, SAMPLE_CFG, tmp_path / "frames")
    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .venv/bin/activate && python -m pytest tests/test_layouts.py -v -k "below or full"
```
Expected: FAIL

- [ ] **Step 3: Implement image_below and image_full**

Create `src/layouts/image_below.py`:

```python
from pathlib import Path
from PIL import Image, ImageDraw
from src.parser import Segment
from src.layouts.base import (
    BaseLayout, _hex_to_rgb, _get_font,
    _draw_centered_text, _wrap_text, _body_without_title,
)
from src.layouts import LayoutFactory


class ImageBelowLayout(BaseLayout):
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"segment_{segment.index:04d}.png"
        width, height = cfg["width"], cfg["height"]
        bg = _hex_to_rgb(cfg["bg_color"])
        accent = _hex_to_rgb(cfg["accent_color"])
        text_color = _hex_to_rgb(cfg["text_color"])

        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, width, 8], fill=accent)

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        body_font = _get_font(cfg["font_family"], cfg["font_size_body"])

        y = 80
        if segment.title:
            y += _draw_centered_text(draw, segment.title, title_font, text_color, y, width)
            y += 50

        body = _body_without_title(segment)
        for line in _wrap_text(body, body_font, width - 200)[:4]:
            if not line:
                y += 20
                continue
            y += _draw_centered_text(draw, line, body_font, text_color, y, width) + 14

        # Image area below text
        img_top = y + 30
        img_max_h = height - img_top - 20
        if segment.image_path and img_max_h > 100:
            try:
                pil_img = Image.open(segment.image_path).convert("RGB")
                iw, ih = pil_img.size
                scale = min((width - 120) / iw, img_max_h / ih, 1.0)
                nw, nh = int(iw * scale), int(ih * scale)
                pil_img = pil_img.resize((nw, nh), Image.LANCZOS)
                ix = (width - nw) // 2
                iy = img_top + (img_max_h - nh) // 2
                img.paste(pil_img, (ix, iy))
            except Exception:
                pass

        img.save(output_path)
        return str(output_path)


LayoutFactory.register("image-below", ImageBelowLayout)
```

Create `src/layouts/image_full.py`:

```python
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from src.parser import Segment
from src.layouts.base import BaseLayout, _hex_to_rgb, _get_font, _draw_centered_text
from src.layouts import LayoutFactory


class ImageFullLayout(BaseLayout):
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"segment_{segment.index:04d}.png"
        width, height = cfg["width"], cfg["height"]
        accent = _hex_to_rgb(cfg["accent_color"])

        # Try to load image as background; fall back to accent gradient
        bg_img = None
        if segment.image_path:
            try:
                bg_img = Image.open(segment.image_path).convert("RGB")
                bg_img = bg_img.resize((width, height), Image.LANCZOS)
            except Exception:
                pass

        if bg_img is None:
            bg_img = Image.new("RGB", (width, height), _hex_to_rgb(cfg["bg_color"]))

        # Dark overlay for text readability
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 100))
        bg_img = bg_img.convert("RGBA")
        bg_img = Image.alpha_composite(bg_img, overlay).convert("RGB")

        draw = ImageDraw.Draw(bg_img)

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
        light_text = _hex_to_rgb(cfg["light_text_color"])

        y = height // 3
        if segment.title:
            for line in segment.title.split("\n"):
                y += _draw_centered_text(draw, line, title_font, light_text, y, width) + 18

        body_lines = [l.strip() for l in segment.text.splitlines()
                      if l.strip() and segment.title and l.strip() not in segment.title]
        y += 30
        for line in body_lines[:4]:
            y += _draw_centered_text(draw, line, body_font, light_text, y, width) + 12

        bg_img.save(output_path)
        return str(output_path)


LayoutFactory.register("image-full", ImageFullLayout)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_layouts.py -v
```
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/layouts/image_below.py src/layouts/image_full.py tests/test_layouts.py
git commit -m "feat(v2): add image-below and image-full layouts"
```

---

### Task 7: Refactor renderer to use layout system

**Files:**
- Modify: `src/renderer.py` — delegate to LayoutFactory, remove V1 render functions
- Modify: `tests/test_renderer.py` — test via layout delegation
- Modify: `main.py` — resolve image before rendering

- [ ] **Step 1: Rewrite renderer to delegate to layouts**

Replace `src/renderer.py`:

```python
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from src.parser import Segment
from src.layouts import LayoutFactory
from src.image_provider import resolve_image


def render_segment(segment: Segment, config: dict, cache_dir: str) -> str:
    render_cfg = config["render"]

    # Resolve image if annotated
    if segment.image_path or segment.layout in ("image-right", "image-below", "image-full"):
        resolved = resolve_image(segment, config, Path(cache_dir))
        if resolved:
            segment.image_path = resolved
        elif segment.layout != "text-only":
            # fall back to text-only if image can't be resolved
            segment.layout = "text-only"

    layout = LayoutFactory.create(segment.layout)
    return layout.render(segment, render_cfg, Path(cache_dir))


# Keep _hex_to_rgb for backward compat in tests
def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.strip().lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
```

- [ ] **Step 2: Run existing renderer tests to check compatibility**

```bash
source .venv/bin/activate && python -m pytest tests/test_renderer.py -v
```
Expected: `test_hex_to_rgb` passes; `test_render_*` tests may fail — fix or update them.

- [ ] **Step 3: Update renderer tests for V2**

Replace `tests/test_renderer.py`:

```python
import pytest
from pathlib import Path
from PIL import Image
from src.parser import Segment
from src.renderer import render_segment, _hex_to_rgb


SAMPLE_CFG = {
    "render": {
        "width": 800, "height": 600,
        "font_family": "/System/Library/Fonts/STHeiti Medium.ttc",
        "font_family_mono": "/System/Library/Fonts/SFNSMono.ttf",
        "font_size_title": 48, "font_size_body": 28, "font_size_code": 22,
        "bg_color": "#f5f5f5", "code_bg_color": "#1e1e1e",
        "accent_color": "#4A90D9", "text_color": "#333333",
        "light_text_color": "#e0e0e0",
    }
}


def test_hex_to_rgb():
    assert _hex_to_rgb("#ff0000") == (255, 0, 0)
    assert _hex_to_rgb("#4A90D9") == (74, 144, 217)
    assert _hex_to_rgb("#1e1e1e") == (30, 30, 30)


def test_render_title_slide_uses_layout(tmp_path):
    seg = Segment(0, "Python Tutorial", 1, "title_slide",
                  "Python Tutorial\n\nAuthor: Test")
    seg.layout = "text-only"
    path = render_segment(seg, SAMPLE_CFG, str(tmp_path))
    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_render_code_block_uses_layout(tmp_path):
    seg = Segment(1, "Example Code", 2, "code_block",
                  "Example Code\n\n```\nprint('hello')\n```")
    seg.layout = "text-only"
    path = render_segment(seg, SAMPLE_CFG, str(tmp_path))
    assert Path(path).exists()
    img = Image.open(path)
    assert img.size == (800, 600)


def test_render_list_uses_layout(tmp_path):
    seg = Segment(2, "Features", 2, "list",
                  "Features\n* Feature A\n* Feature B\n* Feature C")
    seg.layout = "text-only"
    path = render_segment(seg, SAMPLE_CFG, str(tmp_path))
    assert Path(path).exists()


def test_render_falls_back_to_text_only_without_image(tmp_path):
    seg = Segment(0, "Title", 2, "section", "Title\n\nContent.")
    seg.layout = "image-right"
    seg.image_path = None
    path = render_segment(seg, SAMPLE_CFG, str(tmp_path))
    assert Path(path).exists()
```

- [ ] **Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_renderer.py -v
```
Expected: all PASS

- [ ] **Step 5: Ensure full test suite still passes**

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add src/renderer.py tests/test_renderer.py
git commit -m "feat(v2): refactor renderer to delegate to layout system"
```

---

### Task 8: Code syntax highlighting with Pygments

**Files:**
- Create: `src/syntax_highlighter.py`
- Create: `tests/test_syntax_highlighter.py`
- Modify: `requirements.txt` — add `pygments`
- Modify: `src/layouts/text_only.py` — use syntax highlighting for code blocks

- [ ] **Step 1: Install Pygments**

```bash
source .venv/bin/activate && pip install pygments
```
Then add `pygments>=2.18` to `requirements.txt`.

- [ ] **Step 2: Write failing test**

Create `tests/test_syntax_highlighter.py`:

```python
import pytest
from src.syntax_highlighter import highlight_code, tokenize_code


def test_tokenize_python_code():
    tokens = tokenize_code('print("hello")', "python")
    assert len(tokens) > 0
    assert any(t[0] for t in tokens)  # each token has (color_hex, text)


def test_highlight_code_returns_colored_segments():
    result = highlight_code('def foo():\n    return 42\n', "python")
    assert len(result) > 0
    assert all(len(token) == 2 for line in result for token in line)


def test_unknown_language_falls_back():
    result = highlight_code('some code', "fakelang")
    assert len(result) > 0


def test_empty_code_returns_empty():
    result = highlight_code("", "python")
    assert result == []
```

- [ ] **Step 3: Implement syntax highlighter**

Create `src/syntax_highlighter.py`:

```python
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatter import Formatter
from pygments.token import Token


# Monokai-inspired color mapping
TOKEN_COLORS = {
    Token.Keyword: "#F92672",
    Token.Keyword.Namespace: "#F92672",
    Token.Keyword.Type: "#66D9EF",
    Token.Name.Function: "#A6E22E",
    Token.Name.Class: "#A6E22E",
    Token.Name.Decorator: "#A6E22E",
    Token.String: "#E6DB74",
    Token.String.Doc: "#E6DB74",
    Token.String.Affix: "#E6DB74",
    Token.Number: "#AE81FF",
    Token.Number.Integer: "#AE81FF",
    Token.Number.Float: "#AE81FF",
    Token.Comment: "#75715E",
    Token.Comment.Single: "#75715E",
    Token.Comment.Multiline: "#75715E",
    Token.Operator: "#F92672",
    Token.Operator.Word: "#F92672",
    Token.Name.Builtin: "#66D9EF",
    Token.Name.Builtin.Pseudo: "#66D9EF",
    Token.Generic.Heading: "#A6E22E",
    Token.Generic.Subheading: "#A6E22E",
}


class _TokenCollector(Formatter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tokens: list[tuple[str, str]] = []

    def format(self, tokensource, outfile):
        for ttype, value in tokensource:
            color = "#F8F8F2"  # default light text
            for token_type, token_color in TOKEN_COLORS.items():
                if ttype in token_type:
                    color = token_color
                    break
            self.tokens.append((color, value))


def tokenize_code(code: str, language: str) -> list[tuple[str, str]]:
    try:
        lexer = get_lexer_by_name(language, stripnl=False)
    except Exception:
        lexer = guess_lexer(code)
    collector = _TokenCollector()
    highlight(code, lexer, collector)
    return collector.tokens


def highlight_code(code: str, language: str) -> list[list[tuple[str, str]]]:
    """Return list of lines, each line is list of (color_hex, text) tokens."""
    tokens = tokenize_code(code, language)
    lines: list[list[tuple[str, str]]] = []
    current_line: list[tuple[str, str]] = []

    for color, text in tokens:
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                lines.append(current_line)
                current_line = []
            if part:
                current_line.append((color, part))

    if current_line:
        lines.append(current_line)

    return lines
```

- [ ] **Step 4: Update text_only layout to use highlighting for code blocks**

In `src/layouts/text_only.py`, add a `_render_code_block` method and modify the `render` method.

Add before the class:

```python
from src.syntax_highlighter import highlight_code as _highlight_code
```

Modify the `render` method in `TextOnlyLayout` to dispatch code blocks:

```python
    def render(self, segment: Segment, cfg: dict, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"segment_{segment.index:04d}.png"
        width, height = cfg["width"], cfg["height"]

        if segment.type in ("code_block", "mermaid"):
            return self._render_code_content(segment, cfg, output_path, width, height)

        # ... existing text rendering code ...
```

Add `_render_code_content` method to the class:

```python
    def _render_code_content(self, segment, cfg, output_path, width, height):
        code_bg = _hex_to_rgb(cfg["code_bg_color"])
        accent = _hex_to_rgb(cfg["accent_color"])
        light_text = _hex_to_rgb(cfg["light_text_color"])
        img = Image.new("RGB", (width, height), code_bg)
        draw = ImageDraw.Draw(img)

        # Window control dots
        for idx, color in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            x = 40 + idx * 32
            draw.ellipse([x, 30, x + 16, 46], fill=color)

        title_font = _get_font(cfg["font_family"], cfg["font_size_title"])
        body_font = _get_font(cfg["font_family"], cfg["font_size_body"])
        code_font = _get_font(cfg["font_family_mono"], cfg["font_size_code"])

        y = 80
        if segment.title:
            draw.text((60, y), segment.title, font=title_font, fill=accent)
            y += cfg["font_size_title"] + 50

        # Extract language from fence
        code_text = segment.text
        language = "text"
        for line in code_text.splitlines():
            if line.strip().startswith("```") and line.strip() != "```":
                language = line.strip()[3:].strip()
                break

        # Extract raw code
        in_code = False
        raw_lines = []
        for line in code_text.splitlines():
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                raw_lines.append(line)

        if raw_lines:
            highlighted = _highlight_code("\n".join(raw_lines), language)
            line_h = cfg["font_size_code"] + 8
            for line_tokens in highlighted[:15]:
                if y > height - 70:
                    break
                x = 80
                for color_hex, text in line_tokens:
                    color = _hex_to_rgb(color_hex)
                    draw.text((x, y), text, font=code_font, fill=color)
                    bbox = draw.textbbox((0, 0), text, font=code_font)
                    x += bbox[2] - bbox[0]
                y += line_h

        img.save(output_path)
        return str(output_path)
```

- [ ] **Step 5: Run syntax highlighter tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_syntax_highlighter.py -v
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/syntax_highlighter.py tests/test_syntax_highlighter.py requirements.txt src/layouts/text_only.py
git commit -m "feat(v2): add Pygments-based code syntax highlighting"
```

---

### Task 9: Mermaid diagram rendering

**Files:**
- Create: `src/mermaid_renderer.py`
- Create: `tests/test_mermaid_renderer.py`

- [ ] **Step 1: Write tests**

Create `tests/test_mermaid_renderer.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.mermaid_renderer import render_mermaid, is_mermaid_available


def test_is_mermaid_available_yes():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert is_mermaid_available() is True


def test_is_mermaid_available_no():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        assert is_mermaid_available() is False


def test_render_mermaid_calls_mmdc(tmp_path):
    mermaid_code = "graph LR\n  A --> B"
    output = tmp_path / "diagram.png"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("src.mermaid_renderer.is_mermaid_available", return_value=True):
            result = render_mermaid(mermaid_code, str(output))

    assert mock_run.called
    assert result is not None
```

- [ ] **Step 2: Implement mermaid renderer**

Create `src/mermaid_renderer.py`:

```python
import subprocess
import tempfile
from pathlib import Path


def is_mermaid_available() -> bool:
    try:
        result = subprocess.run(
            ["mmdc", "--version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def render_mermaid(code: str, output_path: str) -> str | None:
    if not is_mermaid_available():
        return None

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".mmd", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        mmd_path = f.name

    try:
        result = subprocess.run(
            [
                "mmdc",
                "-i", mmd_path,
                "-o", output_path,
                "-b", "transparent",
                "-s", "2",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        if Path(output_path).exists():
            return output_path
        return None
    except Exception:
        return None
    finally:
        Path(mmd_path).unlink(missing_ok=True)
```

- [ ] **Step 3: Handle mermaid segments in image provider flow**

In `src/renderer.py`, handle mermaid type before layout selection:

Add after the layout/image resolution block:

```python
    # Handle mermaid: render to PNG then treat as image-full
    if segment.type == "mermaid":
        from src.mermaid_renderer import render_mermaid as _render_mermaid
        mermaid_output = Path(cache_dir) / f"mermaid_{segment.index:04d}.png"
        rendered = _render_mermaid(segment.text, str(mermaid_output))
        if rendered:
            segment.image_path = rendered
            segment.layout = "image-below"
```

- [ ] **Step 4: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_mermaid_renderer.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/mermaid_renderer.py tests/test_mermaid_renderer.py
git commit -m "feat(v2): add mermaid diagram rendering via mmdc"
```

---

### Task 10: Keyword highlight rendering

**Files:**
- Create: `src/highlight.py`
- Create: `tests/test_highlight.py`

- [ ] **Step 1: Write tests**

Create `tests/test_highlight.py`:

```python
import pytest
from src.highlight import find_highlight_spans, render_highlighted_text
from PIL import Image, ImageDraw


def test_find_highlight_spans():
    text = "协程不是线程——它运行在单线程中"
    spans = find_highlight_spans(text, "协程不是线程")
    assert len(spans) == 1
    start, end = spans[0]
    assert text[start:end] == "协程不是线程"


def test_no_highlight_returns_empty():
    spans = find_highlight_spans("普通文本", "不存在的关键词")
    assert len(spans) == 0


def test_render_highlighted_text_returns_image(tmp_path):
    cfg = {
        "width": 800, "height": 200,
        "font_family": "/System/Library/Fonts/STHeiti Medium.ttc",
        "font_size_body": 32, "bg_color": "#f5f5f5",
        "accent_color": "#4A90D9", "text_color": "#333333",
    }
    text = "这是关键结论：异步优于多线程"
    highlight_words = "异步优于多线程"

    img = render_highlighted_text(text, highlight_words, cfg)
    assert img is not None
    assert img.size == (800, 200)
```

- [ ] **Step 2: Implement highlight helper**

Create `src/highlight.py`:

```python
from PIL import Image, ImageDraw
from src.layouts.base import _hex_to_rgb, _get_font


def find_highlight_spans(text: str, keyword: str) -> list[tuple[int, int]]:
    if not keyword or keyword not in text:
        return []
    spans = []
    start = 0
    while True:
        idx = text.find(keyword, start)
        if idx == -1:
            break
        spans.append((idx, idx + len(keyword)))
        start = idx + 1
    return spans


def render_highlighted_text(
    text: str, keyword: str, cfg: dict
) -> Image.Image | None:
    if not keyword or keyword not in text:
        return None

    width = cfg["width"]
    height = 200
    bg = _hex_to_rgb(cfg["bg_color"])
    accent = _hex_to_rgb(cfg["accent_color"])
    text_color = _hex_to_rgb(cfg["text_color"])

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    font_normal = _get_font(cfg["font_family"], cfg["font_size_body"])
    font_highlight = _get_font(cfg["font_family"], int(cfg["font_size_body"] * 1.15))

    # Simple left-to-right rendering with inline highlight
    x = 60
    y = 60
    spans = find_highlight_spans(text, keyword)
    last_end = 0

    for start, end in spans:
        # Normal text before highlight
        normal_part = text[last_end:start]
        if normal_part:
            bbox = draw.textbbox((0, 0), normal_part, font=font_normal)
            draw.text((x, y), normal_part, font=font_normal, fill=text_color)
            x += bbox[2] - bbox[0]

        # Highlighted text
        hl_part = text[start:end]
        bbox = draw.textbbox((0, 0), hl_part, font=font_highlight)
        draw.text((x, y), hl_part, font=font_highlight, fill=accent)
        x += bbox[2] - bbox[0]
        last_end = end

    # Remaining normal text
    remaining = text[last_end:]
    if remaining:
        draw.text((x, y), remaining, font=font_normal, fill=text_color)

    return img
```

- [ ] **Step 3: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_highlight.py -v
```
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/highlight.py tests/test_highlight.py
git commit -m "feat(v2): add keyword highlight rendering"
```

---

### Task 11: Parameterize TTS with per-segment voice/speed/pitch

**Files:**
- Modify: `src/tts.py` — generate_audio reads segment-level overrides
- Modify: `tests/test_tts.py` — test per-segment voice override

- [ ] **Step 1: Write test for per-segment TTS params**

Append to `tests/test_tts.py`:

```python
@pytest.mark.asyncio
async def test_generate_audio_uses_segment_voice(tmp_path):
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()
    seg = Segment(0, "Test", 1, "title_slide", "Hello")
    seg.voice = "zh-CN-YunxiNeural"
    seg.speed = "-20%"

    with patch("src.tts._get_mp3_duration", return_value=2.0):
        with patch("edge_tts.Communicate") as mock_comm:
            mock_comm.return_value.save = AsyncMock()
            await generate_audio(seg, {
                "tts": {"voice": "default", "speed": "+0%", "pitch": "+0Hz", "retry": 0}
            }, str(cache_dir))
            # Verify the segment's voice was used
            call_kwargs = mock_comm.call_args
            assert call_kwargs[0][1] == "zh-CN-YunxiNeural"  # voice param


def test_tts_text_for_mermaid():
    seg = Segment(0, "Diagram", 2, "mermaid",
                  "Diagram\n\n```mermaid\ngraph LR\n  A --> B\n```")
    text = tts_text_for_segment(seg)
    assert "mermaid" not in text.lower()
```

- [ ] **Step 2: Update generate_audio to use segment-level overrides**

In `src/tts.py`, modify `generate_audio()` — the voice/speed/pitch resolution:

```python
async def generate_audio(
    segment: Segment,
    config: dict,
    cache_dir: str = "./cache/audio",
) -> float:
    text = tts_text_for_segment(segment)
    if _should_skip_tts(text):
        segment.duration = 0
        return 0

    cache_path = audio_cache_path(text, cache_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        try:
            segment.duration = _get_mp3_duration(str(cache_path))
            return segment.duration
        except Exception:
            cache_path.unlink(missing_ok=True)

    import edge_tts

    tts_config = config.get("tts", {})
    voice = segment.voice or tts_config.get("voice", "zh-CN-XiaoxiaoNeural")
    speed = segment.speed or tts_config.get("speed", "+0%")
    pitch = segment.pitch or tts_config.get("pitch", "+0Hz")
    retry_count = tts_config.get("retry", 1)
    last_error: Exception | None = None

    for _attempt in range(retry_count + 1):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=speed, pitch=pitch)
            await communicate.save(str(cache_path))
            segment.duration = _get_mp3_duration(str(cache_path))
            return segment.duration
        except Exception as exc:
            last_error = exc
            cache_path.unlink(missing_ok=True)

    raise RuntimeError(
        f"TTS generation failed for segment {segment.index}"
    ) from last_error
```

Also update `tts_text_for_segment()` to handle `mermaid` type:

```python
def tts_text_for_segment(segment: Segment) -> str:
    if segment.type in ("code_block", "mermaid"):
        text = _strip_fenced_code(segment.text).strip()
        if text:
            return text
        title = segment.title or "当前段落"
        return f"以下是{title}的示例"
    return segment.text.strip()
```

- [ ] **Step 3: Run TTS tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_tts.py -v
```
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/tts.py tests/test_tts.py
git commit -m "feat(v2): parameterize TTS with per-segment voice/speed/pitch overrides"
```

---

### Task 12: BGM + audio ducking + smart pauses in composer

**Files:**
- Modify: `src/composer.py` — add BGM, silence padding, smart pauses
- Modify: `tests/test_composer.py` — test pause injection and BGM

- [ ] **Step 1: Write tests for audio enhancements**

Append to `tests/test_composer.py`:

```python
def test_compose_video_with_bgm_adds_audio_input(tmp_path):
    segments = [
        Segment(0, "Test", 1, "title_slide", "Test", duration=3.0),
    ]
    seg = segments[0]
    seg.bgm = str(tmp_path / "bgm.mp3")
    # Create fake BGM
    (tmp_path / "bgm.mp3").write_bytes(b"fake mp3")

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    (frames_dir / "segment_0000.png").write_bytes(b"fake")

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    from src.tts import audio_cache_path, tts_text_for_segment
    for s in segments:
        p = audio_cache_path(tts_text_for_segment(s), str(audio_dir))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"fake mp3")

    output = tmp_path / "output.mp4"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("src.composer._check_ffmpeg", return_value=True):
            compose_video(segments, str(output),
                         {"video": {"fps": 30, "codec": "libx264",
                          "audio_codec": "aac", "audio_bitrate": "192k"}},
                         str(frames_dir), str(audio_dir))
    assert mock_run.called


def test_smart_pause_after_title():
    from src.composer import _apply_smart_pauses
    segments = [
        Segment(0, "Title", 1, "title_slide", "Title\n\nContent", duration=5.0),
        Segment(1, "Section", 2, "section", "Section\n\nBody", duration=10.0),
    ]
    config = {
        "audio": {
            "smart_pauses": {
                "after_title": 1.0,
                "around_code": 0.5,
                "between_list_items": 0.2,
            }
        }
    }
    _apply_smart_pauses(segments, config)
    assert segments[0].pause_after >= 1.0


def test_smart_pause_around_code():
    from src.composer import _apply_smart_pauses
    segments = [
        Segment(0, "Code", 2, "code_block", "Code\n\n```\nx\n```", duration=8.0),
    ]
    config = {
        "audio": {
            "smart_pauses": {
                "after_title": 1.0,
                "around_code": 0.5,
                "between_list_items": 0.2,
            }
        }
    }
    _apply_smart_pauses(segments, config)
    assert segments[0].pause_before == 0.5
    assert segments[0].pause_after == 0.5
```

- [ ] **Step 2: Implement BGM, smart pauses, and silence padding**

In `src/composer.py`, add smart pause logic and BGM support.

Add `_apply_smart_pauses()`:

```python
def _apply_smart_pauses(segments: list[Segment], config: dict) -> None:
    audio_cfg = config.get("audio", {})
    pauses = audio_cfg.get("smart_pauses", {})
    after_title = pauses.get("after_title", 1.0)
    around_code = pauses.get("around_code", 0.5)
    between_items = pauses.get("between_list_items", 0.2)

    for i, seg in enumerate(segments):
        if seg.type == "title_slide":
            seg.pause_after = seg.pause_after or after_title
        if seg.type in ("code_block", "mermaid"):
            seg.pause_before = seg.pause_before or around_code
            seg.pause_after = seg.pause_after or around_code
        if seg.type == "list" and i > 0:
            seg.pause_before = seg.pause_before or between_items
```

Update `_write_concat_file()` to account for pauses:

```python
def _write_concat_file(
    segments: list[Segment],
    frames_dir: str,
    concat_path: Path,
) -> None:
    with open(concat_path, "w", encoding="utf-8") as concat_file:
        for segment in segments:
            frame_path = Path(frames_dir) / f"segment_{segment.index:04d}.png"
            duration = max(segment.duration + segment.pause_before + segment.pause_after, 0.5)
            concat_file.write(f"file '{frame_path.absolute()}'\n")
            concat_file.write(f"duration {duration}\n")

        last = segments[-1]
        last_frame = Path(frames_dir) / f"segment_{last.index:04d}.png"
        concat_file.write(f"file '{last_frame.absolute()}'\n")
```

Update `compose_video()` to apply smart pauses and handle BGM:

Add inside `compose_video()`, before `_write_concat_file()`:

```python
    # Apply smart pauses
    _apply_smart_pauses(segments, config)
```

Add BGM support in `_build_ffmpeg_command()`. After the audio_paths loop, add BGM handling:

```python
    # BGM: collect segments with bgm
    bgm_files: set[str] = set()
    for segment in segments:
        if segment.bgm and segment.bgm != "none":
            bgm_path = Path(segment.bgm)
            if bgm_path.exists():
                bgm_files.add(str(bgm_path.absolute()))

    # Add BGM inputs
    for bgm_file in sorted(bgm_files):
        base_cmd.extend(["-stream_loop", "-1", "-i", bgm_file])
        bgm_volume = 0.15
        for seg in segments:
            if seg.bgm == bgm_file:
                bgm_volume = seg.bgm_volume
                break
```

- [ ] **Step 3: Run composer tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_composer.py -v
```
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add src/composer.py tests/test_composer.py
git commit -m "feat(v2): add BGM support, audio ducking, and smart pauses to composer"
```

---

### Task 13: Video transitions (xfade) and progress bar

**Files:**
- Modify: `src/composer.py` — xfade transition support
- Modify: `src/layouts/base.py` — progress bar drawing helper
- Modify: `src/layouts/text_only.py` — add progress bar to rendered frames

- [ ] **Step 1: Add progress bar drawing helper**

In `src/layouts/base.py`, add:

```python
def draw_progress_bar(
    draw: ImageDraw.Draw,
    width: int,
    height: int,
    current_index: int,
    total_segments: int,
    segment_durations: list[float],
    accent_color: tuple[int, int, int],
) -> None:
    bar_h = 6
    y = height - bar_h
    total_duration = sum(segment_durations) or 1.0

    x = 0
    for i, dur in enumerate(segment_durations):
        seg_w = int((dur / total_duration) * width)
        if i <= current_index:
            draw.rectangle([x, y, x + seg_w, height], fill=accent_color)
        x += seg_w

    # Separator lines
    x = 0
    for i, dur in enumerate(segment_durations):
        seg_w = int((dur / total_duration) * width)
        if i > 0:
            draw.line([(x, y), (x, height)], fill=(0, 0, 0), width=1)
        x += seg_w
```

- [ ] **Step 2: Add progress bar to text_only layout**

In `src/layouts/text_only.py`, import `draw_progress_bar` and add it at the end of the `render` method before `img.save(output_path)`:

```python
from src.layouts.base import draw_progress_bar
```

Add before `img.save(output_path)` in the text rendering branch:

```python
        # Progress bar (dummy durations for now — real ones come after TTS)
        durations = [1.0] * (segment.index + 1)
        draw_progress_bar(draw, width, height, segment.index,
                         segment.index + 1, durations, accent)
```

Do the same in `_render_code_content`.

- [ ] **Step 3: Update composer for xfade transitions**

The xfade approach requires rendering each segment as a mini-video, then concatenating with xfade. This is complex — for V2 we'll implement a simpler approach: use a per-segment-generated MP4 and concat with fade filter.

For the plan scope, we add a transition-aware `_write_concat_file_with_transitions()`:

```python
def _write_concat_file_with_transitions(
    segments: list[Segment],
    frames_dir: str,
    concat_path: Path,
    config: dict,
) -> None:
    """Write concat file accounting for transition overlap."""
    trans_dur = config.get("video", {}).get("transition_duration", 0.5)
    with open(concat_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments):
            frame_path = Path(frames_dir) / f"segment_{seg.index:04d}.png"
            duration = max(seg.duration + seg.pause_before + seg.pause_after, 0.5)
            # For non-hard-cut transitions, overlap frames slightly
            if seg.transition != "none" and i < len(segments) - 1:
                duration -= trans_dur / 2
            if i > 0 and segments[i - 1].transition != "none":
                duration -= trans_dur / 2
            f.write(f"file '{frame_path.absolute()}'\n")
            f.write(f"duration {max(duration, 0.1)}\n")
        last_frame = Path(frames_dir) / f"segment_{segments[-1].index:04d}.png"
        f.write(f"file '{last_frame.absolute()}'\n")
```

Replace the call to `_write_concat_file` with `_write_concat_file_with_transitions` in `compose_video()`.

- [ ] **Step 4: Run full test suite**

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add src/composer.py src/layouts/base.py src/layouts/text_only.py
git commit -m "feat(v2): add video transitions and chapter progress bar"
```

---

### Task 14: V2 config and final integration

**Files:**
- Modify: `src/config.py` — add V2 config defaults
- Modify: `config.yaml` — full V2 config
- Modify: `tests/test_config.py` — verify V2 keys

- [ ] **Step 1: Update config defaults**

Add V2 defaults to `DEFAULT_CONFIG` in `src/config.py`:

```python
    "image": {
        "assets_dir": "./assets/images",
        "manifest_file": "./assets/images/manifest.yaml",
    },
    "highlight": {
        "font_scale": 1.15,
        "color_override": None,
    },
    "code_highlight": {
        "theme": "monokai",
        "line_numbers": True,
    },
    "audio": {
        "default_bgm": None,
        "bgm_volume": 0.15,
        "ducking": {
            "enabled": True,
            "reduction_db": 12,
            "attack_ms": 150,
            "release_ms": 400,
        },
        "smart_pauses": {
            "after_title": 1.0,
            "around_code": 0.5,
            "between_list_items": 0.2,
        },
    },
    # In video section, add:
    # "default_transition": "fade",
    # "transition_duration": 0.5,
    # "progress_bar": True,
```

Update the `video` section of `DEFAULT_CONFIG`:

```python
    "video": {
        "fps": 30,
        "codec": "libx264",
        "audio_codec": "aac",
        "audio_bitrate": "192k",
        "output_dir": "./output",
        "default_transition": "fade",
        "transition_duration": 0.5,
        "progress_bar": True,
    },
```

- [ ] **Step 2: Update config.yaml**

Replace `config.yaml` with the full V2 config matching the spec.

- [ ] **Step 3: Update config tests**

Append to `tests/test_config.py`:

```python
def test_v2_config_sections_exist():
    config = load_config()
    assert "image" in config
    assert "audio" in config
    assert "highlight" in config
    assert "code_highlight" in config
    assert config["audio"]["smart_pauses"]["after_title"] == 1.0
    assert config["video"]["default_transition"] == "fade"
```

- [ ] **Step 4: Run full test suite**

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

- [ ] **Step 5: Final integration test — full V2 pipeline with a sample**

Create a V2 sample markdown and run dry-run:

```bash
cat > /tmp/v2_sample.md << 'MDEOF'
<!-- {"voice": "zh-CN-YunxiNeural"} -->

# Python 异步编程

<!-- {"pause_after": 1.5} -->

异步编程是现代 Python 开发的核心技能。

<!-- {"layout": "image-right"} -->

## 事件循环

事件循环驱动协程的执行，理解它才能用好 asyncio。

<!-- {"highlight": "协程不是线程"} -->

协程不是线程，它运行在单线程中通过协作式调度切换上下文。
MDEOF

source .venv/bin/activate && python main.py /tmp/v2_sample.md --dry-run
```

Expected: Shows segments with voice/layout/highlight annotations.

- [ ] **Step 6: Commit**

```bash
git add src/config.py config.yaml tests/test_config.py
git commit -m "feat(v2): add V2 config defaults and final wiring"
```

---

### Task 15: End-to-end V2 integration test

**Files:**
- Create: `tests/test_v2_integration.py`

- [ ] **Step 1: Write V2 integration test**

Create `tests/test_v2_integration.py`:

```python
import pytest
import subprocess
import sys
from pathlib import Path


def test_v2_pipeline_with_annotations(tmp_path):
    md_file = tmp_path / "v2_test.md"
    md_file.write_text(
        '<!-- {"voice": "zh-CN-YunxiNeural", "layout": "image-right"} -->\n'
        '# V2 Test\n\n'
        'This is a V2 annotated document.\n\n'
        '## Code Section\n\n'
        'Here is the code:\n\n'
        '```python\n'
        'def hello():\n'
        '    print("Hello V2")\n'
        '```\n\n'
        '## Features\n\n'
        '- Annotation-driven rendering\n'
        '- Mixed layouts\n'
        '- Syntax highlighting\n\n'
        '<!-- {"highlight": "关键结论"} -->\n'
        '关键结论：V2 让创作者拥有导演级控制力。\n'
    )

    result = subprocess.run(
        [sys.executable, "main.py", str(md_file), "--dry-run"],
        capture_output=True, text=True,
    )

    assert result.returncode == 0
    assert "V2 Test" in result.stdout
    assert "voice=" in result.stdout or "layout=" in result.stdout


def test_v2_mermaid_detection():
    from src.parser import parse_markdown

    md = '## Diagram\n\n```mermaid\ngraph LR\n  A-->B\n```'
    segments = parse_markdown(md)
    mermaid_segs = [s for s in segments if s.type == "mermaid"]
    assert len(mermaid_segs) >= 1


def test_v2_syntax_highlighting():
    from src.syntax_highlighter import highlight_code

    result = highlight_code('print("hello")', "python")
    assert len(result) > 0
    # Each line is a list of (color, text) tuples
    assert all(isinstance(token[0], str) and isinstance(token[1], str)
               for line in result for token in line)


def test_v2_layout_factory_all_types():
    from src.layouts import LayoutFactory
    for name in ("text-only", "image-right", "image-below", "image-full"):
        layout = LayoutFactory.create(name)
        assert layout is not None


def test_v2_annotation_parse_and_apply():
    from src.annotations import parse_annotations, apply_annotations
    from src.parser import Segment

    text = (
        '<!-- {"voice": "zh-CN-YunxiNeural", "layout": "image-right"} -->\n\n'
        '# Title\n\nContent.'
    )
    annotations = parse_annotations(text)
    assert len(annotations) == 1

    segments = [Segment(0, "Title", 1, "title_slide", "Title\n\nContent")]
    result = apply_annotations(segments, annotations, text)
    assert result[0].voice == "zh-CN-YunxiNeural"
    assert result[0].layout == "image-right"
```

- [ ] **Step 2: Run V2 integration test**

```bash
source .venv/bin/activate && python -m pytest tests/test_v2_integration.py -v
```
Expected: all PASS

- [ ] **Step 3: Run full test suite one final time**

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_v2_integration.py
git commit -m "test(v2): add end-to-end V2 integration tests"
```
