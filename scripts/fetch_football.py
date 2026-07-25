#!/usr/bin/env python3
"""Fetch football fixtures from OpenLigaDB for every league configured in config.json.

OpenLigaDB is community-maintained: league shortcuts are stable for the
1. Bundesliga (bl1) but change from season to season (or aren't maintained at
all) for smaller leagues like Regionalliga Suedwest or the women's leagues.
So instead of hardcoding shortcuts, we always ask /getavailableleagues first
and fuzzy-match the current league by name. If no match is found we log a
clear warning and move on -- a missing league must never abort the whole run.

Three fetch scopes, matched to how each league is used in the personal
calendar:
  - "full":        every club in the league is in scope (bl1/bl2/bl3/ffb1/ffb2).
  - "club-filter":  only one specific club's matches are kept (Regionalliga
                    Suedwest -> Stuttgarter Kickers only), with a dedicated
                    non-OpenLigaDB fallback scraper since this league isn't
                    OpenLigaDB-maintained at all right now.
  - "cup":          all matches are fetched, but only kept if at least one
                    side is a club we track (DFB-Pokal draws in amateur clubs
                    from outside our league scope in early rounds).
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from common import (
    build_club_indexes,
    contains_keyword,
    diff_and_log,
    load_clubs,
    load_config,
    load_snapshot,
    log,
    normalize_text,
    http_get_json,
    http_get_text,
    resolve_club_id,
    save_snapshot,
    warn,
)

BERLIN = ZoneInfo("Europe/Berlin")

MIN_RELEVANT_SEASON_AGE_YEARS = 1  # a league whose newest season is older than this is treated as "not maintained"


def find_league_candidates(leagues: list[dict], league_cfg: dict, current_year: int) -> list[dict]:
    candidates = []
    for league in leagues:
        name_norm = normalize_text(league["leagueName"])
        sport_norm = normalize_text(league.get("sport", {}).get("sportName", ""))

        if not all(contains_keyword(name_norm, kw) for kw in league_cfg["leagueNameKeywords"]):
            continue
        if any(contains_keyword(name_norm, kw) for kw in league_cfg["leagueNameExcludeKeywords"]):
            continue
        if league_cfg["sportNameKeywords"] and not all(
            contains_keyword(sport_norm, kw) for kw in league_cfg["sportNameKeywords"]
        ):
            continue
        if any(contains_keyword(sport_norm, kw) for kw in league_cfg["sportNameExcludeKeywords"]):
            continue

        candidates.append(league)

    candidates.sort(key=lambda l: int(l["leagueSeason"]), reverse=True)

    # Drop stale leagues entirely: OpenLigaDB keeps every historical season
    # around, so a name match alone isn't enough -- a league nobody has
    # updated in years must be treated the same as "no league found".
    min_season = current_year - MIN_RELEVANT_SEASON_AGE_YEARS
    return [l for l in candidates if int(l["leagueSeason"]) >= min_season]


def round_label_from_group(group_name: str, round_format: str) -> str | None:
    if round_format == "raw":
        # cup rounds ("1. Runde", "Achtelfinale", ...) are shown as-is
        return group_name or None
    match = re.search(r"\d+", group_name)
    return f"Spieltag {match.group()}" if match else (group_name or None)


def build_event(league_cfg: dict, match: dict, name_to_id: dict) -> dict:
    home, away = match["team1"], match["team2"]  # team1/team2 are always actual home/away
    home_name = home["teamName"].strip()
    away_name = away["teamName"].strip()

    group_name = match.get("group", {}).get("groupName") or ""
    round_label = round_label_from_group(group_name, league_cfg.get("roundFormat", "spieltag"))

    dt_local = datetime.fromisoformat(match["matchDateTime"])
    # OpenLigaDB uses 00:00 as a placeholder when kickoff time isn't confirmed yet.
    time_confirmed = not (dt_local.hour == 0 and dt_local.minute == 0)

    location = None
    loc = match.get("location")
    if loc:
        parts = [p for p in (loc.get("locationStadium"), loc.get("locationCity")) if p]
        location = ", ".join(parts) or None

    return {
        "id": f"football-{league_cfg['id']}-{match['matchID']}",
        "sport": "football",
        "competition": league_cfg["competition"],
        "gender": league_cfg["gender"],
        "round": round_label,
        "start": match["matchDateTimeUTC"],
        "timeConfirmed": time_confirmed,
        "location": location,
        "homeTeamId": resolve_club_id(name_to_id, home_name),
        "homeTeamName": home_name,
        "homeTeamLogo": home.get("teamIconUrl"),
        "awayTeamId": resolve_club_id(name_to_id, away_name),
        "awayTeamName": away_name,
        "awayTeamLogo": away.get("teamIconUrl"),
    }


def parse_kickers_fixture_page(html_text: str, league_cfg: dict, name_to_id: dict) -> list[dict]:
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
    only_competition = league_cfg["fallback"]["onlyCompetition"]
    club_name_match = league_cfg["clubNameMatch"]
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

        opponent_name = away_name if home_name.lower().startswith(club_name_match.lower()) else home_name

        # Each logo appears many times (once per responsive srcSet width), so
        # dedupe by file identity before picking "first team, second team".
        raw_logo_refs = re.findall(r"images\.prismic\.io%2F[^&\"]*?\.(?:png|jpg|jpeg|svg)", block)
        logo_urls = list(dict.fromkeys(unquote(u) for u in raw_logo_refs))
        home_logo = f"https://{logo_urls[0]}" if len(logo_urls) > 0 else None
        away_logo = f"https://{logo_urls[1]}" if len(logo_urls) > 1 else None

        events.append(
            {
                "id": f"football-{league_cfg['id']}-{start[:10]}-{re.sub(r'[^a-z0-9]+', '', opponent_name.lower())}",
                "sport": "football",
                "competition": league_cfg["competition"],
                "gender": league_cfg["gender"],
                "round": None,  # this source doesn't expose a matchday number; filled in below
                "start": start,
                "timeConfirmed": time_confirmed,
                "location": location,
                "homeTeamId": resolve_club_id(name_to_id, home_name),
                "homeTeamName": home_name,
                "homeTeamLogo": home_logo,
                "awayTeamId": resolve_club_id(name_to_id, away_name),
                "awayTeamName": away_name,
                "awayTeamLogo": away_logo,
            }
        )

    # No matchday number is published on this page, so we approximate one by
    # chronological order -- clearly a best-effort label, not an official one.
    events.sort(key=lambda e: e["start"])
    for i, event in enumerate(events, start=1):
        event["round"] = f"Spieltag {i}"

    return events


def fetch_league_matches(config: dict, shortcut: str, season: str) -> list[dict]:
    api_base = config["football"]["apiBase"]
    return http_get_json(f"{api_base}/getmatchdata/{shortcut}/{season}")


def matches_for_club(matches: list[dict], club_name_match: str) -> list[dict]:
    def is_club(team_name: str) -> bool:
        # Prefix match, not substring: a plain substring check on e.g.
        # 'Kickers' would also match unrelated teams like 'Wuerzburger Kickers'.
        return team_name.lower().startswith(club_name_match.lower())

    return [m for m in matches if is_club(m["team1"]["teamName"]) or is_club(m["team2"]["teamName"])]


def fetch_entry(config: dict, leagues: list[dict], league_cfg: dict, current_year: int, name_to_id: dict) -> list[dict] | None:
    candidates = find_league_candidates(leagues, league_cfg, current_year)
    if not candidates:
        fallback = league_cfg.get("fallback")
        if fallback and fallback["source"] == "kickers-site":
            warn(
                f"Keine aktuelle Liga bei OpenLigaDB gefunden, die zu '{league_cfg['competition']}' passt. "
                f"Nutze Fallback-Quelle fuer {league_cfg['id']}: {fallback['url']}"
            )
            try:
                page = http_get_text(fallback["url"])
                events = parse_kickers_fixture_page(page, league_cfg, name_to_id)
            except Exception as exc:
                warn(f"[{league_cfg['id']}] Fallback-Quelle fehlgeschlagen: {exc}")
                return None
            if not events:
                warn(f"[{league_cfg['id']}] Fallback-Quelle lieferte keine '{fallback['onlyCompetition']}'-Spiele.")
                return None
            log(f"[{league_cfg['id']}] Fallback-Quelle verwendet, {len(events)} Spiele gefunden.")
            return events

        gap_note = f" ({league_cfg['knownGap']})" if league_cfg.get("knownGap") else ""
        warn(
            f"Keine aktuelle Liga gefunden, die zu '{league_cfg['competition']}' "
            f"(gender={league_cfg['gender']}) passt (Keywords: {league_cfg['leagueNameKeywords']}). "
            f"Ueberspringe {league_cfg['id']}.{gap_note}"
        )
        return None

    scope = league_cfg["scope"]
    for league in candidates[:3]:
        shortcut, season = league["leagueShortcut"], league["leagueSeason"]
        try:
            matches = fetch_league_matches(config, shortcut, season)
        except RuntimeError as exc:
            warn(f"[{league_cfg['id']}] Abruf von {shortcut}/{season} fehlgeschlagen: {exc}")
            continue

        if scope == "club-filter":
            relevant = matches_for_club(matches, league_cfg["clubNameMatch"])
        elif scope == "cup":
            relevant = [
                m
                for m in matches
                if resolve_club_id(name_to_id, m["team1"]["teamName"]) or resolve_club_id(name_to_id, m["team2"]["teamName"])
            ]
        else:  # "full" -- every match in the league is in scope
            relevant = matches

        if relevant:
            log(
                f"[{league_cfg['id']}] Liga '{league['leagueName']}' (Shortcut {shortcut}, "
                f"Saison {season}) verwendet, {len(relevant)} Spiele gefunden."
            )
            events = [build_event(league_cfg, m, name_to_id) for m in relevant]
            if max(e["start"] for e in events) < datetime.now(timezone.utc).isoformat():
                warn(
                    f"[{league_cfg['id']}] Alle Spiele dieser Saison liegen bereits in der Vergangenheit "
                    f"-- naechste Saison ist bei OpenLigaDB fuer diese Liga offenbar noch nicht befuellt."
                )
            return events

        warn(
            f"[{league_cfg['id']}] Liga '{league['leagueName']}' (Shortcut {shortcut}, Saison {season}) "
            f"gefunden, aber keine relevanten Spiele. Versuche naechste Saison."
        )

    warn(f"[{league_cfg['id']}] In keiner der letzten Saisons Spiele gefunden.")
    return None


def main() -> None:
    config = load_config()
    clubs = load_clubs()
    _, name_to_id = build_club_indexes(clubs)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    try:
        leagues = http_get_json(f"{config['football']['apiBase']}/getavailableleagues")
    except RuntimeError as exc:
        warn(f"getavailableleagues nicht erreichbar, ueberspringe Fussball komplett: {exc}")
        return

    for league_cfg in config["football"]["leagues"]:
        source_id = f"football-{league_cfg['id']}"
        try:
            events = fetch_entry(config, leagues, league_cfg, now.year, name_to_id)
        except Exception as exc:  # a single bad source must not break the others
            warn(f"[{league_cfg['id']}] Unerwarteter Fehler: {exc}")
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
