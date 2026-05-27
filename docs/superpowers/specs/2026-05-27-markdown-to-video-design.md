# Markdown to Video — 设计文档

## 概述

将 Markdown 文件自动转换为视频。面向个人内容创作者，一键将技术博客/教程转为带 AI 配音和画面展示的视频。

**使用方式**：命令行 + 配置文件驱动。

**输出**：与输入 markdown 同名的 `.mp4` 文件（如 `my-tutorial.md` → `my-tutorial.mp4`）。

---

## 架构

```
                    config.yaml
                        │
    input.md ──→ ① 解析器(Parser) ──→ [Segment, Segment, ...]
                        │
                  ② TTS引擎 ──→ segment_01.mp3, segment_02.mp3, ...
                        │
                  ③ 画面渲染 ──→ segment_01.png, segment_02.png, ...
                        │
                  ④ 视频合成 ──→ output.mp4
```

顺序管线：每步完成后进入下一步，中间产物可缓存可预览。

### 技术栈

| 组件 | 库 | 用途 |
|------|---|------|
| Markdown 解析 | `mistune` | md → AST |
| TTS | `edge-tts` | 文本 → mp3 语音 |
| 画面渲染 | `Pillow` | 图片生成 |
| 视频合成 | `ffmpeg` (subprocess) | 图片+音频 → mp4 |
| 配置 | `pyyaml` | config.yaml 读取 |

### 项目结构

```
markdown-to-video/
├── main.py                 # CLI 入口
├── config.yaml             # 默认配置
├── src/
│   ├── parser.py           # Markdown 解析与分段
│   ├── tts.py              # edge-tts 封装
│   ├── renderer.py         # 画面渲染
│   └── composer.py         # 视频合成
├── templates/              # 渲染模板定义
├── cache/                  # 中间产物缓存（音频、图片）
└── output/                 # 最终视频输出
```

---

## 模块设计

### 1. Markdown 解析与分段 (parser.py)

以标题（h1-h6）为边界将 markdown 拆分为 Segment 列表。

**分段规则**：

| 遇到的元素 | 行为 |
|-----------|------|
| `# 一级标题` | 新 Segment，type=title_slide |
| `## ~ ######` | 新 Segment，type=section |
| `` ```code``` `` | 并入当前 Segment，type=code_block |
| 无序/有序列表 | 并入当前 Segment，type=list |
| 普通段落 | 并入当前 Segment，type=paragraph |

**超长段落处理**：Segment 文本超过 200 字时，在句号处二次拆分（阈值可配置）。

**Segment 数据结构**：

```python
@dataclass
class Segment:
    index: int
    title: str           # 标题文本
    level: int           # 标题级别 (1-6)，非标题内容继承最近标题级别
    type: str            # title_slide | section | code_block | list
    text: str            # 完整文本内容
    duration: float = 0  # 由 TTS 音频长度回填
```

**输出示例**：
```
Segment(0, "Python 入门教程", 1, "title_slide", "Python 入门教程\n\n作者：xxx")
Segment(1, "安装依赖", 2, "section", "首先你需要安装...")
Segment(2, "示例代码", 2, "code_block", "以下是一个简单示例：\n```\nprint('hello')\n```")
```

### 2. TTS 语音生成 (tts.py)

遍历 Segment 列表，为每个 Segment 的 text 生成 mp3 音频。

**音频缓存**：以 `hash(text)` 命名音频文件存放在 `cache/audio/`。重复运行跳过已缓存的音频。

**代码块处理**：代码块不朗读代码本身，只朗读 "以下是[标题]的示例代码"。

**跳过条件**：纯符号/分隔线的 Segment 跳过 TTS。

**可配置项**：
```yaml
tts:
  voice: "zh-CN-XiaoxiaoNeural"
  speed: "+0%"
  pitch: "+0Hz"
```

**回填时长**：生成音频后读取实际时长写入 segment.duration。

### 3. 画面渲染 (renderer.py)

根据 Segment 类型使用模板渲染为 1920×1080 PNG。

**模板类型**：

| 模板 | 适用类型 | 布局描述 |
|------|---------|---------|
| 封面页 | title_slide | 标题居中，副标题/作者在下方，渐变背景 |
| 内容页 | section/paragraph | 标题栏在上方，正文居中偏上 |
| 代码页 | code_block | 深色终端背景(#1e1e1e)，左上角红黄绿圆点 |
| 列表页 | list | 标题在上，列表项左对齐，一次性全部显示 |

**V1 简化**：列表不做逐条动画，代码块不做语法高亮（白色等宽字体统一渲染）。

**缓存**：图片存放在 `cache/frames/`，以 `segment.index` 命名。

**可配置项**：
```yaml
render:
  width: 1920
  height: 1080
  font_family: "PingFang SC"
  font_size_title: 72
  font_size_body: 40
  font_size_code: 36
  bg_color: "#f5f5f5"
  code_bg_color: "#1e1e1e"
  accent_color: "#4A90D9"
```

### 4. 视频合成 (composer.py)

将图片序列和音频合成为 mp4 视频。

**合成方式**：使用 ffmpeg 的 concat demuxer 拼接图片序列，每张图片时长 = 对应音频时长，同时混入音频流。

**输出**：`output/<md文件名>.mp4`，h264 编码，30fps，aac 192k 音频。

**可配置项**：
```yaml
video:
  fps: 30
  codec: "h264"
  audio_codec: "aac"
  audio_bitrate: "192k"
```

### 5. CLI 入口 (main.py)

```bash
python main.py my-tutorial.md              # 使用默认配置
python main.py my-tutorial.md -c config.yaml  # 指定配置文件
```

**执行流程**：
1. 加载配置（命令行参数 > config.yaml > 默认值）
2. 解析 markdown → Segment 列表
3. 逐段生成 TTS 音频（自动跳过已缓存）
4. 逐段渲染画面（自动跳过已缓存）
5. 合成视频

**输出**：`output/my-tutorial.mp4`

---

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| md 文件不存在 | 报错退出，提示文件路径 |
| edge-tts 调用失败 | 重试 1 次，仍失败则跳过该段（生成无声片段） |
| ffmpeg 未安装 | 启动时检查，未安装则报错退出并提示安装命令 |
| 磁盘空间不足 | ffmpeg 合成阶段报错，保留中间产物 |
| 空 markdown 文件 | 提示 "文件无有效内容"，退出 |

---

## V1 范围外（后续版本）

- 字幕生成与烧录
- 背景音乐
- 更多模板样式和过渡动画
- 图片素材配图
- 列表逐条动画
- 代码语法高亮
- 多语言 TTS 切换
