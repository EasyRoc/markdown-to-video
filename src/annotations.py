import json
import re


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
            target_line = _first_non_empty_line_after(text, match.end())
            results.append((target_line, data))
    return results


def apply_annotations(
    segments: list,
    annotations: list[tuple[int, dict]],
    text: str,
) -> list:
    if not segments:
        return segments

    _ensure_segment_defaults(segments)
    if not annotations:
        return segments

    line_ranges = _compute_segment_line_ranges(segments, text.splitlines())
    used_indexes: set[int] = set()

    for annotation_line, annotation in annotations:
        segment_index = _find_target_segment_index(annotation_line, line_ranges)
        if segment_index is None:
            segment_index = _first_unused_segment_index(segments, used_indexes)
        if segment_index is None:
            continue
        _fill_segment_from_annotation(segments[segment_index], annotation)
        used_indexes.add(segment_index)

    return segments


def strip_annotation_comments(text: str) -> str:
    def replace(match: re.Match) -> str:
        return "\n" * match.group(0).count("\n")

    return ANNOTATION_PATTERN.sub(replace, text)


def _first_non_empty_line_after(text: str, offset: int) -> int:
    line_number = text[:offset].count("\n") + 1
    remainder = text[offset:].splitlines()
    for index, line in enumerate(remainder):
        if line.strip():
            return line_number + index
    return line_number


def _ensure_segment_defaults(segments: list) -> None:
    for segment in segments:
        for key, value in ANNOTATION_DEFAULTS.items():
            attr = "image_path" if key == "image" else key
            if not hasattr(segment, attr):
                setattr(segment, attr, value)


def _compute_segment_line_ranges(segments: list, lines: list[str]) -> dict[int, tuple[int, int]]:
    starts: dict[int, int] = {}
    search_from = 0
    for segment in segments:
        start = _find_segment_start(segment, lines, search_from)
        starts[segment.index] = start
        search_from = max(start, search_from)

    ranges: dict[int, tuple[int, int]] = {}
    ordered = sorted(starts.items())
    for position, (index, start) in enumerate(ordered):
        if position + 1 < len(ordered):
            end = ordered[position + 1][1] - 1
        else:
            end = len(lines) or start
        ranges[index] = (start, max(start, end))
    return ranges


def _find_segment_start(segment, lines: list[str], search_from: int) -> int:
    title = (segment.title or "").strip()
    if title:
        heading_pattern = re.compile(r"^#{1,6}\s+" + re.escape(title) + r"\s*$")
        for offset in range(search_from, len(lines)):
            line = lines[offset].strip()
            if line == title or heading_pattern.match(line):
                return offset + 1

    first_text = ""
    for line in segment.text.splitlines():
        if line.strip():
            first_text = line.strip()
            break
    if first_text:
        for offset in range(search_from, len(lines)):
            if first_text in lines[offset].strip():
                return offset + 1
    return search_from + 1


def _find_target_segment_index(
    annotation_line: int,
    line_ranges: dict[int, tuple[int, int]],
) -> int | None:
    for index, (start, end) in sorted(line_ranges.items()):
        if start <= annotation_line <= end:
            return index
        if annotation_line < start:
            return index
    return None


def _first_unused_segment_index(segments: list, used_indexes: set[int]) -> int | None:
    for segment in segments:
        if segment.index not in used_indexes:
            return segment.index
    return None


def _fill_segment_from_annotation(segment, annotation: dict) -> None:
    for key, default in ANNOTATION_DEFAULTS.items():
        attr = "image_path" if key == "image" else key
        if key in annotation:
            setattr(segment, attr, annotation[key])
        elif not hasattr(segment, attr):
            setattr(segment, attr, default)
