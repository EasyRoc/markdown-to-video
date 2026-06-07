from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlparse

import mistune

from src.annotations import (
    apply_annotations,
    parse_annotations as _parse_annotations,
    strip_annotation_comments,
)


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
    svg_code: str | None = None


def parse_markdown(
    text: str,
    max_chars_per_segment: int = 200,
    source_dir: str | Path | None = None,
) -> list[Segment]:
    if not text.strip():
        return []

    annotations = _parse_annotations(text)
    clean_text = strip_annotation_comments(text)

    markdown = mistune.create_markdown(renderer="ast", plugins=["table"])
    ast = markdown(clean_text)

    segments: list[Segment] = []
    current: Segment | None = None

    for node in ast:
        node_type = node["type"]

        if node_type == "heading":
            if current is not None:
                segments.append(current)
            title = _extract_text(node).strip()
            level = node["attrs"]["level"]
            current = Segment(
                index=len(segments),
                title=title,
                level=level,
                type="title_slide" if level == 1 else "section",
                text=title,
            )
            continue

        if node_type == "paragraph":
            current = _ensure_segment(current, segments)
            _append_text(current, _extract_text(node).strip())
            image_url = _extract_first_image_url(node)
            if image_url and not current.image_path:
                current.image_path = _resolve_markdown_image_url(image_url, source_dir)
                if current.layout == "text-only":
                    current.layout = "image-below"
            continue

        if node_type == "block_code":
            current = _ensure_segment(current, segments)
            info = node.get("attrs", {}).get("info", "")
            seg_type = "mermaid" if info.strip().lower() == "mermaid" else "code_block"
            fence = f"```{info}".rstrip()
            _append_text(current, f"{fence}\n{node.get('raw', '').rstrip()}\n```")
            current.type = seg_type
            continue

        if node_type == "list":
            current = _ensure_segment(current, segments)
            _append_text(current, _extract_list_text(node))
            current.type = "list"
            continue

        if node_type == "block_quote":
            current = _ensure_segment(current, segments)
            _append_text(current, _extract_text(node).strip())
            continue

        if node_type == "table":
            current = _table_segment(current, segments, _extract_table_data(node))
            continue

        if node_type == "thematic_break" and current is not None:
            segments.append(current)
            current = None

    if current is not None:
        segments.append(current)

    segments = _split_long_segments(segments, max_chars_per_segment)
    for index, segment in enumerate(segments):
        segment.index = index
    segments = apply_annotations(segments, annotations, clean_text)
    return segments


def _ensure_segment(current: Segment | None, segments: list[Segment]) -> Segment:
    if current is not None:
        return current
    return Segment(index=len(segments), title="", level=0, type="section", text="")


def _append_text(segment: Segment, text: str) -> None:
    if not text:
        return
    if segment.text:
        segment.text += "\n\n" + text
    else:
        segment.text = text


def _extract_text(node: dict) -> str:
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


def _extract_first_image_url(node: dict) -> str | None:
    if node.get("type") == "image":
        return node.get("attrs", {}).get("url")
    for child in node.get("children", []) or []:
        url = _extract_first_image_url(child)
        if url:
            return url
    return None


def _resolve_markdown_image_url(image_url: str, source_dir: str | Path | None) -> str:
    parsed = urlparse(image_url)
    if parsed.scheme or source_dir is None:
        return image_url

    path = Path(image_url).expanduser()
    if path.is_absolute():
        return str(path)
    return str((Path(source_dir) / path).resolve())


def _extract_list_text(node: dict) -> str:
    lines = []
    for item in node.get("children", []):
        text = " ".join(_extract_text(item).split())
        if text:
            lines.append(f"* {text}")
    return "\n".join(lines)


def _extract_table_data(node: dict) -> list[list[str]]:
    rows: list[list[str]] = []
    for child in node.get("children", []) or []:
        child_type = child["type"]
        if child_type == "table_head":
            rows.append(
                [_extract_text(cell).strip() for cell in child.get("children", [])]
            )
        elif child_type == "table_body":
            for row in child.get("children", []) or []:
                rows.append(
                    [_extract_text(cell).strip() for cell in row.get("children", [])]
                )
    return rows


def _table_segment(
    current: Segment | None,
    segments: list[Segment],
    table_data: list[list[str]],
) -> Segment:
    title = current.title if current is not None else ""
    level = current.level if current is not None else 0
    if (
        current is not None
        and current.text.strip()
        and current.text.strip() != current.title
    ):
        segments.append(current)
        current = None

    segment = _ensure_segment(current, segments)
    if title and not segment.title:
        segment.title = title
        segment.level = level
    segment.type = "table"
    segment.layout = "table"
    segment.table_data = table_data
    segment.text = _table_summary_text(segment.title, table_data)
    return segment


def _table_summary_text(title: str, table_data: list[list[str]]) -> str:
    columns = len(table_data[0]) if table_data else 0
    data_rows = max(0, len(table_data) - 1)
    summary = f"这张表格包含 {columns} 列、{data_rows} 行数据。"
    return f"{title}\n\n{summary}".strip() if title else summary


def _split_long_segments(
    segments: list[Segment],
    max_chars: int,
) -> list[Segment]:
    if max_chars <= 0:
        return segments

    result: list[Segment] = []
    for segment in segments:
        if len(segment.text) <= max_chars:
            result.append(segment)
            continue

        chunks = _split_text(segment.text, max_chars)
        for chunk in chunks:
            result.append(_copy_segment_with_text(segment, chunk))
    return result


def _copy_segment_with_text(segment: Segment, text: str) -> Segment:
    return Segment(
        index=0,
        title=segment.title,
        level=segment.level,
        type=segment.type,
        text=text,
        duration=segment.duration,
        voice=segment.voice,
        speed=segment.speed,
        pitch=segment.pitch,
        image_path=segment.image_path,
        layout=segment.layout,
        pause_before=segment.pause_before,
        pause_after=segment.pause_after,
        highlight=segment.highlight,
        bgm=segment.bgm,
        bgm_volume=segment.bgm_volume,
        transition=segment.transition,
        table_data=segment.table_data,
        svg_code=segment.svg_code,
    )


def _split_text(text: str, max_chars: int) -> list[str]:
    parts = [part for part in re.split(r"(?<=[。！？.!?])\s*", text) if part]
    if not parts:
        return [text]

    chunks: list[str] = []
    current = ""
    for part in parts:
        if current and len(current) + len(part) + 1 > max_chars:
            chunks.append(current.strip())
            current = part
        elif len(part) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(
                part[index : index + max_chars]
                for index in range(0, len(part), max_chars)
            )
        else:
            current = f"{current} {part}".strip() if current else part

    if current.strip():
        chunks.append(current.strip())
    return chunks
