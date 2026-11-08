"""Word-by-word burned-in captions as an ASS subtitle file."""
from __future__ import annotations

import re
from pathlib import Path

from .tts import Word

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter Black,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,80,80,640,1
Style: Brand,Inter ExtraBold,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,1,0,1,3,0,8,60,60,140,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

HIGHLIGHT = r"{\c&H00D7FF&}"  # warm yellow (ASS colours are BGR)
RESET = r"{\c&HFFFFFF&}"


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean(text: str) -> str:
    text = re.sub(r"[{}\\]", "", text)
    return text.upper()


def build_ass(words: list[Word], total: float, out: Path, brand: str = "", chunk: int = 3) -> Path:
    lines = [HEADER]
    if brand:
        lines.append(f"Dialogue: 0,{_ts(0)},{_ts(total)},Brand,,0,0,0,,{_clean(brand)}\n")
    for i in range(0, len(words), chunk):
        group = words[i:i + chunk]
        group_end = words[i + chunk].start if i + chunk < len(words) else group[-1].end + 0.3
        for j, w in enumerate(group):
            start = w.start
            end = group[j + 1].start if j + 1 < len(group) else group_end
            if end <= start:
                continue
            text = " ".join(
                f"{HIGHLIGHT}{_clean(g.text)}{RESET}" if k == j else _clean(g.text)
                for k, g in enumerate(group)
            )
            lines.append(f"Dialogue: 1,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{text}\n")
    out.write_text("".join(lines))
    return out
