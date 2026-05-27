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


def test_compose_video_with_bgm_adds_audio_input(tmp_path):
    segments = [
        Segment(0, "Test", 1, "title_slide", "Test", duration=3.0),
    ]
    segments[0].bgm = str(tmp_path / "bgm.mp3")
    segments[0].bgm_volume = 0.2
    (tmp_path / "bgm.mp3").write_bytes(b"fake mp3")

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    (frames_dir / "segment_0000.png").write_bytes(b"fake")

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    path = audio_cache_path(tts_text_for_segment(segments[0]), str(audio_dir))
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

    cmd = mock_run.call_args.args[0]
    assert "-stream_loop" in cmd
    assert str((tmp_path / "bgm.mp3").absolute()) in cmd


def test_smart_pause_after_title():
    from src.composer import _apply_smart_pauses

    segments = [
        Segment(0, "Title", 1, "title_slide", "Title\n\nContent", duration=5.0),
        Segment(1, "Section", 2, "section", "Section\n\nBody", duration=10.0),
    ]
    config = {
        "audio": {
            "smart_pauses": {
                "after_title": 1.0,
                "around_code": 0.5,
                "between_list_items": 0.2,
            }
        }
    }

    _apply_smart_pauses(segments, config)

    assert segments[0].pause_after >= 1.0


def test_smart_pause_around_code():
    from src.composer import _apply_smart_pauses

    segments = [
        Segment(0, "Code", 2, "code_block", "Code\n\n```\nx\n```", duration=8.0),
    ]
    config = {
        "audio": {
            "smart_pauses": {
                "after_title": 1.0,
                "around_code": 0.5,
                "between_list_items": 0.2,
            }
        }
    }

    _apply_smart_pauses(segments, config)

    assert segments[0].pause_before == 0.5
    assert segments[0].pause_after == 0.5
