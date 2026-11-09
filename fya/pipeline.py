"""End-to-end: pick topic -> script (EN + ES) -> footage -> per language: voice, render, upload -> history."""
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

SUPPORTED_LANGUAGES = {"en", "es"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50]


def run(settings: Settings, *, topic_id: str | None = None, demo: bool = False,
        upload_mode: str | None = None, keep_work: bool = False) -> dict:
    upload_mode = upload_mode or settings.upload_mode
    if upload_mode not in {"none", "private", "scheduled", "public"}:
        raise SystemExit(f"UPLOAD_MODE must be none/private/scheduled/public, got '{upload_mode}'")
    languages = settings.languages
    unknown = set(languages) - SUPPORTED_LANGUAGES
    if not languages or unknown:
        raise SystemExit(f"FYA_LANGUAGES must be a comma list of {sorted(SUPPORTED_LANGUAGES)}, got {languages}")

    topics = load_topics(settings.topics_file)
    history = load_history(settings.history_file)
    topic = pick_topic(topics, history, "bermuda-grass-texas" if demo and not topic_id else topic_id)
    log.info("Topic: %s", topic.name)

    script = demo_script() if demo else generate_script(
        topic, recent_titles(history, topic.id), model=settings.anthropic_model,
        channel_en=settings.channel_name, channel_es=settings.channel_name_es)
    log.info("Title: %s | %s", script.title, script.title_es)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    out_dir = settings.output_dir / f"{stamp}-{_slug(script.title)}"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    (out_dir / "script.json").write_text(script.model_dump_json(indent=2))

    # Footage is shared by every language version.
    used: set[int] = set()
    clips = [get_clip(seg.visual_query, work / f"clip{i:02d}.mp4", settings.pexels_api_key, used)
             for i, seg in enumerate(script.segments)]

    record = {
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topic": topic.id,
        "title": script.title,
        "upload_mode": upload_mode,
        "versions": {},
    }
    errors: list[str] = []

    for lang in languages:
        loc = script.localized(lang)
        lang_work = work / lang
        lang_work.mkdir(exist_ok=True)
        try:
            segments = []
            for i, (text, clip) in enumerate(zip(loc.narrations, clips)):
                speech = synthesize(text, lang_work / f"tts{i:02d}", provider=settings.tts_provider, lang=lang,
                                    voice=settings.voice(lang), elevenlabs_key=settings.elevenlabs_api_key,
                                    openai_key=settings.openai_api_key)
                segments.append(RenderSegment(speech, clip))
            video = render_short(segments, out_dir / f"short-{lang}.mp4", lang_work,
                                 brand=settings.channel(lang), music_dir=settings.music_dir)
            log.info("[%s] Rendered %s", lang, video)
            # Copy-paste sheet for posting by hand.
            video.with_suffix(".txt").write_text(
                f"TITLE\n{loc.title}\n\nDESCRIPTION\n{loc.description}\n\nTAGS\n{', '.join(loc.tags)}\n",
                encoding="utf-8")
            version = {"title": loc.title, "file": str(video.relative_to(settings.output_dir.parent))}

            if upload_mode != "none":
                if lang == "es" and not settings.yt_refresh_token_es:
                    log.warning("YT_REFRESH_TOKEN_ES not set: posting the Spanish version to the English channel")
                publish_at = (next_publish_time(settings.publish_hour(lang), history, lang)
                              if upload_mode == "scheduled" else None)
                video_id = upload_video(
                    video, title=loc.title, description=loc.description, tags=loc.tags,
                    category_id=topic.youtube_category, lang=lang,
                    privacy="public" if upload_mode == "public" else "private",
                    publish_at=publish_at, synthetic_media=settings.synthetic_media,
                    client_id=settings.yt_client_id, client_secret=settings.yt_client_secret,
                    refresh_token=settings.refresh_token(lang),
                )
                version["youtube_id"] = video_id
                version["url"] = f"https://youtube.com/shorts/{video_id}"
                if publish_at:
                    version["publish_at"] = publish_at.isoformat()
            record["versions"][lang] = version
        except SystemExit:
            raise
        except Exception as e:  # keep going so one language failing doesn't lose the other
            log.exception("[%s] failed", lang)
            errors.append(f"{lang}: {e}")

    (out_dir / "metadata.json").write_text(json.dumps(record, indent=2, ensure_ascii=False))
    if not demo and record["versions"]:
        history.append(record)
        save_history(settings.history_file, history)
    if not keep_work:
        shutil.rmtree(work, ignore_errors=True)
    if errors:
        raise RuntimeError("Some versions failed: " + "; ".join(errors))
    return record
