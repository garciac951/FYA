"""Choose the footage for each segment: Claude looks at candidate thumbnails and picks the best match."""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

import anthropic
import requests
from pydantic import BaseModel

from .visuals import Candidate, FootageSearch, download

log = logging.getLogger(__name__)

MISSING = -1  # the AI skipped this segment: fall back to tag ranking for it
THUMB_WIDTH = 384  # small previews keep the request cheap; enough to recognise the subject


class SegmentChoice(BaseModel):
    segment: int
    candidate: int  # 0 = none of the candidates fit


class ClipChoices(BaseModel):
    choices: list[SegmentChoice]


PICKER_PROMPT = """You pick the background footage (B-roll) for a vertical YouTube Short. For each numbered \
segment you get the narration spoken over it and a few candidate stock clips, shown as preview frames.

Pick the candidate that best shows what that narration is talking about:
- The right subject matters most: the right animal, sport, tool, food, device or task. A golden retriever \
for a dog tip is fine; a cat is not. Soccer is not American football. A generic laptop is fine for a Windows tip.
- Real footage of the thing beats loosely related scenery.
- Avoid clips with visible text, logos, watermarks, or a person talking to the camera (it looks like a presenter \
who isn't speaking).
- The clip will be cropped to vertical, so prefer subjects near the center.
- Each candidate can be used only once in the whole Short.

Answer 0 for a segment only when every candidate would confuse or mislead the viewer; an imperfect but \
on-topic clip is better than none. Return one choice per segment."""


def _thumb_b64(url: str) -> str | None:
    from PIL import Image

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception as e:  # network error or unreadable image
        log.warning("Thumbnail failed (%s): %s", url, e)
        return None
    if img.width > THUMB_WIDTH:
        img = img.resize((THUMB_WIDTH, round(img.height * THUMB_WIDTH / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def ai_choose(narrations: list[str], candidates: list[list[Candidate]], model: str) -> list[int | None] | None:
    """Chosen candidate index per segment (None = none fit, MISSING = not answered), or None if the AI
    pick isn't possible at all."""
    content: list[dict] = [{"type": "text", "text": "Here are the segments and their candidates."}]
    shown: list[dict[int, int]] = []  # per segment: label number -> index in candidates list
    for s, (text, cands) in enumerate(zip(narrations, candidates), start=1):
        content.append({"type": "text", "text": f"\n## Segment {s}\nNarration: {text}"})
        labels: dict[int, int] = {}
        for idx, c in enumerate(cands):
            thumb = _thumb_b64(c.thumb_url) if c.thumb_url else None
            if not thumb:
                continue
            label = len(labels) + 1
            labels[label] = idx
            content.append({"type": "text", "text": f"Segment {s}, candidate {label} (tags: {', '.join(sorted(c.tags))[:120]}):"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": thumb}})
        if not labels:
            content.append({"type": "text", "text": "(no candidates for this segment; answer 0)"})
        shown.append(labels)

    if not any(shown):
        return None
    try:
        response = anthropic.Anthropic().beta.messages.parse(
            model=model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=PICKER_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_format=ClipChoices,
        )
    except anthropic.APIError as e:
        log.warning("AI clip picking failed, using tag ranking instead: %s", e)
        return None
    if response.stop_reason in ("refusal", "max_tokens") or response.parsed_output is None:
        log.warning("AI clip picking gave no answer (stop_reason=%s), using tag ranking", response.stop_reason)
        return None

    picks: list[int | None] = [MISSING] * len(narrations)
    for choice in response.parsed_output.choices:
        s = choice.segment - 1
        if 0 <= s < len(picks):
            picks[s] = shown[s].get(choice.candidate) if choice.candidate else None
    return picks


def pick_footage(narrations: list[str], queries: list[list[str]], work: Path, *, search: FootageSearch,
                 model: str, use_ai: bool) -> list[Path | None]:
    """Download one clip per segment (None = use a gradient background)."""
    if not search.enabled:
        log.warning("No PIXABAY_API_KEY or PEXELS_API_KEY set: using gradient backgrounds")
        return [None] * len(narrations)

    candidates = [search.candidates(q) for q in queries]
    picks = ai_choose(narrations, candidates, model) if use_ai else None
    if picks is None:
        picks = [None] * len(candidates)
        mode = "tag ranking"
    else:
        mode = "AI pick"

    used: set[tuple[str, int]] = set()
    clips: list[Path | None] = []
    for i, (cands, pick) in enumerate(zip(candidates, picks)):
        dest = work / f"clip{i:02d}.mp4"
        if pick is None and mode == "AI pick":
            order = []  # the AI looked and rejected every candidate
        elif pick is None or pick == MISSING:
            order = cands  # tag ranking
        else:
            order = [cands[pick]] + [c for j, c in enumerate(cands) if j != pick]  # chosen, then backups
        chosen = None
        for c in order:
            if c.key in used:
                continue
            if download(c, dest):
                chosen = c
                break
        if chosen:
            used.add(chosen.key)
            how = "tag ranking" if (mode == "tag ranking" or pick == MISSING) else "AI pick"
            log.info("Segment %d: %s %s via %s (query %r, tags: %s)", i + 1, chosen.source, chosen.id, how,
                     chosen.query, ", ".join(sorted(chosen.tags))[:80])
            clips.append(dest)
        else:
            log.warning("Segment %d: no suitable clip, using a gradient background", i + 1)
            clips.append(None)
    return clips
