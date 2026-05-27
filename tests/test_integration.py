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
