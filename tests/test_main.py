import subprocess
import sys


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "markdown" in result.stdout.lower()


def test_cli_file_not_found():
    result = subprocess.run(
        [sys.executable, "main.py", "nonexistent.md"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0


def test_cli_dry_run(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text(
        "# Hello\n\nThis is a test.\n\n## Code\n\n```\nprint(1)\n```\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "main.py", str(md_file), "--dry-run"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Segment" in result.stdout or len(result.stdout) > 0


def test_dry_run_shows_annotation_info(tmp_path):
    md_file = tmp_path / "annotated.md"
    md_file.write_text(
        '<!-- {"voice": "zh-CN-YunxiNeural", "layout": "image-right"} -->\n'
        "# Title\n\nContent.",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "main.py", str(md_file), "--dry-run"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "voice=zh-CN-YunxiNeural" in result.stdout
    assert "layout=image-right" in result.stdout


def test_cli_v3_dry_run_writes_storyboard_artifacts(tmp_path):
    md_file = tmp_path / "v3.md"
    cache_dir = tmp_path / "cache"
    config_file = tmp_path / "config.yaml"
    md_file.write_text(
        "# V3 Demo\n\n"
        "Intro.\n\n"
        "## Pipeline\n\n"
        "输入 Markdown 进入解析流程，最后输出视频。\n",
        encoding="utf-8",
    )
    config_file.write_text(
        "teaching_director:\n"
        f"  cache_dir: \"{cache_dir}\"\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "main.py",
            str(md_file),
            "--v3",
            "--dry-run",
            "-c",
            str(config_file),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "V3 Storyboard" in result.stdout
    assert "kind=diagram" in result.stdout
    assert list((cache_dir / "storyboard").glob("*.json"))
    assert list((cache_dir / "timeline").glob("*.json"))
