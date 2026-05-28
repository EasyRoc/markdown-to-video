from src.teaching_models import Storyboard, Timeline, TimelineScene


def build_timeline(
    storyboard: Storyboard,
    audio_durations: dict[str, float] | None = None,
) -> Timeline:
    durations = audio_durations or {}
    timeline = Timeline()
    cursor = 0.0
    for scene in storyboard.scenes:
        duration = float(durations.get(scene.id, scene.duration_hint))
        frame_path = f"cache/frames/{scene.id}.png"
        audio_path = f"cache/audio/{scene.id}.mp3"
        timeline.scenes.append(
            TimelineScene(
                scene_id=scene.id,
                start=round(cursor, 3),
                duration=round(duration, 3),
                image_path=frame_path,
                audio_path=audio_path,
                transition=scene.annotations.get("transition", "none"),
            )
        )
        timeline.subtitles.append(
            {
                "scene_id": scene.id,
                "start": round(cursor, 3),
                "end": round(cursor + duration, 3),
                "text": scene.narration,
            }
        )
        timeline.assets.append(frame_path)
        cursor += duration
    return timeline
