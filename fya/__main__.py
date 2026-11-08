"""CLI: python -m fya [--topic ID] [--demo] [--upload none|private|scheduled|public]"""
from __future__ import annotations

import argparse
import json
import logging

from .config import Settings
from .pipeline import run
from .topics import load_topics


def main() -> None:
    p = argparse.ArgumentParser(prog="fya", description="Make (and optionally upload) one YouTube Short.")
    p.add_argument("--topic", help="Topic id from config/topics.json (default: automatic rotation)")
    p.add_argument("--demo", action="store_true", help="Use a built-in script; no Claude API key needed")
    p.add_argument("--upload", choices=["none", "private", "scheduled", "public"],
                   help="Override UPLOAD_MODE for this run")
    p.add_argument("--list-topics", action="store_true")
    p.add_argument("--keep-work", action="store_true", help="Keep intermediate files")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()

    if args.list_topics:
        for t in load_topics(settings.topics_file):
            print(f"{t.id:24} weight={t.weight:<4} {t.name}")
        return

    record = run(settings, topic_id=args.topic, demo=args.demo, upload_mode=args.upload, keep_work=args.keep_work)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
