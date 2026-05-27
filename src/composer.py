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

    _apply_smart_pauses(segments, config)
    _write_concat_file_with_transitions(segments, frames_dir, concat_path, config)
    cmd = _build_ffmpeg_command(
        segments,
        output,
        config,
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
            duration = _segment_visual_duration(segment)
            concat_file.write(f"file '{frame_path.absolute()}'\n")
            concat_file.write(f"duration {duration}\n")

        last = segments[-1]
        last_frame = Path(frames_dir) / f"segment_{last.index:04d}.png"
        concat_file.write(f"file '{last_frame.absolute()}'\n")


def _write_concat_file_with_transitions(
    segments: list[Segment],
    frames_dir: str,
    concat_path: Path,
    config: dict,
) -> None:
    transition_duration = config.get("video", {}).get("transition_duration", 0.5)
    with open(concat_path, "w", encoding="utf-8") as concat_file:
        for index, segment in enumerate(segments):
            frame_path = Path(frames_dir) / f"segment_{segment.index:04d}.png"
            duration = _segment_visual_duration(segment)
            if segment.transition != "none" and index < len(segments) - 1:
                duration -= transition_duration / 2
            if index > 0 and segments[index - 1].transition != "none":
                duration -= transition_duration / 2
            concat_file.write(f"file '{frame_path.absolute()}'\n")
            concat_file.write(f"duration {max(duration, 0.1)}\n")

        last = segments[-1]
        last_frame = Path(frames_dir) / f"segment_{last.index:04d}.png"
        concat_file.write(f"file '{last_frame.absolute()}'\n")


def _apply_smart_pauses(segments: list[Segment], config: dict) -> None:
    audio_config = config.get("audio", {})
    pauses = audio_config.get("smart_pauses", {})
    after_title = pauses.get("after_title", 1.0)
    around_code = pauses.get("around_code", 0.5)
    between_items = pauses.get("between_list_items", 0.2)

    for index, segment in enumerate(segments):
        if segment.type == "title_slide":
            segment.pause_after = segment.pause_after or after_title
        if segment.type in {"code_block", "mermaid"}:
            segment.pause_before = segment.pause_before or around_code
            segment.pause_after = segment.pause_after or around_code
        if segment.type == "list" and index > 0:
            segment.pause_before = segment.pause_before or between_items


def _segment_visual_duration(segment: Segment) -> float:
    return max(segment.duration + segment.pause_before + segment.pause_after, 0.5)


def _build_ffmpeg_command(
    segments: list[Segment],
    output: Path,
    config: dict,
    frames_dir: str,
    audio_dir: str,
    concat_path: Path,
) -> list[str]:
    video_config = config["video"]
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

    bgm_paths = _collect_bgm_paths(segments, config)
    for bgm_path in bgm_paths:
        base_cmd.extend(["-stream_loop", "-1", "-i", str(bgm_path)])

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

    if audio_paths or bgm_paths:
        filter_parts = []
        output_label = None

        if audio_paths:
            voice_inputs = "".join(
                f"[{index}:a]" for index in range(1, len(audio_paths) + 1)
            )
            if len(audio_paths) == 1:
                filter_parts.append(f"{voice_inputs}anull[voice]")
            else:
                filter_parts.append(
                    f"{voice_inputs}concat=n={len(audio_paths)}:v=0:a=1[voice]"
                )
            output_label = "[voice]"

        if bgm_paths:
            bgm_input_index = 1 + len(audio_paths)
            bgm_volume = _bgm_volume_for_path(segments, bgm_paths[0], config)
            filter_parts.append(f"[{bgm_input_index}:a]volume={bgm_volume}[bgm]")
            if output_label:
                filter_parts.append(f"{output_label}[bgm]amix=inputs=2:duration=longest[outa]")
            else:
                filter_parts.append("[bgm]anull[outa]")
            output_label = "[outa]"

        if not bgm_paths:
            output_label = "[voice]"

        concat_filter = ";".join(filter_parts)
        encoding.extend(["-filter_complex", concat_filter, "-map", output_label])

    if audio_paths or bgm_paths:
        encoding.extend(
            [
                "-c:a",
                video_config["audio_codec"],
                "-b:a",
                video_config["audio_bitrate"],
            ]
        )

    encoding.append(str(output))
    return base_cmd + encoding


def _collect_bgm_paths(segments: list[Segment], config: dict) -> list[Path]:
    paths: list[Path] = []
    default_bgm = config.get("audio", {}).get("default_bgm")
    for segment in segments:
        bgm = segment.bgm if segment.bgm is not None else default_bgm
        if not bgm or bgm == "none":
            continue
        path = Path(bgm).expanduser()
        if path.exists():
            absolute = path.absolute()
            if absolute not in paths:
                paths.append(absolute)
    return paths[:1]


def _bgm_volume_for_path(segments: list[Segment], bgm_path: Path, config: dict) -> float:
    default_volume = config.get("audio", {}).get("bgm_volume", 0.15)
    for segment in segments:
        if segment.bgm and segment.bgm != "none" and Path(segment.bgm).expanduser().absolute() == bgm_path:
            return segment.bgm_volume
    return default_volume
