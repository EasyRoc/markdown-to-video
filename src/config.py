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
        "font_family": "/System/Library/Fonts/STHeiti Medium.ttc",
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
        "default_transition": "fade",
        "transition_duration": 0.5,
        "progress_bar": True,
    },
    "image": {
        "assets_dir": "./assets/images",
        "manifest_file": "./assets/images/manifest.yaml",
    },
    "highlight": {
        "font_scale": 1.15,
        "color_override": None,
    },
    "code_highlight": {
        "theme": "monokai",
        "line_numbers": True,
    },
    "audio": {
        "default_bgm": None,
        "bgm_volume": 0.15,
        "ducking": {
            "enabled": True,
            "reduction_db": 12,
            "attack_ms": 150,
            "release_ms": 400,
        },
        "smart_pauses": {
            "after_title": 1.0,
            "around_code": 0.5,
            "between_list_items": 0.2,
        },
    },
    "teaching_director": {
        "enabled": False,
        "planner": "rules",
        "cache_dir": "./cache",
        "max_scenes_per_section": 6,
        "code_focus": {
            "enabled": True,
            "max_focus_lines": 4,
        },
        "diagrams": {
            "enabled": True,
            "prefer_mermaid": True,
        },
        "llm": {
            "enabled": False,
            "provider": "openai",
            "model": "",
            "timeout_seconds": 30,
        },
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
