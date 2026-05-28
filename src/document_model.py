import hashlib
from typing import Any

import mistune

from src.annotations import ANNOTATION_DEFAULTS, strip_annotation_comments
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
    current_segment: Segment | None = None
    segment_cursor = 0

    for node in ast:
        node_type = node["type"]
        if node_type == "heading":
            heading = _extract_text(node).strip()
            level = node.get("attrs", {}).get("level", 0)
            segment = _find_segment_for_heading(heading, segments, segment_cursor)
            current_segment = segment
            if segment is not None:
                segment_cursor = segment.index + 1
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

        block = _block_from_node(node, segments, current_segment, segment_cursor)
        if block is None:
            continue
        if current is None:
            current = DocumentSection(heading="", level=0)
            model.sections.append(current)
        if block.source_segment_index >= 0 and not current.annotations:
            segment = segments[block.source_segment_index]
            current.annotations = _segment_annotations(segment)
            current.source_segment_index = segment.index
            current_segment = segment
        if block.source_segment_index >= 0:
            segment_cursor = max(segment_cursor, block.source_segment_index + 1)
        current.blocks.append(block)

    return model


def _block_from_node(
    node: dict[str, Any],
    segments: list[Segment],
    current_segment: Segment | None,
    segment_cursor: int,
) -> DocumentBlock | None:
    node_type = node["type"]
    if node_type == "paragraph":
        text = _extract_text(node).strip()
        return _make_block("paragraph", text, segments, current_segment, segment_cursor)
    if node_type == "block_code":
        language = _code_language(node)
        raw = node.get("raw", "")
        kind = "mermaid" if language.lower() == "mermaid" else "code"
        return _make_block(
            kind,
            raw,
            segments,
            current_segment,
            segment_cursor,
            language=language,
        )
    if node_type == "list":
        items = _extract_list_items(node)
        text = "\n".join(f"* {item}" for item in items)
        block = _make_block("list", text, segments, current_segment, segment_cursor)
        block.list_items = items
        return block
    if node_type == "block_quote":
        return _make_block(
            "quote",
            _extract_text(node).strip(),
            segments,
            current_segment,
            segment_cursor,
        )
    return None


def _make_block(
    kind: str,
    text: str,
    segments: list[Segment],
    current_segment: Segment | None,
    segment_cursor: int,
    language: str = "",
) -> DocumentBlock:
    segment = _find_segment_containing(text, segments, current_segment, segment_cursor)
    return DocumentBlock(
        kind=kind,
        text=text,
        language=language,
        source_segment_index=segment.index if segment else -1,
        annotations=_segment_annotations(segment),
    )


def _find_segment_for_heading(
    heading: str,
    segments: list[Segment],
    start_index: int,
) -> Segment | None:
    for segment in segments[start_index:]:
        if segment.title == heading:
            return segment
    return None


def _find_segment_containing(
    text: str,
    segments: list[Segment],
    current_segment: Segment | None,
    start_index: int,
) -> Segment | None:
    if not text:
        return None
    needle = text.strip().splitlines()[0].strip()
    if current_segment is not None and needle and needle in current_segment.text:
        return current_segment
    for segment in segments[start_index:]:
        if needle and needle in segment.text:
            return segment
    return None


def _segment_annotations(segment: Segment | None) -> dict[str, Any]:
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
        if value != ANNOTATION_DEFAULTS[key]
    }


def _code_language(node: dict[str, Any]) -> str:
    info = node.get("attrs", {}).get("info", "").strip()
    return info.split(maxsplit=1)[0] if info else ""


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
