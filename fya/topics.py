"""Topic pool and posting history."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Topic:
    id: str
    name: str
    weight: float = 1.0
    youtube_category: str = "22"
    angles: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    guardrails: str = ""


def load_topics(path: Path) -> list[Topic]:
    data = json.loads(path.read_text())
    return [Topic(**t) for t in data["topics"]]


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("videos", [])


def save_history(path: Path, videos: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"videos": videos}, indent=2, ensure_ascii=False) + "\n")


def pick_topic(topics: list[Topic], history: list[dict], topic_id: str | None = None) -> Topic:
    """Pick a topic: the one asked for, else rotate so every active topic gets airtime.

    Topics that haven't been posted recently get a boost, so during the exploration
    phase each topic is tested roughly evenly (scaled by weight).
    """
    if topic_id:
        for t in topics:
            if t.id == topic_id:
                return t
        raise SystemExit(f"Unknown topic '{topic_id}'. Known: {', '.join(t.id for t in topics)}")

    active = [t for t in topics if t.weight > 0]
    if not active:
        raise SystemExit("No active topics (all weights are 0).")

    recent = [v["topic"] for v in history[-len(active):]]
    scores = []
    for t in active:
        # How many posts ago was this topic last used? Never used = most overdue.
        try:
            since = recent[::-1].index(t.id) + 1
        except ValueError:
            since = len(active) + 1
        scores.append(t.weight * since * since)
    return random.choices(active, weights=scores, k=1)[0]


def recent_titles(history: list[dict], topic_id: str, n: int = 15) -> list[str]:
    return [v["title"] for v in history if v["topic"] == topic_id][-n:]



CUSTOM_GUARDRAILS = ("This idea came straight from the channel owner. If it touches health, legal, financial or "
                     "safety advice, keep it general and point viewers to a professional.")


def custom_topic(name: str) -> Topic:
    return Topic(id="custom", name=name, youtube_category="22", guardrails=CUSTOM_GUARDRAILS)


def resolve_request(topics: list[Topic], request: str) -> tuple[Topic | None, str | None]:
    """What was typed into the topic box -> (topic, idea).

    A topic id ("dogs") returns that topic and no idea. Anything else is the owner's own idea; the
    topic is returned as None so the scriptwriter picks the best-fitting one from the list.
    """
    request = request.strip()
    for t in topics:
        if request.lower() == t.id:
            return t, None
    return None, request


def recent_titles_any(history: list[dict], n: int = 40) -> list[str]:
    return [v["title"] for v in history][-n:]
