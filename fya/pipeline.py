"""End-to-end: pick topic -> script -> voice -> footage -> render -> (upload) -> history."""
from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone

from .config import Settings
from .render import RenderSegment, render_short
from .scriptgen import demo_script, generate_script
from .topics import load_history, load_topics, pick_topic, recent_titles, save_history
from .tts import synthesize
from .upload import next_publish_time, upload_video
from .visuals import get_clip

log = logging.getLogger(__name__)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50]


def run(settings: Settings, *, topic_id: str | None = None, demo: bool = False,
        upload_mode: str | None = None, keep_work: bool = False) -> dict:
    upload_mode = upload_mode or settings.upload_mode
    if upload_mode not in {"none", "private", "scheduled", "public"}:
        raise SystemExit(f"UPLOAD_MODE must be none/private/scheduled/public, got '{upload_mode}'")

    topics = load_topics(settings.topics_file)
    history = load_history(settings.history_file)
    topic = pick_topic(topics, history, "bermuda-grass-texas" if demo and not topic_id else topic_id)
    log.info("Topic: %s", topic.name)

    script = demo_script() if demo else generate_script(
        topic, recent_titles(history, topic.id), model=settings.anthropic_model, channel=settings.channel_name)
    log.info("Title: %s", script.title)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    out_dir = settings.output_dir / f"{stamp}-{_slug(script.title)}"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    (out_dir / "script.json").write_text(script.model_dump_json(indent=2))

    used: set[int] = set()
    segments = []
    for i, seg in enumerate(script.segments):
        speech = synthesize(seg.narration, work / f"tts{i:02d}", provider=settings.tts_provider,
                            voice=settings.tts_voice, elevenlabs_key=settings.elevenlabs_api_key,
                            openai_key=settings.openai_api_key)
        clip = get_clip(seg.visual_query, work / f"clip{i:02d}.mp4", settings.pexels_api_key, used)
        segments.append(RenderSegment(speech, clip))

    video = render_short(segments, out_dir / "short.mp4", work,
                         brand=settings.channel_name, music_dir=settings.music_dir)
    log.info("Rendered %s", video)

    record = {
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic": topic.id,
        "title": script.title,
        "file": str(video.relative_to(settings.output_dir.parent)),
        "upload_mode": upload_mode,
    }

    if upload_mode != "none":
        publish_at = next_publish_time(settings.publish_hour_utc, history) if upload_mode == "scheduled" else None
        video_id = upload_video(
            video, title=script.title, description=script.description, tags=script.tags,
            category_id=topic.youtube_category,
            privacy="public" if upload_mode == "public" else "private",
            publish_at=publish_at, synthetic_media=settings.synthetic_media,
            client_id=settings.yt_client_id, client_secret=settings.yt_client_secret,
            refresh_token=settings.yt_refresh_token,
        )
        record["youtube_id"] = video_id
        record["url"] = f"https://youtube.com/shorts/{video_id}"
        if publish_at:
            record["publish_at"] = publish_at.isoformat()

    (out_dir / "metadata.json").write_text(json.dumps(record, indent=2))
    if not demo:
        history.append(record)
        save_history(settings.history_file, history)
    if not keep_work:
        shutil.rmtree(work, ignore_errors=True)
    return record
