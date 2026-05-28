from src.teaching_models import (
    Scene,
    ScriptSection,
    Storyboard,
    TeachingScript,
    VisualInstruction,
)


def build_storyboard(script: TeachingScript, config: dict | None = None) -> Storyboard:
    director_config = (config or {}).get("teaching_director", {})
    max_per_section = director_config.get("max_scenes_per_section", 6)
    diagrams_enabled = director_config.get("diagrams", {}).get("enabled", True)
    code_focus_enabled = director_config.get("code_focus", {}).get("enabled", True)
    storyboard = Storyboard(
        title=script.title,
        planner=script.planner,
        source_hash=script.source_hash,
    )
    counter = 1
    if script.title:
        storyboard.scenes.append(
            _scene(
                counter,
                "title",
                script.title,
                -1,
                script.title,
                VisualInstruction("text", script.title, script.title),
                3.0,
                {},
            )
        )
        counter += 1

    for section in script.sections:
        section_scenes = _section_scenes(
            section,
            counter,
            diagrams_enabled=diagrams_enabled,
            code_focus_enabled=code_focus_enabled,
        )
        section_scenes = section_scenes[:max_per_section]
        storyboard.scenes.extend(section_scenes)
        counter += len(section_scenes)
    return storyboard


def _section_scenes(
    section: ScriptSection,
    start_counter: int,
    diagrams_enabled: bool,
    code_focus_enabled: bool,
) -> list[Scene]:
    scenes: list[Scene] = []
    counter = start_counter

    scenes.append(
        _scene(
            counter,
            "objective",
            section.heading,
            0,
            section.objective,
            VisualInstruction("callout", section.heading or "本节目标", section.objective),
            4.0,
            section.annotations,
        )
    )
    counter += 1

    for index, narration in enumerate(section.narration_blocks):
        scenes.append(
            _scene(
                counter,
                "concept",
                section.heading,
                index,
                narration,
                VisualInstruction(
                    "text",
                    section.heading or "概念讲解",
                    narration,
                    highlights=section.key_points[:2],
                ),
                _duration_hint(narration),
                section.annotations,
            )
        )
        counter += 1

    if diagrams_enabled:
        for candidate in section.diagram_candidates:
            scenes.append(
                _scene(
                    counter,
                    "diagram",
                    section.heading,
                    0,
                    f"这张图展示 {section.heading or '当前内容'} 的流程关系。",
                    VisualInstruction("mermaid", candidate.title, candidate.mermaid),
                    5.0,
                    section.annotations,
                )
            )
            counter += 1

    for explanation in section.code_explanations:
        scenes.append(
            _scene(
                counter,
                "code_overview",
                section.heading,
                0,
                explanation.overview,
                VisualInstruction(
                    "code",
                    section.heading or "代码概览",
                    explanation.code,
                    language=explanation.language,
                ),
                5.0,
                section.annotations,
            )
        )
        counter += 1
        if code_focus_enabled:
            for focus in explanation.focus_lines:
                scenes.append(
                    _scene(
                        counter,
                        "code_focus",
                        section.heading,
                        int(focus["line_number"]),
                        str(focus["explanation"]),
                        VisualInstruction(
                            "code",
                            f"第 {focus['line_number']} 行",
                            explanation.code,
                            highlights=[str(focus["code"])],
                            language=explanation.language,
                        ),
                        4.5,
                        section.annotations,
                    )
                )
                counter += 1

    if section.summary:
        scenes.append(
            _scene(
                counter,
                "summary",
                section.heading,
                0,
                section.summary,
                VisualInstruction("callout", "小结", section.summary),
                4.0,
                section.annotations,
            )
        )
    return scenes


def _scene(
    counter: int,
    kind: str,
    source_section: str,
    source_block_index: int,
    narration: str,
    visual: VisualInstruction,
    duration_hint: float,
    annotations: dict,
) -> Scene:
    return Scene(
        id=f"scene-{counter:03d}",
        kind=kind,
        source_section=source_section,
        source_block_index=source_block_index,
        narration=narration,
        visual=visual,
        duration_hint=duration_hint,
        annotations=dict(annotations),
    )


def _duration_hint(text: str) -> float:
    return max(3.0, min(10.0, len(text) / 14))
