from unittest.mock import AsyncMock, patch

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


@pytest.mark.asyncio
async def test_generate_audio_uses_segment_voice(tmp_path):
    cache_dir = tmp_path / "audio"
    cache_dir.mkdir()
    seg = Segment(0, "Test", 1, "title_slide", "Hello")
    seg.voice = "zh-CN-YunxiNeural"
    seg.speed = "-20%"

    with patch("src.tts._get_mp3_duration", return_value=2.0):
        with patch("edge_tts.Communicate") as mock_communicate:
            mock_communicate.return_value.save = AsyncMock()
            await generate_audio(
                seg,
                {
                    "tts": {
                        "voice": "default",
                        "speed": "+0%",
                        "pitch": "+0Hz",
                        "retry": 0,
                    }
                },
                str(cache_dir),
            )

    call_args = mock_communicate.call_args
    assert call_args.args[1] == "zh-CN-YunxiNeural"
    assert call_args.kwargs["rate"] == "-20%"


def test_tts_text_for_mermaid():
    seg = Segment(
        0,
        "Diagram",
        2,
        "mermaid",
        "Diagram\n\n```mermaid\ngraph LR\n  A --> B\n```",
    )

    text = tts_text_for_segment(seg)

    assert "mermaid" not in text.lower()
    assert "graph LR" not in text


def test_tts_text_for_table_uses_summary_not_raw_markdown():
    seg = Segment(
        0,
        "模板",
        2,
        "table",
        "模板\n\n这张表格包含 3 列、2 行数据。",
    )
    seg.table_data = [["类型", "模板", "效果"], ["列表", "列表页", "标题 + 圆点列表"]]

    text = tts_text_for_segment(seg)

    assert "这张表格包含" in text
    assert "|" not in text
