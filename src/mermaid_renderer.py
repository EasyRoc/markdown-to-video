import subprocess
import tempfile
from pathlib import Path


def is_mermaid_available() -> bool:
    try:
        result = subprocess.run(
            ["mmdc", "--version"],
            capture_output=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def render_mermaid(code: str, output_path: str) -> str | None:
    if not is_mermaid_available():
        return None

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".mmd",
        delete=False,
        encoding="utf-8",
    ) as mermaid_file:
        mermaid_file.write(code)
        mermaid_path = mermaid_file.name

    try:
        result = subprocess.run(
            [
                "mmdc",
                "-i",
                mermaid_path,
                "-o",
                str(output),
                "-b",
                "transparent",
                "-s",
                "2",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return str(output)
    except Exception:
        return None
    finally:
        Path(mermaid_path).unlink(missing_ok=True)
