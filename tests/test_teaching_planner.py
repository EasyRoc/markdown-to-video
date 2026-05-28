from src.document_model import build_document_model
from src.teaching_planner import RulesTeachingPlanner, create_teaching_planner


def test_rules_planner_generates_objective_narration_and_summary():
    model = build_document_model(
        "## Event Loop\n\n"
        "The event loop receives tasks, schedules callbacks, and resumes coroutines."
    )

    script = RulesTeachingPlanner().plan(model)

    section = script.sections[0]
    assert script.planner == "rules"
    assert section.objective == "本节目标：理解 Event Loop。"
    assert "event loop" in section.narration_blocks[0].lower()
    assert section.summary == "小结：Event Loop 的核心是理解主要概念和使用场景。"


def test_rules_planner_extracts_code_explanation_focus_lines():
    model = build_document_model(
        "## Async Example\n\n"
        "```python\n"
        "async def main():\n"
        "    await fetch_data()\n"
        "    print('done')\n"
        "```"
    )

    script = RulesTeachingPlanner().plan(model)

    explanation = script.sections[0].code_explanations[0]
    assert explanation.language == "python"
    assert explanation.overview == "这段 python 代码展示了 Async Example 的一个实现片段。"
    assert explanation.focus_lines[0]["line_number"] == 1
    assert "async def main" in explanation.focus_lines[0]["code"]
    assert any("await" in item["code"] for item in explanation.focus_lines)


def test_rules_planner_creates_diagram_candidate_for_process_text():
    model = build_document_model(
        "## Pipeline\n\n"
        "输入内容会进入解析流程，然后调用渲染模块，最后输出视频。"
    )

    script = RulesTeachingPlanner().plan(model)

    candidate = script.sections[0].diagram_candidates[0]
    assert candidate.title == "Pipeline 流程图"
    assert "graph LR" in candidate.mermaid
    assert "输入" in candidate.mermaid


def test_create_teaching_planner_falls_back_to_rules_for_llm_config():
    planner = create_teaching_planner(
        {
            "teaching_director": {
                "planner": "llm",
                "llm": {"enabled": True},
            }
        }
    )

    assert isinstance(planner, RulesTeachingPlanner)


def test_rules_planner_respects_max_focus_lines_config():
    model = build_document_model(
        "## Example\n\n"
        "```python\n"
        "a = 1\n"
        "b = 2\n"
        "c = 3\n"
        "```"
    )
    planner = RulesTeachingPlanner(
        {"teaching_director": {"code_focus": {"max_focus_lines": 2}}}
    )

    script = planner.plan(model)

    assert len(script.sections[0].code_explanations[0].focus_lines) == 2
