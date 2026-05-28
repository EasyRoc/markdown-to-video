# Markdown to Video V3 — Teaching Director Engine Design

## Overview

V3 upgrades markdown-to-video from a segment renderer into a teaching-video director.

The current V2 pipeline can render Markdown into a video, with annotations, mixed layouts, images, Mermaid diagrams, syntax highlighting, audio controls, and transitions. The visible weakness is that each Markdown section still behaves like a mostly static page. It does not decide how to teach a topic, how to split a concept into steps, or how to explain code line by line.

V3 adds a planning layer before rendering:

```text
Markdown
    -> DocumentModel
    -> TeachingScript
    -> Storyboard
    -> Timeline
    -> Existing V2 render/audio/compose pipeline
    -> Video
```

The first V3 release focuses on technical tutorials and code explanation. It uses deterministic rules by default, with an optional LLM planner later for richer narration and scene selection.

## Goals

1. Turn one Markdown section into multiple teaching scenes when useful.
2. Generate more natural narration than directly reading Markdown.
3. Explain code blocks through overview, focused highlights, and summary scenes.
4. Generate diagram scenes for process, architecture, and relationship content.
5. Keep the current V2 rendering, TTS, subtitles, audio, and composition capabilities reusable.
6. Expose the generated teaching plan as JSON so users can inspect and debug the result.
7. Keep offline generation usable without an API key or network dependency.

## Non-Goals

1. Do not build a full AI image-generation pipeline in this release.
2. Do not make LLM usage mandatory.
3. Do not replace the existing video composer.
4. Do not redesign all visual templates at once.
5. Do not attempt to support every content genre equally; the MVP optimizes for technical tutorials and code-heavy Markdown.

## Recommended Approach

Use a segment-compatible teaching director.

V3 should sit above the existing V2 segment pipeline. It will parse Markdown into a richer document model, plan a teaching script, expand that script into storyboard scenes, and then adapt scenes back into renderable units for the existing renderer.

This is preferred over a full parser rewrite because it makes visible improvements quickly while preserving the V2 work that already exists.

### Alternatives Considered

**Full Markdown AST rewrite**

This would produce a cleaner internal model, but it would touch more code and delay visible improvements. It is a good later direction after the director layer proves useful.

**LLM-first storyboard generation**

This would likely produce the best narration, but it makes the basic product dependent on external services, credentials, latency, and model output stability. V3 should support LLM enhancement later, not require it.

## User-Visible Behavior

Given a Markdown document such as:

````markdown
## Event Loop

The event loop receives tasks, schedules callbacks, and resumes coroutines.

```python
async def main():
    await fetch_data()
    print("done")
```
````

V2 tends to render this as a section page plus a code page.

V3 should produce a teaching sequence closer to:

1. Section objective scene: what the viewer will understand after this section.
2. Concept scene: what the event loop does in plain language.
3. Diagram scene: task queue -> event loop -> coroutine/callback.
4. Code overview scene: what the snippet demonstrates.
5. Code focus scene: highlight `await fetch_data()` and explain suspension/resume behavior.
6. Summary scene: the key takeaway.

The result should look like a short tutorial, not a slideshow of Markdown blocks.

## Architecture

### DocumentModel

`DocumentModel` is a normalized representation of Markdown content.

It should preserve the existing parser behavior while making content easier to plan:

```text
DocumentModel
  title
  sections[]
    heading
    level
    blocks[]
      kind: paragraph | list | code | mermaid | image | quote | table
      text
      language
      annotations
      source_segment_index
```

Responsibilities:

1. Group related blocks under headings.
2. Preserve source indices for compatibility with V2 segments.
3. Keep annotations available for scene planning.
4. Identify code language and Mermaid blocks.
5. Provide lightweight signals such as word count, code line count, and keyword candidates.

### TeachingScript

`TeachingScript` turns document structure into teachable intent.

```text
TeachingScript
  title
  sections[]
    objective
    key_points[]
    narration_blocks[]
    code_explanations[]
    diagram_candidates[]
    summary
```

Responsibilities:

1. Rewrite terse Markdown into spoken narration.
2. Extract section objectives from headings and first paragraphs.
3. Identify key terms and emphasize them consistently.
4. Detect code blocks that deserve line-focused explanation.
5. Detect content that can become diagrams.

The default implementation is `RulesTeachingPlanner`. It uses heuristics instead of external AI:

1. Headings become objectives.
2. Paragraphs become short narration blocks.
3. Lists become step-by-step scenes.
4. Code blocks become overview/focus/summary explanations.
5. Process words such as "流程", "步骤", "架构", "调用", "队列", "输入", and "输出" mark diagram candidates.

### Storyboard

`Storyboard` is the central V3 artifact. It describes what each scene should say and show.

```text
Storyboard
  metadata
    title
    planner
    source_hash
  scenes[]
    id
    kind: title | objective | concept | diagram | code_overview | code_focus | summary
    source_section
    source_block_index
    narration
    visual
      type: text | code | mermaid | image | callout
      payload
      title
      highlights[]
    duration_hint
    annotations
```

Responsibilities:

