#!/usr/bin/env python3
"""Fetch football fixtures from OpenLigaDB for all clubs configured in config.json.

OpenLigaDB is community-maintained: league shortcuts are stable for the
1. Bundesliga (bl1) but change from season to season (or aren't maintained at
all) for smaller leagues like Regionalliga Suedwest or the women's leagues.
So instead of hardcoding shortcuts, we always ask /getavailableleagues first
and fuzzy-match the current league by name. If no match is found we log a
clear warning and move on -- a missing league must never abort the whole run.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from common import (
    contains_keyword,
    diff_and_log,
    load_config,
    load_snapshot,
    log,
    normalize_text,
    http_get_json,
    save_snapshot,
    warn,
)


MIN_RELEVANT_SEASON_AGE_YEARS = 1  # a league whose newest season is older than this is treated as "not maintained"


def find_league_candidates(leagues: list[dict], entry: dict, current_year: int) -> list[dict]:
    candidates = []
    for league in leagues:
        name_norm = normalize_text(league["leagueName"])
        sport_norm = normalize_text(league.get("sport", {}).get("sportName", ""))

        if not all(contains_keyword(name_norm, kw) for kw in entry["leagueNameKeywords"]):
            continue
        if any(contains_keyword(name_norm, kw) for kw in entry["leagueNameExcludeKeywords"]):
            continue
        if entry["sportNameKeywords"] and not all(
            contains_keyword(sport_norm, kw) for kw in entry["sportNameKeywords"]
        ):
            continue
        if any(contains_keyword(sport_norm, kw) for kw in entry["sportNameExcludeKeywords"]):
            continue

        candidates.append(league)

    # newest season first
    candidates.sort(key=lambda l: int(l["leagueSeason"]), reverse=True)

    # Drop stale leagues entirely: OpenLigaDB keeps every historical season
    # around, so a name match alone isn't enough -- a league nobody has
    # updated in years must be treated the same as "no league found".
    min_season = current_year - MIN_RELEVANT_SEASON_AGE_YEARS
    return [l for l in candidates if int(l["leagueSeason"]) >= min_season]


def build_event(entry: dict, match: dict) -> dict:
    home, away = match["team1"], match["team2"]  # team1/team2 are always actual home/away
    club_is_home = entry["clubNameMatch"].lower() in home["teamName"].lower()
    opponent_name = away["teamName"] if club_is_home else home["teamName"]

    group_name = match.get("group", {}).get("groupName") or ""
    round_match = re.search(r"\d+", group_name)
    round_label = f"Spieltag {round_match.group()}" if round_match else group_name or None

    title = f"{entry['emoji']} {entry['clubShortName']} - {opponent_name} – {entry['competition']} – {round_label or ''}".strip()

    dt_local = datetime.fromisoformat(match["matchDateTime"])
    # OpenLigaDB uses 00:00 as a placeholder when kickoff time isn't confirmed yet.
    time_confirmed = not (dt_local.hour == 0 and dt_local.minute == 0)

    location = None
    loc = match.get("location")
    if loc:
        parts = [p for p in (loc.get("locationStadium"), loc.get("locationCity")) if p]
        location = ", ".join(parts) or None

    return {
        "id": f"football-{entry['id']}-{match['matchID']}",
        "sport": "football",
        "competition": entry["competition"],
        "round": round_label,
        "title": title,
        "start": match["matchDateTimeUTC"],
        "timeConfirmed": time_confirmed,
        "location": location,
        "participants": {
            "home": {
                "name": home["teamName"],
                "shortName": home.get("shortName") or home["teamName"],
                "logo": home.get("teamIconUrl"),
            },
            "away": {
                "name": away["teamName"],
                "shortName": away.get("shortName") or away["teamName"],
                "logo": away.get("teamIconUrl"),
            },
        },
        "homeAway": "home" if club_is_home else "away",
    }


def fetch_entry(config: dict, leagues: list[dict], entry: dict, current_year: int) -> list[dict] | None:
    candidates = find_league_candidates(leagues, entry, current_year)
    if not candidates:
        warn(
            f"Keine aktuelle Liga gefunden, die zu '{entry['competition']}' passt "
            f"(Keywords: {entry['leagueNameKeywords']}). Ueberspringe {entry['id']}."
        )
        return None

    api_base = config["football"]["apiBase"]
    for league in candidates[:3]:
        shortcut, season = league["leagueShortcut"], league["leagueSeason"]
        try:
            matches = http_get_json(f"{api_base}/getmatchdata/{shortcut}/{season}")
        except RuntimeError as exc:
            warn(f"[{entry['id']}] Abruf von {shortcut}/{season} fehlgeschlagen: {exc}")
            continue

        club_matches = [
            m
            for m in matches
            if entry["clubNameMatch"].lower() in m["team1"]["teamName"].lower()
            or entry["clubNameMatch"].lower() in m["team2"]["teamName"].lower()
        ]
        if club_matches:
            log(
                f"[{entry['id']}] Liga '{league['leagueName']}' (Shortcut {shortcut}, "
                f"Saison {season}) verwendet, {len(club_matches)} Spiele gefunden."
            )
            events = [build_event(entry, m) for m in club_matches]
            if max(e["start"] for e in events) < datetime.now(timezone.utc).isoformat():
                warn(
                    f"[{entry['id']}] Alle Spiele dieser Saison liegen bereits in der Vergangenheit "
                    f"-- naechste Saison ist bei OpenLigaDB fuer diese Liga offenbar noch nicht befuellt."
                )
            return events

        warn(
            f"[{entry['id']}] Liga '{league['leagueName']}' (Shortcut {shortcut}, Saison {season}) "
            f"gefunden, aber keine Spiele fuer '{entry['clubNameMatch']}'. Versuche naechste Saison."
        )

    warn(f"[{entry['id']}] In keiner der letzten Saisons Spiele gefunden.")
    return None


def main() -> None:
    config = load_config()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    try:
        leagues = http_get_json(f"{config['football']['apiBase']}/getavailableleagues")
    except RuntimeError as exc:
        warn(f"getavailableleagues nicht erreichbar, ueberspringe Fussball komplett: {exc}")
        return

    for entry in config["football"]["entries"]:
        source_id = f"football-{entry['id']}"
        try:
            events = fetch_entry(config, leagues, entry, now.year)
        except Exception as exc:  # a single bad source must not break the others
            warn(f"[{entry['id']}] Unerwarteter Fehler: {exc}")
            continue

        if events is None:
            continue

        old_snapshot = load_snapshot(source_id)
        changed = diff_and_log(source_id, old_snapshot["events"], events)
        if changed:
            log(f"[{source_id}] Aenderungen gefunden, Snapshot wird aktualisiert.")
        else:
            log(f"[{source_id}] Keine Aenderungen.")
        save_snapshot(source_id, events, now_iso)


if __name__ == "__main__":
    main()
