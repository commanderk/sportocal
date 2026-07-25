#!/usr/bin/env python3
"""Build the combined docs/kalender.ics from all data/*.json snapshots.

Always rebuilt from scratch on every run (cheap, and much simpler than
tracking per-source dirtiness) -- the actual git workflow only commits the
result if it actually changed.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from common import DATA_DIR, DOCS_DIR, format_event_title, load_clubs, log

BERLIN = ZoneInfo("Europe/Berlin")
ICS_PATH = DOCS_DIR / "kalender.ics"


def fold_line(line: str) -> str:
    """RFC 5545 line folding at 75 octets, continuation lines start with a space."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts = []
    while len(encoded) > 75:
        cut = 75
        # avoid splitting a multi-byte UTF-8 sequence
        while (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(encoded[:cut].decode("utf-8"))
        encoded = encoded[cut:]
    parts.append(encoded.decode("utf-8"))
    return ("\r\n ").join(parts)


def escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def build_vevent(event: dict, clubs_by_id: dict) -> list[str]:
    start_raw = event["start"]
    time_confirmed = event.get("timeConfirmed", True)
    description_parts = [f"Wettbewerb: {event['competition']}"]
    if event.get("round"):
        description_parts.append(f"Runde: {event['round']}")
    if not time_confirmed:
        description_parts.append("Hinweis: Uhrzeit noch nicht final")

    lines = ["BEGIN:VEVENT", f"UID:{event['id']}@sportocal"]

    if len(start_raw) == 10 or not time_confirmed:
        # all-day event
        if len(start_raw) == 10:
            day = datetime.fromisoformat(start_raw).date()
        else:
            day = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(BERLIN).date()
        lines.append(f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}")
    else:
        dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        lines.append(f"DTSTART:{dt.strftime('%Y%m%dT%H%M%SZ')}")
        lines.append(f"DTEND:{(dt + timedelta(hours=2)).strftime('%Y%m%dT%H%M%SZ')}")

    lines.append(f"SUMMARY:{escape_text(format_event_title(event, clubs_by_id))}")
    lines.append(f"DESCRIPTION:{escape_text(chr(10).join(description_parts))}")
    if event.get("location"):
        lines.append(f"LOCATION:{escape_text(event['location'])}")
    lines.append(f"CATEGORIES:{event['sport'].upper()}")
    lines.append("END:VEVENT")
    return lines


def main() -> None:
    clubs_by_id = {club["id"]: club for club in load_clubs()}

    events = []
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            snapshot = json.load(f)
        events.extend(snapshot.get("events", []))

    events.sort(key=lambda e: e["start"])

    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//sportocal//kalender//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:sportocal",
        "X-WR-TIMEZONE:Europe/Berlin",
    ]
    for event in events:
        vevent_lines = build_vevent(event, clubs_by_id)
        vevent_lines.insert(1, f"DTSTAMP:{now_stamp}")
        lines.extend(vevent_lines)
    lines.append("END:VCALENDAR")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with ICS_PATH.open("w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(fold_line(l) for l in lines))
        f.write("\r\n")

    log(f"kalender.ics geschrieben mit {len(events)} Terminen -> {ICS_PATH}")


if __name__ == "__main__":
    main()
