from src.document_model import build_document_model
from src.storyboard import build_storyboard
from src.teaching_planner import RulesTeachingPlanner


def _script_from_markdown(markdown: str):
    return RulesTeachingPlanner().plan(build_document_model(markdown))


def test_storyboard_adds_title_objective_concept_and_summary_scenes():
    script = _script_from_markdown(
        "# Demo\n\n"
        "Intro text.\n\n"
        "## Install\n\n"
        "Install the package before running examples."
    )

    storyboard = build_storyboard(script)

    kinds = [scene.kind for scene in storyboard.scenes]
    assert kinds[0] == "title"
    assert "objective" in kinds
    assert "concept" in kinds
    assert "summary" in kinds
    assert storyboard.scenes[0].visual.title == "Demo"


def test_storyboard_expands_code_into_overview_focus_and_summary():
    script = _script_from_markdown(
        "## Async Example\n\n"
        "```python\n"
        "async def main():\n"
        "    await fetch_data()\n"
        "    print('done')\n"
        "```"
    )

    storyboard = build_storyboard(script)

    code_kinds = [scene.kind for scene in storyboard.scenes if scene.kind.startswith("code")]
    assert code_kinds == ["code_overview", "code_focus", "code_focus", "code_focus"]
    assert storyboard.scenes[1].visual.type == "code"
    assert "async def main" in storyboard.scenes[2].visual.payload


def test_storyboard_adds_diagram_scene_for_diagram_candidate():
    script = _script_from_markdown(
        "## Pipeline\n\n"
        "输入内容会进入解析流程，然后调用渲染模块，最后输出视频。"
    )

    storyboard = build_storyboard(script)

    diagram = [scene for scene in storyboard.scenes if scene.kind == "diagram"][0]
    assert diagram.visual.type == "mermaid"
    assert "graph LR" in diagram.visual.payload


def test_storyboard_respects_max_scenes_per_section():
    script = _script_from_markdown(
        "## Long Code\n\n"
        "```python\n"
        "a = 1\n"
        "b = 2\n"
        "c = 3\n"
        "d = 4\n"
        "e = 5\n"
        "```"
    )

    storyboard = build_storyboard(
        script,
        {"teaching_director": {"max_scenes_per_section": 3}},
    )

    section_scenes = [scene for scene in storyboard.scenes if scene.source_section == "Long Code"]
    assert len(section_scenes) == 3


def test_storyboard_can_disable_diagrams_and_code_focus():
    script = _script_from_markdown(
        "## Pipeline\n\n"
        "输入内容会进入解析流程，然后调用渲染模块，最后输出视频。\n\n"
        "```python\n"
        "a = 1\n"
        "b = 2\n"
        "```"
    )

    storyboard = build_storyboard(
        script,
        {
            "teaching_director": {
                "diagrams": {"enabled": False},
                "code_focus": {"enabled": False},
            }
        },
    )

    kinds = [scene.kind for scene in storyboard.scenes]
    assert "diagram" not in kinds
    assert "code_focus" not in kinds
    assert "code_overview" in kinds
