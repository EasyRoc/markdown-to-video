from dataclasses import dataclass
import re

import mistune


@dataclass
class Segment:
    index: int
    title: str
    level: int
    type: str
    text: str
    duration: float = 0


def parse_markdown(text: str, max_chars_per_segment: int = 200) -> list[Segment]:
    if not text.strip():
        return []

    markdown = mistune.create_markdown(renderer="ast")
    ast = markdown(text)

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
            continue

        if node_type == "block_code":
            current = _ensure_segment(current, segments)
            info = node.get("attrs", {}).get("info", "")
            fence = f"```{info}".rstrip()
            _append_text(current, f"{fence}\n{node.get('raw', '').rstrip()}\n```")
            current.type = "code_block"
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

        if node_type == "thematic_break" and current is not None:
            segments.append(current)
            current = None

    if current is not None:
        segments.append(current)

    segments = _split_long_segments(segments, max_chars_per_segment)
    for index, segment in enumerate(segments):
        segment.index = index
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


def _extract_list_text(node: dict) -> str:
    lines = []
    for item in node.get("children", []):
        text = " ".join(_extract_text(item).split())
        if text:
            lines.append(f"* {text}")
    return "\n".join(lines)


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
            result.append(
                Segment(
                    index=0,
                    title=segment.title,
                    level=segment.level,
                    type=segment.type,
                    text=chunk,
                    duration=segment.duration,
                )
            )
    return result


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
