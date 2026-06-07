# LLM 语义理解重构设计

## 目标

用 DeepSeek LLM 替代规则引擎，实现：
1. 识别文章语义结构
2. 生成教学大纲和总结
3. 自动生成可渲染的 SVG 图解
4. 视频按总结 + SVG 进行讲解

## 架构

```
Markdown 文本
  → [Stage 1] LLM 全文分析 → 教学大纲 + SVG 规划
  → [Stage 2] LLM 逐节展开 → 讲解文案 + SVG 代码
  → SVG 渲染 (cairosvg → PIL Image)
  → TTS 语音合成 (edge-tts，复用)
  → 帧渲染 (PIL layouts，复用)
  → 视频合成 (ffmpeg，复用)
```

核心思路：LLM 替代规则引擎做语义理解，保留现有渲染/合成链路。

## 数据模型

### Stage 1 输出 — Outline

```json
{
  "title": "视频标题",
  "sections": [
    {
      "heading": "章节标题",
      "key_points": ["要点1", "要点2"],
      "svg_types": ["flowchart", "timeline"],
      "svg_intent": "展示XX的调用流程"
    }
  ]
}
```

### Stage 2 输出 — Scene[]

```json
[
  {
    "kind": "title | concept | diagram | code | summary",
    "narration": "自然口语讲解文案",
    "svg_code": "<svg>...</svg>",
    "duration_hint": 12.5,
    "layout": "text-only | image-below | image-full"
  }
]
```

Stage 2 输出直接映射到现有 Storyboard → Scene[] → Segment[] → 帧渲染链路。

## LLM 调用策略

### Prompt 设计

- **Stage 1**：输入全文 Markdown，要求输出 JSON Outline。强调"识别文章结构、提取核心论点、规划视觉表达"
- **Stage 2**：输入大纲节点 + 对应原文，要求输出 JSON Scene[]。强调"自然口语化文案 + 可渲染的 SVG 代码 + 时长估算"

### 错误处理与降级

1. JSON 解析失败 → 重试一次（带格式错误提示）
2. 重试仍失败 → 降级到规则引擎（RulesTeachingPlanner）
3. SVG 代码渲染失败（cairosvg 报错）→ scene 降级为 text-only 布局

### 成本与性能

- Stage 1：每次视频生成一次调用，token 量 = 全文长度
- Stage 2：每节一次调用，可 3-5 节并发
- `--dry-run`：只输出 LLM 返回的 JSON，不渲染视频

## 文件变更计划

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/llm_client.py` | DeepSeek API 封装（chat completion、retry、JSON 解析） |
| `src/outline_planner.py` | Stage 1：全文 → Outline（prompt 模板 + 调用） |
| `src/scene_generator.py` | Stage 2：大纲节点 + 原文 → Scene[]（prompt 模板 + 调用） |
| `src/svg_renderer.py` | SVG 字符串 → PIL Image（cairosvg + CJK 字体注入） |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/teaching_pipeline.py` | 新增 LLMTeachingPipeline，编排 Stage 1 → Stage 2 → 渲染链路 |
| `src/teaching_planner.py` | 保留为 fallback（已是 RulesTeachingPlanner） |
| `config.yaml` | 新增 `llm` 配置段 |
| `main.py` | 新增 `--llm` flag |

### 不动文件

- `src/tts.py` — TTS 不变
- `src/renderer.py` + `src/layouts/` — 帧渲染不变
- `src/composer.py` — 视频合成不变
- `src/document_model.py` — 文档模型不变
- `src/storyboard.py` + `src/timeline.py` — 数据模型复用
