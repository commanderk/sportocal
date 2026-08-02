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
  - races.json   -- the cycling races, grouped for the selection UI (see
                     build_race_groups_payload())
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from common import PUBLIC_DIR, load_all_events, load_clubs, load_config, log

SITE_DATA_DIR = PUBLIC_DIR / "data"

# Grouping lives here (not in the frontend) so the picker's tier order/labels
# are computed once, server-side -- public/app.js just renders whatever
# groups races.json hands it, the same way it already treats football's
# leagues.json entries as ready-made groups.
TIER_ORDER = ["grand-tour", "uci-worldtour", "uci-proseries", "regional"]
TIER_LABELS = {
    "grand-tour": "Grand Tours",
    "uci-worldtour": "UCI WorldTour",
    "uci-proseries": "UCI ProSeries",
    "regional": "Regional",
}
GENDER_ORDER = ["men", "women"]
GENDER_SUFFIXES = {"men": "Männer", "women": "Frauen"}


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

    race_groups = build_race_groups_payload(config)
    write_json(SITE_DATA_DIR / "races.json", race_groups)
    race_count = sum(len(group["races"]) for group in race_groups)
    log(f"races.json geschrieben mit {race_count} Rennen in {len(race_groups)} Gruppen -> {SITE_DATA_DIR / 'races.json'}")


def build_race_groups_payload(config: dict) -> list[dict]:
    """Groups cycling races by tier, splitting a tier into separate
    Männer/Frauen groups (each with its own select-all in the UI) only once
    that tier actually has races of both genders -- same principle as
    football's "1. Bundesliga" vs. "Frauen-Bundesliga" being separate,
    equally-ranked groups instead of one mixed group. A tier with only one
    gender stays a single, unsuffixed group (e.g. "UCI ProSeries")."""
    races = config["cycling"]["races"]

    genders_by_tier: dict[str, set[str]] = {}
    races_by_tier_gender: dict[tuple[str, str], list[dict]] = {}
    for race in races:
        tier, gender = race["tier"], race["gender"]
        genders_by_tier.setdefault(tier, set()).add(gender)
        entry = {"id": race["id"], "name": race["name"], "shortName": race["shortName"]}
        if race.get("country"):
            entry["country"] = race["country"]
        races_by_tier_gender.setdefault((tier, gender), []).append(entry)

    groups = []
    for tier in TIER_ORDER:
        needs_suffix = len(genders_by_tier.get(tier, ())) > 1
        for gender in GENDER_ORDER:
            group_races = races_by_tier_gender.get((tier, gender))
            if not group_races:
                continue
            label = TIER_LABELS[tier]
            if needs_suffix:
                label = f"{label} {GENDER_SUFFIXES[gender]}"
            groups.append({"tier": tier, "gender": gender, "label": label, "races": group_races})
    return groups


if __name__ == "__main__":
    main()
