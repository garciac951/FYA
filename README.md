# FYA: faceless YouTube Shorts pipeline

Makes one vertical Short per day and (optionally) uploads it to YouTube.

```
topic rotation ─▶ Claude writes script ─▶ voiceover (edge / ElevenLabs / OpenAI)
      ─▶ Pexels stock footage ─▶ ffmpeg: 1080x1920, word-by-word captions, music
      ─▶ YouTube upload (none / private / scheduled / public) ─▶ data/history.json
```

- **Topics:** `config/topics.json`. Ten topics to start (fly fishing, mechanics, Texas Bermuda lawns,
  Java, raising a boy, cooking, basketball, football, beer 21+, dogs). Topics are rotated so each one
  gets tested. Raise a topic's `weight` when it does well, or set it to `0` to pause it.
- **Schedule:** `.github/workflows/daily-short.yml` runs once a day. It can also be started by hand from the Actions tab.
- **History:** every video is logged in `data/history.json` so topics and ideas don't repeat.

Start here: **[docs/SETUP.md](docs/SETUP.md)** · Name ideas: **[docs/CHANNEL_NAMES.md](docs/CHANNEL_NAMES.md)**

## Quick test

```bash
pip install -r requirements.txt   # plus ffmpeg
python -m fya --demo              # renders a sample Short to output/ with no API keys
python -m fya --list-topics
```

## Content rules baked into the scriptwriter

- One specific, accurate idea per Short. The hook is the first sentence. No "like and subscribe."
- It avoids repeating earlier titles on the same topic.
- Beer content is written for adults 21+, educational only, with no binge drinking, drinking and driving, or brand endorsements.
- Dog health content is general and points owners to a vet.

These rules exist because YouTube demonetizes "inauthentic" mass-produced content. Each video has to offer something real.
