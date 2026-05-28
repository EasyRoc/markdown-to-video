import hashlib
from pathlib import Path

from src.teaching_models import Storyboard, TeachingScript, Timeline


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def write_teaching_artifacts(
    cache_root: str | Path,
    script: TeachingScript,
    storyboard: Storyboard,
    timeline: Timeline,
) -> dict[str, Path]:
    root = Path(cache_root)
    identifier = storyboard.source_hash or script.source_hash or "storyboard"
    paths = {
        "script": root / "script" / f"{identifier}.json",
        "storyboard": root / "storyboard" / f"{identifier}.json",
        "timeline": root / "timeline" / f"{identifier}.json",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    paths["script"].write_text(script.to_json(), encoding="utf-8")
    paths["storyboard"].write_text(storyboard.to_json(), encoding="utf-8")
    paths["timeline"].write_text(timeline.to_json(), encoding="utf-8")
    return paths
