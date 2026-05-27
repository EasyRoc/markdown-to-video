from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.composer import _check_ffmpeg, compose_video
from src.parser import Segment
from src.tts import audio_cache_path, tts_text_for_segment


def test_check_ffmpeg_found():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert _check_ffmpeg() is True


def test_check_ffmpeg_not_found():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        assert _check_ffmpeg() is False


def test_compose_video_calls_ffmpeg(tmp_path):
    segments = [
        Segment(
            index=0,
            title="Test",
            level=1,
            type="title_slide",
            text="Test",
            duration=3.0,
        ),
        Segment(
            index=1,
            title="Section",
            level=2,
            type="section",
            text="Content",
            duration=5.0,
        ),
    ]

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    for index in range(2):
        (frames_dir / f"segment_{index:04d}.png").write_bytes(b"fake png")

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    for segment in segments:
        path = audio_cache_path(tts_text_for_segment(segment), str(audio_dir))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake mp3")

    output = tmp_path / "output.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with patch("src.composer._check_ffmpeg", return_value=True):
            compose_video(
                segments,
                str(output),
                {
                    "video": {
                        "fps": 30,
                        "codec": "libx264",
                        "audio_codec": "aac",
                        "audio_bitrate": "192k",
                    }
                },
                str(frames_dir),
                str(audio_dir),
            )

    assert mock_run.called
    cmd = mock_run.call_args.args[0]
    assert "ffmpeg" in cmd[0]
    assert str(output) in cmd


def test_compose_video_ffmpeg_missing_raises(tmp_path):
    with patch("src.composer._check_ffmpeg", return_value=False):
        with pytest.raises(SystemExit):
            compose_video([], str(tmp_path / "out.mp4"), {}, ".", ".")
