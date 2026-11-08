"""Upload to YouTube with the Data API v3."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def next_publish_time(hour_utc: int, history: list[dict]) -> datetime:
    """Next free slot at hour_utc, after any video already scheduled."""
    now = datetime.now(timezone.utc)
    slot = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    if slot <= now + timedelta(minutes=30):
        slot += timedelta(days=1)
    scheduled = {v.get("publish_at") for v in history if v.get("publish_at")}
    while slot.isoformat() in scheduled:
        slot += timedelta(days=1)
    return slot


def upload_video(path: Path, *, title: str, description: str, tags: list[str], category_id: str,
                 privacy: str, publish_at: datetime | None, synthetic_media: bool,
                 client_id: str, client_secret: str, refresh_token: str) -> str:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    if not (client_id and client_secret and refresh_token):
        raise SystemExit("Uploading needs YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN (see docs/SETUP.md)")

    creds = Credentials(None, refresh_token=refresh_token, token_uri="https://oauth2.googleapis.com/token",
                        client_id=client_id, client_secret=client_secret, scopes=SCOPES)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": False,
        "containsSyntheticMedia": synthetic_media,
    }
    if publish_at:
        status["privacyStatus"] = "private"  # YouTube requires private for scheduled publishing
        status["publishAt"] = publish_at.isoformat().replace("+00:00", "Z")

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": tags[:15],
            "categoryId": category_id,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": status,
    }
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            log.info("Upload %d%%", int(progress.progress() * 100))
    video_id = response["id"]
    log.info("Uploaded https://youtube.com/shorts/%s (%s)", video_id, status["privacyStatus"])
    return video_id
