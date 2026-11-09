"""Background footage from free stock libraries (Pixabay, Pexels), or a generated gradient as a fallback."""
from __future__ import annotations

import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH = "https://pixabay.com/api/videos/"
MAX_DOWNLOAD_BYTES = 80 * 1024 * 1024


def _download(url: str, dest: Path) -> bool:
    try:
        with requests.get(url, stream=True, timeout=120) as dl:
            dl.raise_for_status()
            with dest.open("wb") as out:
                for chunk in dl.iter_content(1 << 20):
                    out.write(chunk)
        return True
    except requests.RequestException as e:
        log.warning("Download failed for %s: %s", url, e)
        return False


# --- Pixabay -----------------------------------------------------------------

def _pixabay_best(hit: dict) -> dict | None:
    """Pick the rendition to download: tall enough to crop to 1080x1920 without a big upscale, not huge."""
    renditions = [v for v in (hit.get("videos") or {}).values()
                  if v.get("url") and v.get("width") and v.get("height")]
    if not renditions:
        return None
    usable = [v for v in renditions if (v.get("size") or 0) <= MAX_DOWNLOAD_BYTES] or renditions
    good = [v for v in usable if v["height"] >= 1080]
    # Smallest rendition that's at least 1080 tall, else the tallest available.
    return min(good, key=lambda v: v["height"]) if good else max(usable, key=lambda v: v["height"])


def pick_pixabay(hits: list[dict], exclude: set) -> tuple[dict, dict] | None:
    candidates = []
    for hit in hits:
        key = ("pixabay", hit.get("id"))
        if key in exclude or (hit.get("duration") or 0) < 4:
            continue
        r = _pixabay_best(hit)
        if r:
            candidates.append((hit, r))
    if not candidates:
        return None
    # Portrait clips first (no cropping needed), keeping Pixabay's relevance order otherwise.
    portrait = [c for c in candidates if c[1]["height"] > c[1]["width"]]
    return (portrait or candidates)[0]


def fetch_pixabay(query: str, dest: Path, api_key: str, exclude: set) -> Path | None:
    params = {"key": api_key, "q": query[:100], "video_type": "film", "safesearch": "true", "per_page": 30}
    try:
        r = requests.get(PIXABAY_SEARCH, params=params, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning("Pixabay search failed for %r: %s", query, str(e).replace(api_key, "***"))
        return None
    choice = pick_pixabay(r.json().get("hits", []), exclude)
    if not choice:
        return None
    hit, rendition = choice
    if not _download(rendition["url"], dest):
        return None
    exclude.add(("pixabay", hit["id"]))
    log.info("Pixabay %s (%sx%s) for %r", hit["id"], rendition["width"], rendition["height"], query)
    return dest


# --- Pexels ------------------------------------------------------------------

def _pexels_best(video: dict) -> dict | None:
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height")]
    if not files:
        return None
    # Prefer portrait files at or above 1280px tall, smallest such file to keep downloads light.
    tall = [f for f in files if f["height"] >= 1280 and f["height"] >= f.get("width", 0)]
    pool = tall or [f for f in files if f["height"] >= 720] or files
    return min(pool, key=lambda f: f["height"] * (f.get("width") or 1))


def fetch_pexels(query: str, dest: Path, api_key: str, exclude: set) -> Path | None:
    for orientation in ("portrait", None):
        params = {"query": query, "per_page": 15, "size": "medium"}
        if orientation:
            params["orientation"] = orientation
        try:
            r = requests.get(PEXELS_SEARCH, headers={"Authorization": api_key}, params=params, timeout=30)
            r.raise_for_status()
        except requests.RequestException as e:
            log.warning("Pexels search failed for %r: %s", query, e)
            return None
        for video in r.json().get("videos", []):
            key = ("pexels", video["id"])
            if key in exclude or video.get("duration", 0) < 4:
                continue
            f = _pexels_best(video)
            if not f or not _download(f["link"], dest):
                continue
            exclude.add(key)
            log.info("Pexels %s for %r", video["id"], query)
            return dest
    return None


# --- Entry point -------------------------------------------------------------

def get_clip(query: str, dest: Path, exclude: set, *, pixabay_key: str = "", pexels_key: str = "") -> Path | None:
    """Return a downloaded clip path, or None to tell the renderer to use a gradient.

    Tries each configured library with the full query, then with a broader query (last word dropped).
    """
    queries = [query]
    if len(query.split()) > 1:
        queries.append(" ".join(query.split()[:-1]))
    for q in queries:
        if pixabay_key and fetch_pixabay(q, dest, pixabay_key, exclude):
            return dest
        if pexels_key and fetch_pexels(q, dest, pexels_key, exclude):
            return dest
    log.warning("No stock clip found for %r; using a gradient background", query)
    return None
