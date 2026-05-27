from src.config import DEFAULT_CONFIG, load_config


def test_default_config_has_required_keys():
    for key in ("tts", "render", "video"):
        assert key in DEFAULT_CONFIG


def test_load_config_merges_yaml(tmp_path):
    custom_yaml = tmp_path / "custom.yaml"
    custom_yaml.write_text('tts:\n  voice: "zh-CN-YunxiNeural"\n')

    config = load_config(str(custom_yaml))

    assert config["tts"]["voice"] == "zh-CN-YunxiNeural"
    assert config["render"]["width"] == 1920


def test_load_config_cli_overrides():
    cli_overrides = {"tts": {"speed": "+20%"}}
    config = load_config(cli_overrides=cli_overrides)

    assert config["tts"]["speed"] == "+20%"
    assert config["tts"]["voice"] == "zh-CN-XiaoxiaoNeural"
