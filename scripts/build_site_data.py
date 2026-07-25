#!/usr/bin/env python3
"""Combine all data/*.json snapshots into public/data/events.json for the website.

public/ is the Vercel static root, so the frontend can only fetch files that
live under public/ -- the top-level data/ directory itself is not served
(it's only readable server-side, by api/calendar.ics.py).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from common import PUBLIC_DIR, load_all_events, log

SITE_DATA_PATH = PUBLIC_DIR / "data" / "events.json"


def main() -> None:
    events = sorted(load_all_events(), key=lambda e: e["start"])

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
