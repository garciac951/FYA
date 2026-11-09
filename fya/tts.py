"""Text-to-speech providers. Each returns an audio file plus per-word timings for captions."""
from __future__ import annotations

import asyncio
import base64
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from .media import probe_duration

log = logging.getLogger(__name__)


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Speech:
    audio: Path
    duration: float
    words: list[Word]


DEFAULT_VOICES = {
    ("edge", "en"): "en-US-AndrewMultilingualNeural",
    ("edge", "es"): "es-MX-JorgeNeural",
    # ElevenLabs and OpenAI voices are multilingual: same voice speaks both languages.
    ("elevenlabs", "en"): "pNInz6obpgDQGcFmaJgB",  # "Adam", a stock ElevenLabs voice
    ("elevenlabs", "es"): "pNInz6obpgDQGcFmaJgB",
    ("openai", "en"): "onyx",
    ("openai", "es"): "onyx",
    ("espeak", "en"): "en-us",
    ("espeak", "es"): "es-419",
}


def estimate_words(text: str, duration: float) -> list[Word]:
    """Spread words over the clip in proportion to their length (for providers without timestamps)."""
    tokens = text.split()
    weights = [len(t) + 2 for t in tokens]
    total = sum(weights) or 1
    words, t = [], 0.0
    for tok, w in zip(tokens, weights):
        span = duration * w / total
        words.append(Word(tok, t, t + span))
        t += span
    return words


def _edge(text: str, voice: str, out: Path) -> list[Word]:
    import edge_tts

    async def run() -> list[Word]:
        comm = edge_tts.Communicate(text, voice, rate="+8%", boundary="WordBoundary")
        words: list[Word] = []
        with out.open("wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 1e7
                    words.append(Word(chunk["text"], start, start + chunk["duration"] / 1e7))
        return words

    # The free service sometimes returns no audio (throttling or a hiccup). Retry with backoff.
    last_error: Exception | None = None
    for attempt in range(5):
        if attempt:
            time.sleep(3 * attempt * attempt)  # 3s, 12s, 27s, 48s
        try:
            words = asyncio.run(run())
            if out.exists() and out.stat().st_size > 0:
                time.sleep(0.5)  # be gentle: many small requests in a row get throttled
                return words
            last_error = RuntimeError("empty audio")
        except Exception as e:  # edge_tts raises NoAudioReceived, WebSocketError, aiohttp errors...
            last_error = e
        log.warning("Edge TTS attempt %d failed (%s) for %r", attempt + 1, last_error, text[:60])
    raise RuntimeError(f"Edge TTS returned no audio after 5 tries for {text[:60]!r}") from last_error


def _elevenlabs(text: str, voice: str, api_key: str, out: Path) -> list[Word]:
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps",
        headers={"xi-api-key": api_key},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    out.write_bytes(base64.b64decode(data["audio_base64"]))
    align = data["alignment"]
    words: list[Word] = []
    cur, start, end = "", None, 0.0
    for ch, s, e in zip(align["characters"], align["character_start_times_seconds"],
                        align["character_end_times_seconds"]):
        if ch.isspace():
            if cur:
                words.append(Word(cur, start, end))
            cur, start = "", None
            continue
        if start is None:
            start = s
        cur += ch
        end = e
    if cur:
        words.append(Word(cur, start, end))
    return words


def _openai(text: str, voice: str, api_key: str, out: Path) -> None:
    r = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": "gpt-4o-mini-tts", "voice": voice, "input": text, "response_format": "mp3"},
        timeout=120,
    )
    r.raise_for_status()
    out.write_bytes(r.content)


def _espeak(text: str, voice: str, out: Path) -> None:
    subprocess.run(["espeak-ng", "-v", voice, "-s", "165", "-w", str(out), text], check=True)


def synthesize(text: str, out_base: Path, *, provider: str, lang: str = "en", voice: str = "",
               elevenlabs_key: str = "", openai_key: str = "") -> Speech:
    voice = voice or DEFAULT_VOICES.get((provider, lang), "")
    words: list[Word] | None = None
    if provider == "edge":
        out = out_base.with_suffix(".mp3")
        words = _edge(text, voice, out)
    elif provider == "elevenlabs":
        if not elevenlabs_key:
            raise SystemExit("TTS_PROVIDER=elevenlabs needs ELEVENLABS_API_KEY")
        out = out_base.with_suffix(".mp3")
        words = _elevenlabs(text, voice, elevenlabs_key, out)
    elif provider == "openai":
        if not openai_key:
            raise SystemExit("TTS_PROVIDER=openai needs OPENAI_API_KEY")
        out = out_base.with_suffix(".mp3")
        _openai(text, voice, openai_key, out)
    elif provider == "espeak":
        out = out_base.with_suffix(".wav")
        _espeak(text, voice, out)
    else:
        raise SystemExit(f"Unknown TTS_PROVIDER '{provider}'")

    duration = probe_duration(out)
    if not words:
        words = estimate_words(text, duration)
    return Speech(out, duration, words)
