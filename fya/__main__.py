"""CLI: python -m fya [--topic ID|IDEA] [--languages both|en|es] [--reuse-run N] [--demo] [--upload MODE]"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .config import Settings
from .pipeline import run
from .topics import load_topics


def main() -> None:
    p = argparse.ArgumentParser(prog="fya", description="Make (and optionally upload) one YouTube Short.")
    p.add_argument("--topic", help="A topic id from config/topics.json, or your own idea in plain words "
                                   "(default: automatic rotation)")
    p.add_argument("--demo", action="store_true", help="Use a built-in script; no Claude API key needed")
    p.add_argument("--upload", choices=["none", "private", "scheduled", "public"],
                   help="Override UPLOAD_MODE for this run")
    p.add_argument("--languages", choices=["both", "en", "es"],
                   help="Which versions to make (default: FYA_LANGUAGES, normally both)")
    p.add_argument("--reuse-run", metavar="N",
                   help="Re-render the script saved by run N (data/scripts/run-N.json) instead of writing a new one")
    p.add_argument("--reuse-script", metavar="PATH", help="Re-render a script.json file")
    p.add_argument("--list-topics", action="store_true")
    p.add_argument("--keep-work", action="store_true", help="Keep intermediate files")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()

    if args.list_topics:
        for t in load_topics(settings.topics_file):
            print(f"{t.id:24} weight={t.weight:<4} {t.name}")
        return

    languages = {"both": ["en", "es"], "en": ["en"], "es": ["es"]}.get(args.languages or "")
    reuse = None
    if args.reuse_script:
        reuse = Path(args.reuse_script)
    elif args.reuse_run:
        if not args.reuse_run.strip().isdigit():
            raise SystemExit(f"--reuse-run must be a run number like 7, got {args.reuse_run!r}")
        reuse = settings.scripts_dir / f"run-{args.reuse_run.strip()}.json"
    if reuse is not None and not reuse.exists():
        raise SystemExit(f"No saved script at {reuse}. Scripts are kept in data/scripts/ for runs made after "
                         "this feature was added, and in each run's artifact for 14 days.")

    record = run(settings, topic_request=args.topic, demo=args.demo, upload_mode=args.upload,
                 keep_work=args.keep_work, languages=languages, reuse_script=reuse)
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
