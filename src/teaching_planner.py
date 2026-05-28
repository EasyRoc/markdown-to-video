import re

from src.teaching_models import (
    CodeExplanation,
    DiagramCandidate,
    DocumentBlock,
    DocumentModel,
    ScriptSection,
    TeachingScript,
)


PROCESS_KEYWORDS = ("流程", "步骤", "架构", "调用", "队列", "输入", "输出", "pipeline", "flow")


class RulesTeachingPlanner:
    name = "rules"

    def __init__(self, config: dict | None = None):
        director_config = (config or {}).get("teaching_director", {})
        code_focus = director_config.get("code_focus", {})
        self.max_focus_lines = int(code_focus.get("max_focus_lines", 4))

    def plan(self, document: DocumentModel) -> TeachingScript:
        script = TeachingScript(
            title=document.title,
            planner=self.name,
            source_hash=document.source_hash,
        )
        for section in document.sections:
            script.sections.append(
                ScriptSection(
                    heading=section.heading,
                    objective=_objective_for_heading(section.heading),
                    key_points=_key_points_for_blocks(section.blocks),
                    narration_blocks=_narration_for_blocks(section.blocks),
                    code_explanations=[
                        _code_explanation(
                            section.heading,
                            block,
                            max_focus_lines=self.max_focus_lines,
                        )
                        for block in section.blocks
                        if block.kind == "code"
                    ],
                    diagram_candidates=[
                        _diagram_candidate(section.heading, block)
                        for block in section.blocks
                        if _is_diagram_candidate(block)
                    ],
                    summary=_summary_for_heading(section.heading),
                    annotations=section.annotations,
                )
            )
        return script


def create_teaching_planner(config: dict | None = None) -> RulesTeachingPlanner:
    return RulesTeachingPlanner(config)


def _objective_for_heading(heading: str) -> str:
    if heading:
        return f"本节目标：理解 {heading}。"
    return "本节目标：理解当前内容的核心概念。"


def _summary_for_heading(heading: str) -> str:
    name = heading or "当前内容"
    return f"小结：{name} 的核心是理解主要概念和使用场景。"


def _key_points_for_blocks(blocks: list[DocumentBlock]) -> list[str]:
    points: list[str] = []
    for block in blocks:
        if block.kind == "list":
            points.extend(block.list_items[:4])
        elif block.kind == "paragraph":
            first = _first_sentence(block.text)
            if first:
                points.append(first)
        if len(points) >= 4:
            break
    return points[:4]


def _narration_for_blocks(blocks: list[DocumentBlock]) -> list[str]:
    narration: list[str] = []
    for block in blocks:
        if block.kind == "paragraph" and block.text.strip():
            narration.append(_spoken_text(block.text))
        elif block.kind == "list" and block.list_items:
            narration.append("这里有几个重点：" + "；".join(block.list_items) + "。")
    return narration


def _code_explanation(
    heading: str,
    block: DocumentBlock,
    max_focus_lines: int,
) -> CodeExplanation:
    language = block.language or "code"
    title = heading or "当前主题"
    lines = [line for line in block.text.splitlines() if line.strip()]
    focus_lines = []
    for index, line in enumerate(lines[:max_focus_lines], start=1):
        focus_lines.append(
            {
                "line_number": index,
                "code": line,
                "explanation": _line_explanation(line),
            }
        )
    return CodeExplanation(
        language=language,
        code=block.text,
        overview=f"这段 {language} 代码展示了 {title} 的一个实现片段。",
        focus_lines=focus_lines,
        summary="这段代码的重点是看清执行顺序、关键调用和最终输出。",
    )


def _line_explanation(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith(("async def", "def ")):
        return "这一行定义了函数入口，是后续逻辑的起点。"
    if "await " in stripped:
        return "这一行会等待异步结果，同时把控制权交还给事件循环。"
    if "return " in stripped:
        return "这一行返回计算结果。"
    if "print(" in stripped:
        return "这一行把结果输出到终端。"
    return "这一行承载当前代码片段中的一个具体步骤。"


def _is_diagram_candidate(block: DocumentBlock) -> bool:
    if block.kind not in {"paragraph", "list"}:
        return False
    lowered = block.text.lower()
    return any(keyword in lowered for keyword in PROCESS_KEYWORDS)


def _diagram_candidate(heading: str, block: DocumentBlock) -> DiagramCandidate:
    title = f"{heading or '当前内容'} 流程图"
    return DiagramCandidate(
        title=title,
        source_text=block.text,
        mermaid="graph LR\n  A[输入] --> B[处理]\n  B --> C[输出]",
    )


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[。！？.!?])\s*", text.strip())
    return parts[0].strip() if parts and parts[0].strip() else text.strip()


def _spoken_text(text: str) -> str:
    stripped = " ".join(text.split())
    if stripped.endswith(("。", ".", "！", "!", "？", "?")):
        return stripped
    return stripped + "。"
