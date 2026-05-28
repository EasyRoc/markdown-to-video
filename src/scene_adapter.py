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
