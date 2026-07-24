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

import html
import re
from datetime import datetime, timezone
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from common import (
    contains_keyword,
    diff_and_log,
    load_config,
    load_snapshot,
    log,
    normalize_text,
    http_get_json,
    http_get_text,
    save_snapshot,
    warn,
)

BERLIN = ZoneInfo("Europe/Berlin")


MIN_RELEVANT_SEASON_AGE_YEARS = 1  # a league whose newest season is older than this is treated as "not maintained"


def is_our_club(entry: dict, team_name: str) -> bool:
    """Prefix match, not substring: cup competitions pull in many more clubs
    than a single league, and a plain substring check on e.g. 'Mainz' or
    'Kickers' would also match unrelated teams like 'TSV Schott Mainz' or
    'Wuerzburger Kickers'."""
    return team_name.lower().startswith(entry["clubNameMatch"].lower())


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


def build_title(entry: dict, home_name: str, away_name: str, club_is_home: bool, round_label: str | None) -> str:
    """Title always follows actual home - away order, with the emoji marking
    wherever our club is -- so at a glance in the calendar you can tell
    whether it's a home or away game just from where the emoji sits."""
    if club_is_home:
        home_label = f"{entry['emoji']} {entry['clubShortName']}"
        away_label = away_name
    else:
        home_label = home_name
        away_label = f"{entry['emoji']} {entry['clubShortName']}"
    return f"{home_label} - {away_label} – {entry['competition']} – {round_label or ''}".strip()


def build_event(entry: dict, match: dict) -> dict:
    home, away = match["team1"], match["team2"]  # team1/team2 are always actual home/away
    club_is_home = is_our_club(entry, home["teamName"])
    home_name = home["teamName"].strip()
    away_name = away["teamName"].strip()

    group_name = match.get("group", {}).get("groupName") or ""
    if entry.get("roundFormat", "spieltag") == "raw":
        # cup rounds ("1. Runde", "Achtelfinale", ...) are shown as-is
        round_label = group_name or None
    else:
        round_match = re.search(r"\d+", group_name)
        round_label = f"Spieltag {round_match.group()}" if round_match else group_name or None

    title = build_title(entry, home_name, away_name, club_is_home, round_label)

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
                "name": home["teamName"].strip(),
                "shortName": (home.get("shortName") or home["teamName"]).strip(),
                "logo": home.get("teamIconUrl"),
            },
            "away": {
                "name": away["teamName"].strip(),
                "shortName": (away.get("shortName") or away["teamName"]).strip(),
                "logo": away.get("teamIconUrl"),
            },
        },
        "homeAway": "home" if club_is_home else "away",
    }


def parse_kickers_fixture_page(html_text: str, entry: dict) -> list[dict]:
    """Parse the official club fixtures page (stuttgarter-kickers.de/team/spielplan).

    Server-rendered HTML (no JS execution needed): every match is one
    <article> block containing a competition label, a date/time string, a
    venue, and the two team names in home-then-away order (verified against
    known home games at the club's own stadium). There's no OpenLigaDB-style
    league API for Regionalliga Suedwest right now, so this is a best-effort
    fallback tied to this one page's current markup -- if the club relaunches
    their site this will need re-checking, hence the narrow try/except in the
    caller rather than letting a markup change break the whole run.
    """
    only_competition = entry["fallback"]["onlyCompetition"]
    events = []
    for block in re.findall(r"<article.*?</article>", html_text, re.DOTALL):
        comp_match = re.search(
            r'<span class="pb-1 text-base font-bold text-blueLight-500[^"]*">([^<]*)</span>', block
        )
        if not comp_match or html.unescape(comp_match.group(1)).strip() != only_competition:
            continue

        teams = re.findall(r'<span class="text-h[^"]*">([^<]*)</span>', block)
        if len(teams) != 2:
            continue
        home_name, away_name = (html.unescape(t).strip() for t in teams)

        date_match = re.search(r'640:text-base 640:font-bold">(.*?)</span>', block, re.DOTALL)
        location_match = re.search(r'<span class="w-8/12[^"]*">([^<]*)</span>', block)
        location = html.unescape(location_match.group(1)).strip() if location_match else None

        if not date_match:
            continue
        date_text = html.unescape(re.sub(r"<!--.*?-->", "", date_match.group(1)))
        day_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", date_text)
        if not day_match:
            continue
        day, month, year = (int(x) for x in day_match.groups())

        time_match = re.search(r"Anstoß um (\d{2})[.:](\d{2}) Uhr", date_text)
        if time_match:
            hour, minute = (int(x) for x in time_match.groups())
            local_dt = datetime(year, month, day, hour, minute, tzinfo=BERLIN)
            start = local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            time_confirmed = True
        else:
            start = f"{year:04d}-{month:02d}-{day:02d}"
            time_confirmed = False

        club_is_home = is_our_club(entry, home_name)
        opponent_name = away_name if club_is_home else home_name

        # Each logo appears many times (once per responsive srcSet width), so
        # dedupe by file identity before picking "first team, second team".
        raw_logo_refs = re.findall(r"images\.prismic\.io%2F[^&\"]*?\.(?:png|jpg|jpeg|svg)", block)
        logo_urls = list(dict.fromkeys(unquote(u) for u in raw_logo_refs))
        home_logo = f"https://{logo_urls[0]}" if len(logo_urls) > 0 else None
        away_logo = f"https://{logo_urls[1]}" if len(logo_urls) > 1 else None

        title = build_title(entry, home_name, away_name, club_is_home, "{ROUND}")

        events.append(
            {
                "id": f"football-{entry['id']}-{start[:10]}-{re.sub(r'[^a-z0-9]+', '', opponent_name.lower())}",
                "sport": "football",
                "competition": entry["competition"],
                "round": None,  # this source doesn't expose a matchday number; filled in below
                "title": title,
                "start": start,
                "timeConfirmed": time_confirmed,
                "location": location,
                "participants": {
                    "home": {"name": home_name, "shortName": home_name, "logo": home_logo},
                    "away": {"name": away_name, "shortName": away_name, "logo": away_logo},
                },
                "homeAway": "home" if club_is_home else "away",
            }
        )

    # No matchday number is published on this page, so we approximate one by
    # chronological order -- clearly a best-effort label, not an official one.
    events.sort(key=lambda e: e["start"])
    for i, event in enumerate(events, start=1):
        event["round"] = f"Spieltag {i}"
        event["title"] = event["title"].replace("{ROUND}", event["round"])

    return events


def fetch_entry(config: dict, leagues: list[dict], entry: dict, current_year: int) -> list[dict] | None:
    candidates = find_league_candidates(leagues, entry, current_year)
    if not candidates:
        fallback = entry.get("fallback")
        if fallback and fallback["source"] == "kickers-site":
            warn(
                f"Keine aktuelle Liga bei OpenLigaDB gefunden, die zu '{entry['competition']}' passt. "
                f"Nutze Fallback-Quelle fuer {entry['id']}: {fallback['url']}"
            )
            try:
                page = http_get_text(fallback["url"])
                events = parse_kickers_fixture_page(page, entry)
            except Exception as exc:
                warn(f"[{entry['id']}] Fallback-Quelle fehlgeschlagen: {exc}")
                return None
            if not events:
                warn(f"[{entry['id']}] Fallback-Quelle lieferte keine '{fallback['onlyCompetition']}'-Spiele.")
                return None
            log(f"[{entry['id']}] Fallback-Quelle verwendet, {len(events)} Spiele gefunden.")
            return events

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
            if is_our_club(entry, m["team1"]["teamName"]) or is_our_club(entry, m["team2"]["teamName"])
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
