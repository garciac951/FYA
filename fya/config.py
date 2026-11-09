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
    channel_name: str = field(default_factory=lambda: _env("FYA_CHANNEL_NAME", "Porch Talk Pro"))
    channel_name_es: str = field(default_factory=lambda: _env("FYA_CHANNEL_NAME_ES", "Plática de Porche"))
    # Which versions to make for every Short: "en,es" (default), "en" or "es"
    languages: list[str] = field(default_factory=lambda: [
        x.strip() for x in _env("FYA_LANGUAGES", "en,es").split(",") if x.strip()])

    # Voice: edge (free), elevenlabs, openai, espeak (offline, robotic: testing only)
    tts_provider: str = field(default_factory=lambda: _env("TTS_PROVIDER", "edge"))
    tts_voice: str = field(default_factory=lambda: _env("TTS_VOICE", ""))
    tts_voice_es: str = field(default_factory=lambda: _env("TTS_VOICE_ES", ""))
    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))

    # Visuals
    pexels_api_key: str = field(default_factory=lambda: _env("PEXELS_API_KEY"))

    # Upload: none | private | scheduled | public
    upload_mode: str = field(default_factory=lambda: _env("UPLOAD_MODE", "none"))
    publish_hour_utc: int = field(default_factory=lambda: int(_env("PUBLISH_HOUR_UTC", "23")))
    publish_hour_utc_es: int = field(default_factory=lambda: int(_env("PUBLISH_HOUR_UTC_ES", "1")))
    synthetic_media: bool = field(default_factory=lambda: _env("YT_SYNTHETIC_MEDIA", "false").lower() == "true")
    yt_client_id: str = field(default_factory=lambda: _env("YT_CLIENT_ID"))
    yt_client_secret: str = field(default_factory=lambda: _env("YT_CLIENT_SECRET"))
    yt_refresh_token: str = field(default_factory=lambda: _env("YT_REFRESH_TOKEN"))
    # Token for the Spanish channel. Leave unset to post the Spanish version to the same channel.
    yt_refresh_token_es: str = field(default_factory=lambda: _env("YT_REFRESH_TOKEN_ES"))

    def channel(self, lang: str) -> str:
        return self.channel_name_es if lang == "es" else self.channel_name

    def voice(self, lang: str) -> str:
        return self.tts_voice_es if lang == "es" else self.tts_voice

    def publish_hour(self, lang: str) -> int:
        return self.publish_hour_utc_es if lang == "es" else self.publish_hour_utc

    def refresh_token(self, lang: str) -> str:
        if lang == "es" and self.yt_refresh_token_es:
            return self.yt_refresh_token_es
        return self.yt_refresh_token

    # Paths
    topics_file: Path = ROOT / "config" / "topics.json"
    history_file: Path = ROOT / "data" / "history.json"
    output_dir: Path = ROOT / "output"
    music_dir: Path = ROOT / "assets" / "music"
