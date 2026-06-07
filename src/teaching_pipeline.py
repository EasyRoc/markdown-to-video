import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

from src.document_model import build_document_model
from src.llm_client import LLMClient, LLMError
from src.outline_planner import OutlinePlanner
from src.scene_adapter import storyboard_to_segments
from src.scene_generator import SceneGenerator
from src.storyboard import build_storyboard
from src.storyboard_io import write_teaching_artifacts
from src.teaching_models import (
    DocumentModel,
    Scene,
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

    except Exception as exc:
        print(f"LLM pipeline failed ({exc}), falling back to rules planner", file=sys.stderr)
        return _build_with_rules(text, config, source_dir)


def _extract_section_texts(document: DocumentModel, outline) -> list[str]:
    """Match outline sections to DocumentModel sections and extract text content."""
    result = []
    for ol_sec in outline.sections:
        matched = ""
        for doc_sec in document.sections:
            if doc_sec.heading == ol_sec.heading:
                matched = "\n\n".join(
                    b.text for b in doc_sec.blocks if b.text.strip()
                )
                break
        if not matched:
            for doc_sec in document.sections:
                if ol_sec.heading in doc_sec.heading:
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
