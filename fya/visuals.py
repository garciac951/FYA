"""Background footage: Pexels stock video, or a generated gradient when none is available."""
from __future__ import annotations

import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

PEXELS_SEARCH = "https://api.pexels.com/videos/search"


def _best_file(video: dict) -> dict | None:
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("height")]
    if not files:
        return None
    # Prefer portrait files at or above 1280px tall, smallest such file to keep downloads light.
    tall = [f for f in files if f["height"] >= 1280 and f["height"] >= f.get("width", 0)]
    pool = tall or [f for f in files if f["height"] >= 720] or files
    return min(pool, key=lambda f: f["height"] * (f.get("width") or 1))


def fetch_pexels(query: str, dest: Path, api_key: str, exclude: set[int]) -> Path | None:
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
            if video["id"] in exclude or video.get("duration", 0) < 4:
                continue
            f = _best_file(video)
            if not f:
                continue
            try:
                with requests.get(f["link"], stream=True, timeout=120) as dl:
                    dl.raise_for_status()
                    with dest.open("wb") as out:
                        for chunk in dl.iter_content(1 << 20):
                            out.write(chunk)
            except requests.RequestException as e:
                log.warning("Download failed for Pexels video %s: %s", video["id"], e)
                continue
            exclude.add(video["id"])
            log.info("Pexels %s for %r", video["id"], query)
            return dest
    return None


def get_clip(query: str, dest: Path, api_key: str, exclude: set[int]) -> Path | None:
    """Return a downloaded clip path, or None to tell the renderer to use a gradient."""
    if not api_key:
        return None
    clip = fetch_pexels(query, dest, api_key, exclude)
    if clip is None and len(query.split()) > 1:
        # Retry with a broader query (drop the last word).
        clip = fetch_pexels(" ".join(query.split()[:-1]), dest, api_key, exclude)
    return clip
