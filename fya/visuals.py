"""Stock footage search (Pixabay, Pexels): returns ranked candidate clips with preview thumbnails."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests

log = logging.getLogger(__name__)

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH = "https://pixabay.com/api/videos/"
MAX_DOWNLOAD_BYTES = 80 * 1024 * 1024
STOP = {"the", "and", "with", "for", "close", "closeup", "shot", "view", "slow", "motion", "video", "stock"}


@dataclass
class Candidate:
    source: str
    id: int
    tags: set[str]
    width: int
    height: int
    download_url: str
    thumb_url: str
    query: str
    query_index: int  # 0 = the most specific search for this segment
    rank: int  # position in that search's results
    score: float = field(default=0.0)

    @property
    def key(self) -> tuple[str, int]:
        return (self.source, self.id)

    @property
    def portrait(self) -> bool:
        return self.height > self.width


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3 and w not in STOP}


def _match(a: str, b: str) -> bool:
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def score(c: Candidate) -> float:
    """Relevance first (search words found in the clip's tags), then search specificity and rank.

    Orientation is only a small tie-breaker: a relevant horizontal clip beats an irrelevant vertical one.
    """
    q = words(c.query)
    overlap = sum(1 for w in q if any(_match(w, t) for t in c.tags)) / max(1, len(q))
    return overlap * 10 + (2 - 0.5 * c.query_index) + (1 - c.rank / 40) + (0.3 if c.portrait else 0)


# --- Pixabay -----------------------------------------------------------------

def _pixabay_rendition(hit: dict) -> dict | None:
    """Smallest rendition at least 1080px tall (so the vertical crop isn't blurry), without huge downloads."""
    renditions = [v for v in (hit.get("videos") or {}).values()
                  if v.get("url") and v.get("width") and v.get("height")]
    if not renditions:
        return None
    usable = [v for v in renditions if (v.get("size") or 0) <= MAX_DOWNLOAD_BYTES] or renditions
    good = [v for v in usable if v["height"] >= 1080]
    return min(good, key=lambda v: v["height"]) if good else max(usable, key=lambda v: v["height"])


def _pixabay_thumb(hit: dict) -> str:
    videos = hit.get("videos") or {}
    for size in ("tiny", "small", "medium", "large"):
        thumb = (videos.get(size) or {}).get("thumbnail")
        if thumb:
            return thumb
    return ""


def search_pixabay(query: str, api_key: str, query_index: int) -> list[Candidate]:
    params = {"key": api_key, "q": query[:100], "video_type": "film", "safesearch": "true", "per_page": 20}
    try:
        r = requests.get(PIXABAY_SEARCH, params=params, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("Pixabay search failed for %r: %s", query, str(e).replace(api_key, "***"))
        return []
    out = []
    for rank, hit in enumerate(r.json().get("hits", [])):
        rend = _pixabay_rendition(hit)
        if not rend or (hit.get("duration") or 0) < 4:
            continue
        out.append(Candidate("pixabay", hit["id"], words(hit.get("tags", "")), rend["width"], rend["height"],
                             rend["url"], _pixabay_thumb(hit), query, query_index, rank))
    return out


# --- Pexels ------------------------------------------------------------------

def _pexels_file(video: dict) -> dict | None:
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height")]
    if not files:
        return None
    good = [f for f in files if f["height"] >= 1080]
    return min(good, key=lambda f: f["height"]) if good else max(files, key=lambda f: f["height"])


def search_pexels(query: str, api_key: str, query_index: int) -> list[Candidate]:
    try:
        r = requests.get(PEXELS_SEARCH, headers={"Authorization": api_key},
                         params={"query": query, "per_page": 15}, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("Pexels search failed for %r: %s", query, e)
        return []
    out = []
    for rank, video in enumerate(r.json().get("videos", [])):
        f = _pexels_file(video)
        if not f or video.get("duration", 0) < 4:
            continue
        slug_words = words(video.get("url", "").rstrip("/").rsplit("/", 1)[-1])  # .../video/man-fishing-in-river-123/
        out.append(Candidate("pexels", video["id"], slug_words, f.get("width") or 0, f["height"], f["link"],
                             video.get("image", ""), query, query_index, rank))
    return out


# --- Gathering & download ------------------------------------------------------

class FootageSearch:
    """Searches the configured libraries, caching results within a run."""

    def __init__(self, pixabay_key: str = "", pexels_key: str = ""):
        self.pixabay_key, self.pexels_key = pixabay_key, pexels_key
        self._cache: dict[str, list[Candidate]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.pixabay_key or self.pexels_key)

    def search(self, query: str, query_index: int) -> list[Candidate]:
        if query not in self._cache:
            found = []
            if self.pixabay_key:
                found += search_pixabay(query, self.pixabay_key, query_index)
            if self.pexels_key:
                found += search_pexels(query, self.pexels_key, query_index)
            self._cache[query] = found
        # Copies, so per-segment query_index/score don't leak between segments.
        return [Candidate(**{**c.__dict__, "query_index": query_index}) for c in self._cache[query]]

    def candidates(self, queries: list[str], limit: int = 5) -> list[Candidate]:
        """Best `limit` distinct clips across this segment's searches, ranked by score."""
        pool: dict[tuple[str, int], Candidate] = {}
        for i, q in enumerate(q for q in queries if q.strip()):
            for c in self.search(q.strip(), i):
                c.score = score(c)
                if c.key not in pool or pool[c.key].score < c.score:
                    pool[c.key] = c
        return sorted(pool.values(), key=lambda c: c.score, reverse=True)[:limit]


def download(c: Candidate, dest: Path) -> bool:
    try:
        with requests.get(c.download_url, stream=True, timeout=120) as dl:
            dl.raise_for_status()
            with dest.open("wb") as out:
                for chunk in dl.iter_content(1 << 20):
                    out.write(chunk)
        return dest.stat().st_size > 0
    except requests.RequestException as e:
        log.warning("Download failed for %s %s: %s", c.source, c.id, e)
        return False
