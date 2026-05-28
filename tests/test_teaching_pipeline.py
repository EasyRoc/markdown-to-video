import json

from src.config import load_config
from src.teaching_pipeline import build_teaching_assets, dry_run_summary, write_dry_run_artifacts


def test_build_teaching_assets_expands_sample_into_storyboard_and_segments():
    markdown = (
        "# Python Tutorial\n\n"
        "Python is useful for automation.\n\n"
        "## Installation\n\n"
        "输入源码经过解析流程，最后输出视频。\n\n"
        "```shell\n"
        "brew install python\n"
        "```"
    )

    assets = build_teaching_assets(markdown, load_config())

    assert assets.document.title == "Python Tutorial"
    assert len(assets.storyboard.scenes) > len(assets.document.sections)
    assert len(assets.segments) == len(assets.storyboard.scenes)
    assert any(scene.kind == "diagram" for scene in assets.storyboard.scenes)
    assert any(segment.type == "code_block" for segment in assets.segments)


def test_build_teaching_assets_resolves_markdown_image_relative_to_source_dir(tmp_path):
    image_dir = tmp_path / "assets"
    image_dir.mkdir()
    image_path = image_dir / "pipeline.png"
    image_path.write_bytes(b"placeholder")
    markdown = "# Demo\n\n## Flow\n\n![Pipeline](assets/pipeline.png)"

    assets = build_teaching_assets(markdown, load_config(), source_dir=tmp_path)

    assert any(segment.image_path == str(image_path) for segment in assets.segments)


def test_dry_run_summary_lists_storyboard_scenes():
    assets = build_teaching_assets(
        "## Intro\n\nA short explanation.",
        load_config(),
    )

    summary = dry_run_summary(assets)

    assert "V3 Storyboard" in summary
    assert "Scene 001" in summary
    assert "kind=objective" in summary


def test_write_dry_run_artifacts_uses_configured_cache_dir(tmp_path):
    config = load_config(
        cli_overrides={
            "teaching_director": {
                "cache_dir": str(tmp_path),
            }
        }
    )
    assets = build_teaching_assets("## Intro\n\nContent.", config)

    paths = write_dry_run_artifacts(assets, config)

    assert paths["storyboard"].exists()
    data = json.loads(paths["storyboard"].read_text(encoding="utf-8"))
    assert data["planner"] == "rules"
