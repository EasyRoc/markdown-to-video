import hashlib
import re
from pathlib import Path

from mutagen.mp3 import MP3

from src.parser import Segment


def audio_cache_path(text: str, cache_dir: str) -> Path:
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / f"{text_hash}.mp3"


def tts_text_for_segment(segment: Segment) -> str:
    if segment.type == "code_block":
        text = _strip_fenced_code(segment.text).strip()
        if text:
            return text
        title = segment.title or "当前段落"
        return f"以下是{title}的示例代码"
    return segment.text.strip()


async def generate_audio(
    segment: Segment,
    config: dict,
    cache_dir: str = "./cache/audio",
) -> float:
    text = tts_text_for_segment(segment)
    if _should_skip_tts(text):
        segment.duration = 0
        return 0

    cache_path = audio_cache_path(text, cache_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        try:
            segment.duration = _get_mp3_duration(str(cache_path))
            return segment.duration
        except Exception:
            cache_path.unlink(missing_ok=True)

    import edge_tts

    tts_config = config.get("tts", {})
    retry_count = tts_config.get("retry", 1)
    last_error: Exception | None = None

    for _attempt in range(retry_count + 1):
        try:
            communicate = edge_tts.Communicate(
                text,
                tts_config.get("voice", "zh-CN-XiaoxiaoNeural"),
                rate=tts_config.get("speed", "+0%"),
                pitch=tts_config.get("pitch", "+0Hz"),
            )
            await communicate.save(str(cache_path))
            segment.duration = _get_mp3_duration(str(cache_path))
            return segment.duration
        except Exception as exc:
            last_error = exc
            cache_path.unlink(missing_ok=True)

    raise RuntimeError(f"TTS generation failed for segment {segment.index}") from last_error


def _strip_fenced_code(text: str) -> str:
    lines = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            lines.append(line)
    return "\n".join(lines)


def _should_skip_tts(text: str) -> bool:
    return not re.search(r"[\w\u4e00-\u9fff]", text)


def _get_mp3_duration(filepath: str) -> float:
    audio = MP3(filepath)
    return float(audio.info.length)
