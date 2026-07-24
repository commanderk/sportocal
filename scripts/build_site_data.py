#!/usr/bin/env python3
"""Combine all data/*.json snapshots into docs/data/events.json for the website.

docs/ is the GitHub Pages publish root, so the frontend can only fetch files
that live under docs/ -- the top-level data/ directory itself is not served.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from common import DATA_DIR, DOCS_DIR, log

SITE_DATA_PATH = DOCS_DIR / "data" / "events.json"


def main() -> None:
    events = []
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            snapshot = json.load(f)
        events.extend(snapshot.get("events", []))

    events.sort(key=lambda e: e["start"])

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "events": events,
    }

    SITE_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SITE_DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    log(f"Website-Daten geschrieben mit {len(events)} Terminen -> {SITE_DATA_PATH}")


if __name__ == "__main__":
    main()
