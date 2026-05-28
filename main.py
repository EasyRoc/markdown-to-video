#!/usr/bin/env python3
import argparse
import asyncio
import sys
from pathlib import Path

from src.composer import compose_video
from src.config import load_config
from src.parser import Segment, parse_markdown
from src.renderer import render_segment
from src.teaching_pipeline import (
    build_teaching_assets,
    dry_run_summary,
    write_dry_run_artifacts,
)
from src.tts import generate_audio


def _segment_tts_config(segment: Segment, config: dict) -> dict:
    tts_config = dict(config["tts"])
    if segment.voice:
        tts_config["voice"] = segment.voice
    if segment.speed:
        tts_config["speed"] = segment.speed
    if segment.pitch:
        tts_config["pitch"] = segment.pitch
    return tts_config


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert markdown files to video with AI voiceover."
    )
    parser.add_argument("markdown", help="Path to markdown file")
    parser.add_argument("-c", "--config", help="Path to config YAML file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only and show segments without generating media",
    )
    parser.add_argument(
        "--v3",
        action="store_true",
        help="Use the V3 teaching director before rendering",
    )
    args = parser.parse_args()

    md_path = Path(args.markdown)
    if not md_path.exists():
        print(f"Error: file not found: {args.markdown}", file=sys.stderr)
        sys.exit(1)

    text = md_path.read_text(encoding="utf-8")
    if not text.strip():
        print("Error: file has no content", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    max_chars = config["render"]["max_chars_per_segment"]
    assets = None

    if args.v3:
        assets = build_teaching_assets(text, config)
        segments = assets.segments
    else:
        segments = parse_markdown(text, max_chars_per_segment=max_chars)

    if not segments:
        print("Error: no valid content found in file", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        if args.v3:
            print(dry_run_summary(assets))
            paths = write_dry_run_artifacts(assets, config)
            print(f"Artifacts written to: {paths['storyboard'].parent.parent}")
        else:
            for segment in segments:
                title = segment.title or "(no title)"
                extra = []
                if segment.voice:
                    extra.append(f"voice={segment.voice}")
                if segment.layout != "text-only":
                    extra.append(f"layout={segment.layout}")
                if segment.image_path:
                    extra.append(f"image={segment.image_path}")
                if segment.highlight:
                    extra.append(f"highlight={segment.highlight}")
                extra_text = ", " + ", ".join(extra) if extra else ""
                print(
                    f"Segment {segment.index}: "
                    f"type={segment.type}, title={title}, chars={len(segment.text)}"
                    f"{extra_text}"
                )
        return

    output_dir = Path(config["video"]["output_dir"])
    output_path = output_dir / f"{md_path.stem}.mp4"
    cache_audio = Path("./cache/audio")
    cache_frames = Path("./cache/frames")

    print(f"Generating audio for {len(segments)} segments...")
    for position, segment in enumerate(segments, start=1):
        title = segment.title or f"segment {segment.index}"
        print(f"  [{position}/{len(segments)}] {title}")
        tts_config = dict(config)
        tts_config["tts"] = _segment_tts_config(segment, config)
        await generate_audio(segment, tts_config, str(cache_audio))

    print(f"Rendering {len(segments)} frames...")
    for position, segment in enumerate(segments, start=1):
        print(f"  [{position}/{len(segments)}] segment {segment.index}")
        render_segment(segment, config, str(cache_frames))

    print("Composing video...")
    compose_video(
        segments,
        str(output_path),
        config,
        str(cache_frames),
        str(cache_audio),
    )


if __name__ == "__main__":
    asyncio.run(main())
