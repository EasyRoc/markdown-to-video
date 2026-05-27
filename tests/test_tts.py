from unittest.mock import patch

import pytest

from src.parser import Segment
from src.tts import audio_cache_path, generate_audio, tts_text_for_segment


def test_tts_text_for_code_block():
    seg = Segment(
        index=0,
        title="安装",
        level=2,
        type="code_block",
        text="安装\n\n```\npip install x\n```",
    )

    text = tts_text_for_segment(seg)

    assert "pip install" not in text
    assert "安装" in text


def test_tts_text_for_section():
    seg = Segment(
        index=0,
        title="介绍",
        level=2,
        type="section",
        text="介绍\n\n这是正文内容。",
    )

    text = tts_text_for_segment(seg)

    assert "这是正文内容" in text


def test_tts_text_for_list():
    seg = Segment(
        index=0,
        title="功能",
        level=2,
        type="list",
        text="功能\n* 特性一\n* 特性二",
    )

    text = tts_text_for_segment(seg)

    assert "特性一" in text
    assert "特性二" in text


def test_audio_cache_path():
    path = audio_cache_path("hello world", "./cache/audio")
    path2 = audio_cache_path("hello world", "./cache/audio")

    assert path == path2
    assert path.suffix == ".mp3"
    assert "cache/audio" in str(path)


@pytest.mark.asyncio
async def test_generate_audio_cached(tmp_path):
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()
    seg = Segment(
        index=0,
        title="测试",
        level=1,
        type="title_slide",
        text="测试标题",
    )
    cached_path = audio_cache_path("测试标题", str(cache_dir))
    cached_path.parent.mkdir(parents=True, exist_ok=True)
    cached_path.write_bytes(b"fake mp3 data")

    with patch("src.tts._get_mp3_duration", return_value=3.5):
        duration = await generate_audio(seg, {"tts": {"retry": 1}}, str(cache_dir))

    assert duration == 3.5
    assert seg.duration == 3.5
