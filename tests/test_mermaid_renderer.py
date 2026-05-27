from pathlib import Path
from unittest.mock import MagicMock, patch

from src.mermaid_renderer import is_mermaid_available, render_mermaid


def test_is_mermaid_available_yes():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        assert is_mermaid_available() is True


def test_is_mermaid_available_no():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()

        assert is_mermaid_available() is False


def test_render_mermaid_calls_mmdc(tmp_path):
    mermaid_code = "graph LR\n  A --> B"
    output = tmp_path / "diagram.png"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with patch("src.mermaid_renderer.is_mermaid_available", return_value=True):
            result = render_mermaid(mermaid_code, str(output))

    assert mock_run.called
    assert result == str(output)
    assert not any(Path(tmp_path).glob("*.mmd"))
