from pathlib import Path

from src.image_provider import load_manifest, match_image_from_manifest, resolve_image


def test_resolve_image_returns_annotation_path(tmp_path):
    img = tmp_path / "test.png"
    img.write_text("fake", encoding="utf-8")
    segment = type(
        "Seg",
        (),
        {
            "image_path": str(img),
            "title": "Test",
            "text": "Test content",
        },
    )()

    result = resolve_image(segment, {}, tmp_path)

    assert result == str(img)


def test_resolve_image_returns_none_when_no_match(tmp_path):
    segment = type(
        "Seg",
        (),
        {
            "image_path": None,
            "title": "Random",
            "text": "No matching images anywhere.",
        },
    )()

    config = {"image": {"assets_dir": str(tmp_path), "manifest_file": ""}}
    result = resolve_image(segment, config, tmp_path)

    assert result is None


def test_load_manifest(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "images:\n"
        "  - file: python.png\n"
        "    keywords: [python, coding]\n"
        "  - file: docker.png\n"
        "    keywords: [docker, container]\n",
        encoding="utf-8",
    )

    data = load_manifest(str(manifest))

    assert len(data["images"]) == 2


def test_match_image_from_manifest():
    manifest = {
        "images": [
            {"file": "python.png", "keywords": ["python", "coding"]},
            {"file": "docker.png", "keywords": ["docker", "container"]},
            {"file": "generic.png", "keywords": ["software"]},
        ]
    }

    result = match_image_from_manifest(
        "In this Python tutorial we will learn coding basics.", manifest
    )

    assert result is not None
    assert "python" in str(result).lower()


def test_match_image_no_match_returns_none():
    manifest = {
        "images": [
            {"file": "docker.png", "keywords": ["docker", "container"]},
        ]
    }

    result = match_image_from_manifest(
        "Python is a great language for data science.", manifest
    )

    assert result is None
