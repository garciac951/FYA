"""Assemble the vertical 1080x1920 Short with ffmpeg."""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from .captions import build_ass
from .media import probe_duration, run_ffmpeg
from .tts import Speech, Word

W, H, FPS = 1080, 1920, 30
GRADIENTS = [
    ("0x0f2027", "0x2c5364"), ("0x1d2b64", "0x3a6073"), ("0x134e5e", "0x71b280"),
    ("0x42275a", "0x734b6d"), ("0x232526", "0x414345"), ("0x3a1c71", "0xd76d77"),
]


@dataclass
class RenderSegment:
    speech: Speech
    clip: Path | None


def _video_segment(seg: RenderSegment, dur: float, out: Path, idx: int) -> None:
    vf_common = f"fps={FPS},setsar=1,format=yuv420p"
    enc = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS)]
    if seg.clip:
        # Random start inside longer clips so reused footage doesn't look identical.
        clip_len = probe_duration(seg.clip)
        start = random.uniform(0, max(0.0, clip_len - dur - 0.5)) if clip_len > dur + 1 else 0.0
        zoom = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"scale=iw*1.08:ih*1.08,crop={W}:{H}:x='(iw-{W})*t/{dur:.2f}':y='(ih-{H})/2'")
        run_ffmpeg(["-ss", f"{start:.2f}", "-stream_loop", "-1", "-i", str(seg.clip), "-t", f"{dur:.3f}",
                    "-vf", f"{zoom},{vf_common}", *enc, str(out)])
    else:
        c0, c1 = GRADIENTS[idx % len(GRADIENTS)]
        src = f"gradients=s={W}x{H}:c0={c0}:c1={c1}:speed=0.015:d={dur:.3f}:r={FPS}"
        run_ffmpeg(["-f", "lavfi", "-i", src, "-vf", vf_common, *enc, str(out)])


def _concat(files: list[Path], out: Path, work: Path, name: str) -> None:
    lst = work / f"{name}.txt"
    lst.write_text("".join(f"file '{f.resolve()}'\n" for f in files))
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])


def render_short(segments: list[RenderSegment], out: Path, work: Path, *,
                 brand: str = "", music_dir: Path | None = None) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    videos, audios, words = [], [], []
    t = 0.0
    for i, seg in enumerate(segments):
        gap = 0.6 if i == len(segments) - 1 else 0.12
        dur = seg.speech.duration + gap
        a = work / f"a{i:02d}.wav"
        run_ffmpeg(["-i", str(seg.speech.audio), "-af", f"apad=whole_dur={dur:.3f}",
                    "-t", f"{dur:.3f}", "-ar", "48000", "-ac", "2", str(a)])
        v = work / f"v{i:02d}.mp4"
        _video_segment(seg, dur, v, i)
        audios.append(a)
        videos.append(v)
        words += [Word(w.text, w.start + t, w.end + t) for w in seg.speech.words]
        t += dur

    video = work / "video.mp4"
    narration = work / "narration.wav"
    _concat(videos, video, work, "videos")
    _concat(audios, narration, work, "audios")
    ass = build_ass(words, t, work / "captions.ass", brand=brand)

    inputs = ["-i", str(video), "-i", str(narration)]
    music = sorted(p for p in (music_dir.glob("*") if music_dir else []) if p.suffix.lower() in {".mp3", ".m4a", ".wav", ".ogg"})
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(random.choice(music))]
        afilter = ("[2:a]volume=0.10,afade=t=out:st={end:.2f}:d=1[m];"
                   "[1:a][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[a]").format(end=max(0, t - 1))
    else:
        afilter = "[1:a]loudnorm=I=-14:TP=-1.5[a]"
    vfilter = f"[0:v]subtitles='{ass.resolve()}'[v]"

    run_ffmpeg([*inputs, "-filter_complex", f"{vfilter};{afilter}", "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{t:.3f}",
                "-movflags", "+faststart", str(out)])
    return out
