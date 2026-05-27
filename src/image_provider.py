from pathlib import Path
from urllib.parse import urlparse

import yaml


def resolve_image(segment, config: dict, cache_dir: Path) -> str | None:
    if getattr(segment, "image_path", None):
        return _resolve_explicit_image(segment.image_path, cache_dir)

    image_config = config.get("image", {})
    manifest_path = image_config.get("manifest_file") or ""
    if not manifest_path:
        return None

    manifest = load_manifest(manifest_path)
    candidate = match_image_from_manifest(segment.text, manifest)
    if not candidate:
        return None

    assets_dir = Path(image_config.get("assets_dir", "./assets/images"))
    full_path = assets_dir / candidate
    return str(full_path) if full_path.exists() else None


def load_manifest(path: str) -> dict:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return {"images": []}

    with open(manifest_path, encoding="utf-8") as manifest_file:
        data = yaml.safe_load(manifest_file) or {}
    if "images" not in data or not isinstance(data["images"], list):
        data["images"] = []
    return data


def match_image_from_manifest(text: str, manifest: dict) -> str | None:
    images = manifest.get("images", [])
    if not images:
        return None

    text_lower = text.lower()
    best_file = None
    best_score = 0

    for entry in images:
        keywords = entry.get("keywords", [])
        score = sum(1 for keyword in keywords if str(keyword).lower() in text_lower)
        if score > best_score:
            best_score = score
            best_file = entry.get("file")

    return best_file if best_score > 0 else None


def _resolve_explicit_image(image_path: str, cache_dir: Path) -> str | None:
    parsed = urlparse(image_path)
    if parsed.scheme in {"http", "https"}:
        return image_path

    path = Path(image_path).expanduser()
    if path.is_absolute():
        return str(path) if path.exists() else None

    candidates = [
        Path.cwd() / path,
        cache_dir / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None
