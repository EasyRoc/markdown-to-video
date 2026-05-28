import subprocess
import sys
from pathlib import Path


def test_full_pipeline_dry_run_on_fixture():
    fixture = Path("tests/fixtures/sample.md")

    result = subprocess.run(
        [sys.executable, "main.py", str(fixture), "--dry-run"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Getting Started" in result.stdout
    assert "title_slide" in result.stdout
    assert "code_block" in result.stdout
    assert "list" in result.stdout


def test_v3_dry_run_on_fixture_expands_storyboard(tmp_path):
    fixture = Path("tests/fixtures/sample.md")
    cache_dir = tmp_path / "cache"
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "teaching_director:\n"
        f"  cache_dir: \"{cache_dir}\"\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "main.py",
            str(fixture),
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
    assert "Scene" in result.stdout
    assert result.stdout.count("Scene") > 4
