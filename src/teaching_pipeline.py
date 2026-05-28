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
