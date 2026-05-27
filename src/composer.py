import subprocess
import sys
from pathlib import Path

from src.parser import Segment
from src.tts import audio_cache_path, tts_text_for_segment


def _check_ffmpeg() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def compose_video(
    segments: list[Segment],
    output_path: str,
    config: dict,
    frames_dir: str = "./cache/frames",
    audio_dir: str = "./cache/audio",
) -> None:
    if not _check_ffmpeg():
        print("Error: ffmpeg not found. Install it with: brew install ffmpeg")
        sys.exit(1)

    if not segments:
        raise ValueError("Cannot compose video without segments")

    video_config = config["video"]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    concat_path = output.parent / ".concat_list.txt"

    _write_concat_file(segments, frames_dir, concat_path)
    cmd = _build_ffmpeg_command(
        segments,
        output,
        video_config,
        frames_dir,
        audio_dir,
        concat_path,
    )

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}")
        raise RuntimeError("ffmpeg composition failed")

    concat_path.unlink(missing_ok=True)
    print(f"Video saved to: {output}")


def _write_concat_file(
    segments: list[Segment],
    frames_dir: str,
    concat_path: Path,
) -> None:
    with open(concat_path, "w", encoding="utf-8") as concat_file:
        for segment in segments:
            frame_path = Path(frames_dir) / f"segment_{segment.index:04d}.png"
            duration = max(segment.duration, 0.5)
            concat_file.write(f"file '{frame_path.absolute()}'\n")
            concat_file.write(f"duration {duration}\n")

        last = segments[-1]
        last_frame = Path(frames_dir) / f"segment_{last.index:04d}.png"
        concat_file.write(f"file '{last_frame.absolute()}'\n")


def _build_ffmpeg_command(
    segments: list[Segment],
    output: Path,
    video_config: dict,
    frames_dir: str,
    audio_dir: str,
    concat_path: Path,
) -> list[str]:
    audio_paths = []
    for segment in segments:
        text = tts_text_for_segment(segment)
        audio_path = audio_cache_path(text, audio_dir)
        if audio_path.exists():
            audio_paths.append(audio_path)

    base_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
    ]

    for audio_path in audio_paths:
        base_cmd.extend(["-i", str(audio_path)])

    encoding = [
        "-map",
        "0:v",
        "-c:v",
        video_config["codec"],
        "-r",
        str(video_config["fps"]),
        "-pix_fmt",
        "yuv420p",
    ]

    if audio_paths:
        filter_inputs = "".join(f"[{index}:a]" for index in range(1, len(audio_paths) + 1))
        concat_filter = f"{filter_inputs}concat=n={len(audio_paths)}:v=0:a=1[outa]"
        encoding.extend(
            [
                "-filter_complex",
                concat_filter,
                "-map",
                "[outa]",
                "-c:a",
                video_config["audio_codec"],
                "-b:a",
                video_config["audio_bitrate"],
            ]
        )

    encoding.extend(["-shortest", str(output)])
    return base_cmd + encoding
