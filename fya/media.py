"""Small ffmpeg/ffprobe helpers."""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{result.stderr[-2000:]}")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


def loudness_gain_db(path: Path, target_lufs: float = -14.0) -> float:
    """Gain (dB) that brings the file to target_lufs, measured with a loudnorm analysis pass.

    A constant gain is used instead of loudnorm's dynamic mode, which can emit NaN samples on some
    inputs and crash the AAC encoder. Returns 0 if the file can't be measured (e.g. silence).
    """
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    text = result.stderr
    start, end = text.rfind("{"), text.rfind("}")
    try:
        measured = float(json.loads(text[start:end + 1])["input_i"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return 0.0
    if not math.isfinite(measured) or measured < -70:
        return 0.0
    return max(-20.0, min(20.0, target_lufs - measured))
