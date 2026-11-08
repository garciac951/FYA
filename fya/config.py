"""Settings, read from environment variables (GitHub secrets/vars in CI, a .env file locally)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


@dataclass
class Settings:
    # Script writing
    anthropic_model: str = field(default_factory=lambda: _env("FYA_MODEL", "claude-opus-5-5"))
    channel_name: str = field(default_factory=lambda: _env("FYA_CHANNEL_NAME", "Porch Talk"))

    # Voice: edge (free), elevenlabs, openai, espeak (offline, robotic: testing only)
    tts_provider: str = field(default_factory=lambda: _env("TTS_PROVIDER", "edge"))
    tts_voice: str = field(default_factory=lambda: _env("TTS_VOICE", ""))
    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))

    # Visuals
    pexels_api_key: str = field(default_factory=lambda: _env("PEXELS_API_KEY"))

    # Upload: none | private | scheduled | public
    upload_mode: str = field(default_factory=lambda: _env("UPLOAD_MODE", "none"))
    publish_hour_utc: int = field(default_factory=lambda: int(_env("PUBLISH_HOUR_UTC", "23")))
    synthetic_media: bool = field(default_factory=lambda: _env("YT_SYNTHETIC_MEDIA", "false").lower() == "true")
    yt_client_id: str = field(default_factory=lambda: _env("YT_CLIENT_ID"))
    yt_client_secret: str = field(default_factory=lambda: _env("YT_CLIENT_SECRET"))
    yt_refresh_token: str = field(default_factory=lambda: _env("YT_REFRESH_TOKEN"))

    # Paths
    topics_file: Path = ROOT / "config" / "topics.json"
    history_file: Path = ROOT / "data" / "history.json"
    output_dir: Path = ROOT / "output"
    music_dir: Path = ROOT / "assets" / "music"
