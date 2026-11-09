# Setup guide

You do these steps once. After that a GitHub Action makes a Short every day.

## 1. Create the channel (about 10 minutes)

1. Use a **personal** Google account, not a work account.
2. Go to youtube.com → profile picture → **Create a channel**. Choose **"Use a custom name"**
   so it becomes a Brand Account. That lets you add managers later and keeps the channel separate from your personal profile.
3. Pick a name and handle (see [CHANNEL_NAMES.md](CHANNEL_NAMES.md)).
4. Verify the channel with your phone: youtube.com/verify. This unlocks videos longer than 15 minutes, custom thumbnails and some API limits.
5. Add a profile picture, a banner and a one-line description, for example: *"Practical know-how in under a minute: trucks, lawns, grilling, fishing, dogs, tech and more."*
6. **Create the Spanish channel the same way** (recommended), from the same Google account:
   youtube.com/account → **Add or manage your channels** → **Create a channel**. Name it for example
   *Plática de Porche*. Description: *"Consejos prácticos en menos de un minuto: trocas, jardín, asador, pesca, perros, tecnología y más."*

   Why a separate channel: YouTube shows Shorts to viewers based on the channel's audience and language.
   A channel that mixes English and Spanish confuses the algorithm, subscribers get half their feed in a
   language they don't watch, and posting the same video twice on one channel can look like the repetitive
   content YouTube refuses to monetize. If you still want one channel, skip this and the Spanish
   version is posted to the English channel.

## 2. Free API keys

| Secret | Where | Cost |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys | About 2-5 cents per script |
| `PEXELS_API_KEY` | pexels.com/api → sign up → key shown instantly | Free |
| `ELEVENLABS_API_KEY` (optional) | elevenlabs.io → Profile → API key | From about $5 a month. Sounds better than the free voice |

The default voice (`TTS_PROVIDER=edge`) is free and needs no key.

## 3. Let the uploader post to your channel

1. Go to console.cloud.google.com and create a project, for example "fya-uploader".
2. **APIs & Services → Library**: enable **YouTube Data API v3**.
3. **APIs & Services → OAuth consent screen**: choose External. Fill in the app name and your email.
   Add the scope `.../auth/youtube.upload`. Add yourself as a test user.
4. **Publish the app to "In production"** on the same screen. You don't need Google's verification for
   personal use: you'll just click through an "unverified app" warning once. If you skip this, Google
   **expires the refresh token after 7 days** and uploads stop.
5. **Credentials → Create credentials → OAuth client ID → Desktop app**. Download the JSON file.
6. On your computer:
   ```bash
   pip install google-auth-oauthlib
   python scripts/youtube_auth.py ~/Downloads/client_secret_XXXX.json
   ```
   Sign in, **pick the English channel** (not your personal one) and allow access. The script prints three values.
7. **Run it a second time and pick the Spanish channel.** Keep only the new `YT_REFRESH_TOKEN` it prints
   and save it as `YT_REFRESH_TOKEN_ES`. The client ID and secret are the same for both channels.

**Important limit:** until Google audits your API project, **every upload is locked to private**. That's fine
for the review phase. When you're ready to post automatically, request the audit with the
"YouTube API Services - Audit and Quota Extension" form, linked from the YouTube API docs. It's free.
Quota: each upload uses about 1,600 of the default 10,000 units a day. One Short a day in two languages
uses about 3,200, so there's room for up to 3 Shorts a day in both languages.

## 4. Add the secrets to GitHub

Repo → **Settings → Secrets and variables → Actions**.

**Secrets:** `ANTHROPIC_API_KEY`, `PEXELS_API_KEY`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`,
`YT_REFRESH_TOKEN_ES` (the Spanish channel; leave it out to post both versions to one channel), and
`ELEVENLABS_API_KEY` if used.

**Variables** (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `FYA_CHANNEL_NAME` | `Porch Talk` | English channel name, shown on the video and given to the scriptwriter |
| `FYA_CHANNEL_NAME_ES` | `Plática de Porche` | Spanish channel name |
| `FYA_LANGUAGES` | `en,es` | Which versions to make: `en,es`, `en` or `es` |
| `TTS_VOICE_ES` | `es-MX-JorgeNeural` (edge) | Spanish voice. ElevenLabs and OpenAI use the same voice for both languages |
| `PUBLISH_HOUR_UTC_ES` | `1` | When Spanish Shorts publish in `scheduled` mode. 01:00 UTC is about 7-8pm in Texas |
| `UPLOAD_MODE` | `none` | `none` = render only (download it from the Action run) · `private` = upload privately for you to review · `scheduled` = auto-publish at `PUBLISH_HOUR_UTC` · `public` = publish now |
| `PUBLISH_HOUR_UTC` | `23` | 23:00 UTC is about 5-6pm in Texas |
| `TTS_PROVIDER` | `edge` | `edge` (free), `elevenlabs`, `openai` |
| `TTS_VOICE` | provider default | For example `en-US-GuyNeural` for edge, or an ElevenLabs voice id |
| `YT_SYNTHETIC_MEDIA` | `false` | Set `true` if videos ever use realistic AI-generated footage. Stock clips with a TTS voice don't need the label |

## 5. Turn it on

1. Merge this branch into the default branch. Scheduled workflows only run from the default branch.
2. **Actions → Daily Short → Run workflow** to try it once. With `UPLOAD_MODE=none`, download the video from the run's **Artifacts**.
3. Recommended rollout:
   - Week 1: `none` or `private`. Watch every video and tell Claude what to change.
   - Weeks 2-3: `private`. Publish the good ones yourself in YouTube Studio.
   - After the API audit is approved: `scheduled`.

## Optional: background music

Put royalty-free tracks (`.mp3`) in `assets/music/`. The YouTube Audio Library is a safe source.
One is picked at random for each video and mixed quietly under the voice.

## Run locally

```bash
pip install -r requirements.txt     # also needs ffmpeg
cp .env.example .env                # fill in keys
python -m fya --demo                # built-in script, no Claude key needed
python -m fya --topic dogs          # real run, render only
python -m fya --upload private      # render + private upload
```
