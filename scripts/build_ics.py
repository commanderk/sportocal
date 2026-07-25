#!/usr/bin/env python3
"""Build the combined public/kalender.ics from all data/*.json snapshots.

Always rebuilt from scratch on every run (cheap, and much simpler than
tracking per-source dirtiness) -- the actual git workflow only commits the
result if it actually changed. This is the unfiltered "everything" feed for
the interim combined site; the personalized single-user feed lives in
api/calendar_ics.py and shares the same VEVENT/VCALENDAR rendering via
common.build_calendar_text().
"""
from __future__ import annotations

from common import PUBLIC_DIR, build_calendar_text, load_all_events, load_clubs, log

ICS_PATH = PUBLIC_DIR / "kalender.ics"


def main() -> None:
    clubs_by_id = {club["id"]: club for club in load_clubs()}
    events = sorted(load_all_events(), key=lambda e: e["start"])

    calendar_text = build_calendar_text(events, clubs_by_id, calendar_name="sportocal")

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    with ICS_PATH.open("w", encoding="utf-8", newline="") as f:
        f.write(calendar_text)

    log(f"kalender.ics geschrieben mit {len(events)} Terminen -> {ICS_PATH}")


if __name__ == "__main__":
    main()
