from copy import deepcopy

import yaml


DEFAULT_CONFIG = {
    "tts": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "speed": "+0%",
        "pitch": "+0Hz",
        "retry": 1,
    },
    "render": {
        "width": 1920,
        "height": 1080,
        "font_family": "/System/Library/Fonts/PingFang.ttc",
        "font_family_mono": "/System/Library/Fonts/SFNSMono.ttf",
        "font_size_title": 72,
        "font_size_body": 40,
        "font_size_code": 34,
        "bg_color": "#f5f5f5",
        "code_bg_color": "#1e1e1e",
        "accent_color": "#4A90D9",
        "text_color": "#333333",
        "light_text_color": "#e0e0e0",
        "max_chars_per_segment": 200,
    },
    "video": {
        "fps": 30,
        "codec": "libx264",
        "audio_codec": "aac",
        "audio_bitrate": "192k",
        "output_dir": "./output",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(
    config_path: str | None = None,
    cli_overrides: dict | None = None,
) -> dict:
    config = deepcopy(DEFAULT_CONFIG)

    if config_path:
        with open(config_path, encoding="utf-8") as config_file:
            file_config = yaml.safe_load(config_file) or {}
        config = _deep_merge(config, file_config)

    if cli_overrides:
        config = _deep_merge(config, cli_overrides)

    return config
