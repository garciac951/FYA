# FYA: faceless YouTube Shorts pipeline

Makes one vertical Short per day, in **English and Spanish**, and (optionally) uploads each version to YouTube.

```
topic rotation ─▶ Claude writes the script in English + a natural Spanish adaptation
      ─▶ Pixabay (or Pexels) stock footage: Claude checks preview frames and picks the clip that
         matches each sentence (shared by both versions)
      ─▶ for each language: voiceover ─▶ ffmpeg 1080x1920 + word-by-word captions
      ─▶ YouTube upload (none / private / scheduled / public) ─▶ data/history.json
```

- **Languages:** `FYA_LANGUAGES=en,es` by default. The Spanish version goes to a second channel when
  `YT_REFRESH_TOKEN_ES` is set, otherwise to the same channel.
- **Topics:** `config/topics.json`. Twelve topics to start (fly fishing, mechanics, Texas Bermuda lawns,
  Java, raising a boy, cooking, basketball, football, beer 21+, dogs, phone tips, computer and OS tips).
  Topics are rotated so each one gets tested. Raise a topic's `weight` when it does well, or set it to `0` to pause it.
- **Schedule:** `.github/workflows/daily-short.yml` runs once a day. It can also be started by hand from the Actions tab,
  for both languages or just one, and can redo one language from an earlier run's script (see docs/SETUP.md).
- **Scripts:** every run's script is saved in `data/scripts/run-N.json` (N = the run number).
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
- Tech tips name the platform (iPhone, Android, Windows, Mac) and avoid menu paths the writer isn't sure of.
- Spanish is adapted, not translated word for word: conversational Mexican and US Hispanic Spanish, addressing the viewer as "tú".

These rules exist because YouTube demonetizes "inauthentic" mass-produced content. Each video has to offer something real.