1. Expand each section into a sequence of teaching scenes.
2. Keep narration and visuals separate.
3. Attach highlight instructions to code and text scenes.
4. Carry compatible annotations forward to rendering.
5. Serialize to JSON for dry-run and cache inspection.

### Timeline

`Timeline` converts storyboard scenes into renderable timing.

```text
Timeline
  scenes[]
    scene_id
    start
    duration
    image_path
    audio_path
    transition
  subtitles[]
    scene_id
    start
    end
    text
  assets[]
```

Responsibilities:

1. Generate TTS from scene narration.
2. Use actual audio duration when available.
3. Fall back to `duration_hint` in dry-run mode.
4. Create subtitle cues from narration.
5. Provide a stable input for the existing composer.

### Renderer Adapter

The first implementation should avoid a full renderer rewrite.

Storyboard scenes can be converted into renderable segment-like inputs:

1. `text` and `callout` scenes use the existing text layout.
2. `code` scenes use the existing syntax highlighter and code renderer.
3. `mermaid` scenes use the existing Mermaid renderer.
4. Image-related scenes use the V2 image provider and mixed layouts.

If a scene contains a visual type the renderer cannot handle, it falls back to a readable text scene and logs a warning.

## Planner Modes

### Rules Planner

The rules planner is the default and must work offline.

It should be deterministic, testable, and conservative. It should not pretend to understand content beyond simple structure and keywords. Its job is to create a better teaching sequence from Markdown structure.

### Optional LLM Planner

The LLM planner is a future-compatible extension point.

It may improve:

1. Narration rewriting.
2. Section objective generation.
3. Code explanation quality.
4. Diagram selection.
5. Scene ordering.

It must remain optional. If an LLM call fails, times out, or returns invalid output, the system falls back to the rules planner and reports the fallback.

## CLI And Config

V3 should add opt-in behavior first:

```bash
python main.py input.md --v3
python main.py input.md --v3 --dry-run
```

Dry-run should print a concise summary and write JSON artifacts:

```text
cache/script/<source-hash>.json
cache/storyboard/<source-hash>.json
cache/timeline/<source-hash>.json
```

Suggested config:

```yaml
teaching_director:
  enabled: false
  planner: rules
  max_scenes_per_section: 6
  code_focus:
    enabled: true
    max_focus_lines: 4
  diagrams:
    enabled: true
    prefer_mermaid: true
  llm:
    enabled: false
    provider: openai
    model: ""
    timeout_seconds: 30
```

The existing V2 path remains the default until V3 output is stable enough to become default.

## Error Handling

1. Markdown parsing errors should fail with a clear message.
2. Unsupported block types should become text scenes, not crash the pipeline.
3. Invalid storyboard JSON should fail validation before rendering.
4. Mermaid rendering failures should fall back to a text explanation scene.
5. TTS failures should keep existing behavior: report the failed scene and stop unless an existing silent-audio fallback is already configured.
6. Optional LLM planner failures should fall back to the rules planner.
7. Cache writes should be best-effort; rendering should not fail solely because diagnostic JSON cannot be written, but the warning should be visible.

## Testing Strategy

Unit tests:

1. Build `DocumentModel` from headings, paragraphs, lists, code, and Mermaid blocks.
2. Generate `TeachingScript` from technical sections.
3. Generate storyboard scenes for paragraph-only, list-heavy, code-heavy, and Mermaid-heavy input.
4. Verify code blocks produce overview/focus/summary scenes.
5. Verify diagram candidates produce Mermaid scenes when enabled.
6. Verify unsupported visuals fall back safely.
7. Verify dry-run writes valid JSON artifacts.

Integration tests:

1. Run V3 dry-run on the existing sample Markdown.
2. Assert storyboard scene count is greater than the original segment count for suitable content.
3. Assert generated scene kinds include at least title/objective/concept/code or diagram when source content supports them.
4. Run a short full video generation path using mocked or minimal audio where the existing test suite already supports it.

Regression tests:

1. Existing V1/V2 behavior remains unchanged when `--v3` is not enabled.
2. Existing annotations still affect compatible scenes.
3. Existing renderer tests continue to pass.

## Acceptance Criteria

1. `python main.py tests/fixtures/sample.md --v3 --dry-run` writes script, storyboard, and timeline JSON.
2. The storyboard contains multiple teaching scenes per substantial section.
3. Code blocks produce at least one focused explanation scene when code focus is enabled.
4. Process or architecture prose can produce a Mermaid diagram scene when diagrams are enabled.
5. Full V3 generation can produce an MP4 using the existing renderer/composer path.
6. All existing tests pass.
7. New tests cover the director/planner/storyboard/timeline layers.
8. The default non-V3 pipeline remains backward compatible.

## Implementation Boundary

The implementation plan should be split into small tasks:

1. Add dataclasses and JSON serialization for DocumentModel, TeachingScript, Storyboard, and Timeline.
2. Add a Markdown-to-DocumentModel adapter using existing parser outputs where possible.
3. Add the rules teaching planner.
4. Add storyboard generation and dry-run output.
5. Add scene-to-renderer adapter.
6. Wire `--v3` through the CLI.
7. Add tests and sample dry-run verification.

The first implementation should favor clear data contracts over visual polish. Once V3 produces richer scenes reliably, later work can improve templates, animation, and optional LLM quality.
