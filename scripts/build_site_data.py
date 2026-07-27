#!/usr/bin/env python3
"""Combine all data/*.json snapshots + config into public/data/*.json for the website.

public/ is the Vercel static root, so the frontend can only fetch files that
live under public/ -- the top-level data/ and config/ directories themselves
are not served (they're only readable server-side, by api/calendar_ics.py).

Writes:
  - events.json  -- all events, for the read-only list/preview view
  - clubs.json   -- club id/name/shortName/colorHex, for the selection UI
                     (internal-only fields like openligadbTeamName are dropped)
  - leagues.json -- the club-selectable football leagues (cup sources are
                     excluded: DFB-Pokal isn't picked directly, it's pulled in
                     automatically for whichever clubs are selected)
  - races.json   -- the cycling races, for the selection UI
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from common import PUBLIC_DIR, load_all_events, load_clubs, load_config, log

SITE_DATA_DIR = PUBLIC_DIR / "data"


def write_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    events = sorted(load_all_events(), key=lambda e: e["start"])
    write_json(
        SITE_DATA_DIR / "events.json",
        {"generatedAt": datetime.now(timezone.utc).isoformat(), "events": events},
    )
    log(f"events.json geschrieben mit {len(events)} Terminen -> {SITE_DATA_DIR / 'events.json'}")

    clubs = [
        {
            "id": club["id"],
            "name": club["name"],
            "shortName": club["shortName"],
            "colorHex": club["colorHex"],
            "teams": {
                gender: {"league": team["league"]}
                for gender, team in club.get("teams", {}).items()
                if team
            },
        }
        for club in load_clubs()
    ]
    write_json(SITE_DATA_DIR / "clubs.json", clubs)
    log(f"clubs.json geschrieben mit {len(clubs)} Vereinen -> {SITE_DATA_DIR / 'clubs.json'}")

    config = load_config()
    leagues = [
        {"id": league["id"], "competition": league["competition"], "gender": league["gender"]}
        for league in config["football"]["leagues"]
        if league["scope"] != "cup"
    ]
    write_json(SITE_DATA_DIR / "leagues.json", leagues)
    log(f"leagues.json geschrieben mit {len(leagues)} Liga-Gruppen -> {SITE_DATA_DIR / 'leagues.json'}")

    races = build_races_payload(config)
    write_json(SITE_DATA_DIR / "races.json", races)
    log(f"races.json geschrieben mit {len(races)} Rennen -> {SITE_DATA_DIR / 'races.json'}")


def build_races_payload(config: dict) -> list[dict]:
    races = []
    for race in config["cycling"]["races"]:
        entry = {"id": race["id"], "name": race["name"], "gender": race["gender"], "tier": race["tier"]}
        if race.get("country"):
            entry["country"] = race["country"]
        races.append(entry)
    return races


if __name__ == "__main__":
    main()
