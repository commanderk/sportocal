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
                    Suedwest -> Stuttgarter Kickers only).
  - "cup":          all matches are fetched, but only kept if at least one
                    side is a club we track (DFB-Pokal draws in amateur clubs
                    from outside our league scope in early rounds).

A league can also declare a `primarySource` in config.json (currently ffb2
and Regionalliga Suedwest, both DFB Datencenter -- neither is maintained by
OpenLigaDB right now) that skips OpenLigaDB entirely instead of only falling
back to a secondary source on a miss -- see fetch_dfb_datencenter_entry()
below. DFB Datencenter has no per-match venue on the pages we scrape, so a
best-effort location comes from the static config/stadiums.json lookup
instead (see common.load_stadiums()) -- deliberately not a fallback inside
the generic OpenLigaDB build_event() path, just for events from this source.

Since a primarySource league never touches OpenLigaDB at all, /getavailable-
leagues itself is fetched lazily (see get_leagues() in main()) -- only the
first non-primarySource league in the loop actually triggers it, and if it
fails, only *those* leagues are skipped; ffb2/Regionalliga Suedwest keep
working even when OpenLigaDB is down entirely.
"""
from __future__ import annotations

import html
import re
from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from common import (
    build_club_indexes,
    contains_keyword,
    diff_and_log,
    load_clubs,
    load_config,
    load_snapshot,
    load_stadiums,
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

DFB_DATENCENTER_WEEKDAYS = "Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag"


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


def match_has_a_real_date(match_date_time_utc: str | None) -> bool:
    """OpenLigaDB's placeholder for "no date known at all yet" is the Unix
    epoch ("1970-01-01T00:00:00") rather than an absent/null field -- seen
    live on an ffb1 match still missing both team's schedule. A plain
    None-check on matchDateTimeUTC alone would let that sentinel through as
    a real (garbage) calendar date, so this parses it and rejects anything
    at or before the epoch. Also rejects an unparseable value defensively,
    same "treat as missing" outcome rather than raising."""
    if not match_date_time_utc:
        return False
    try:
        parsed = datetime.fromisoformat(match_date_time_utc.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.year > 1970


def build_event(league_cfg: dict, match: dict, name_to_id: dict) -> dict | None:
    home, away = match["team1"], match["team2"]  # team1/team2 are always actual home/away
    home_name = home["teamName"].strip()
    away_name = away["teamName"].strip()

    match_datetime_utc = match.get("matchDateTimeUTC")
    if not match_has_a_real_date(match_datetime_utc):
        warn(
            f"[{league_cfg['id']}] Kein gueltiges Datum fuer '{home_name} - {away_name}' "
            f"(matchID {match.get('matchID')}) -- Spiel wird uebersprungen."
        )
        return None

    group_name = match.get("group", {}).get("groupName") or ""
    round_label = round_label_from_group(group_name, league_cfg.get("roundFormat", "spieltag"))

    match_datetime_local = match.get("matchDateTime")
    if match_datetime_local:
        dt_local = datetime.fromisoformat(match_datetime_local)
        # OpenLigaDB uses 00:00 as a placeholder when kickoff time isn't confirmed yet.
        time_confirmed = not (dt_local.hour == 0 and dt_local.minute == 0)
    else:
        # matchDateTime itself missing (matchDateTimeUTC is real, see above)
        # -- no local kickoff time to check, so treat it the same as an
        # unconfirmed placeholder rather than assuming it's confirmed.
        time_confirmed = False

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
        "start": match_datetime_utc,
        "timeConfirmed": time_confirmed,
        "location": location,
        "homeTeamId": resolve_club_id(name_to_id, home_name),
        "homeTeamName": home_name,
        "homeTeamLogo": home.get("teamIconUrl"),
        "awayTeamId": resolve_club_id(name_to_id, away_name),
        "awayTeamName": away_name,
        "awayTeamLogo": away.get("teamIconUrl"),
    }


def parse_dfb_datencenter_date(date_text: str) -> tuple[str, bool]:
    """DFB Datencenter shows a fixture's date either fully scheduled
    ("Sonntag, 02.08.2026 14:00 Uhr") or, before kickoff is set, only a
    provisional date window ("02.10. ~ 04.10.2026", no weekday/time) --
    analogous to OpenLigaDB's 00:00-placeholder handling in build_event(),
    just signalled by a distinct textual format here instead of a placeholder
    time. Only the window's start date is used, per the same "don't guess a
    precise time we don't have" rule. Raises ValueError if neither format
    matches, so the caller can skip just that one match instead of guessing.
    """
    text = html.unescape(date_text).strip()

    timed_match = re.search(
        rf"(?:{DFB_DATENCENTER_WEEKDAYS}),\s*(\d{{2}})\.(\d{{2}})\.(\d{{4}})\s+(\d{{2}})[.:](\d{{2}})\s*Uhr", text
    )
    if timed_match:
        day, month, year, hour, minute = (int(x) for x in timed_match.groups())
        local_dt = datetime(year, month, day, hour, minute, tzinfo=BERLIN)
        return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), True

    window_match = re.search(r"(\d{2})\.(\d{2})\.(?:(\d{4}))?\s*~\s*(\d{2})\.(\d{2})\.(\d{4})", text)
    if window_match:
        start_day, start_month, start_year, _end_day, _end_month, end_year = window_match.groups()
        year = int(start_year) if start_year else int(end_year)
        return f"{year:04d}-{int(start_month):02d}-{int(start_day):02d}", False

    raise ValueError(f"unbekanntes Datumsformat {text!r}")


def dfb_datencenter_name_overrides(clubs: list[dict]) -> dict[str, str]:
    """Supplemental team-name -> club-id entries for DFB Datencenter's own
    spelling of a club's name, which for several clubs diverges from both
    the OpenLigaDB name and the club's plain display name (dropped founding
    year/number, no "Frauen" suffix, shortened prefixes -- e.g. "Turbine
    Potsdam" vs. "1. FFC Turbine Potsdam" for ffb2, or "Hessen Kassel" vs.
    "KSV Hessen Kassel" for Regionalliga Suedwest). Checks every gender's
    team entry, not just one -- a club can have this override on
    teams.women (ffb2), teams.men (Regionalliga Suedwest), or in principle
    both. See config/clubs.json's teams.<gender>.dfbDatencenterTeamName.
    Kept local to this module instead of folded into common.py's generic
    build_club_indexes(), since the quirk is specific to this one source."""
    overrides = {}
    for club in clubs:
        for team in club.get("teams", {}).values():
            alt_name = team.get("dfbDatencenterTeamName") if team else None
            if alt_name:
                overrides[alt_name] = club["id"]
    return overrides


def gender_scoped_stadiums(
    stadiums: dict[str, str | dict[str, str]], clubs: list[dict], gender: str
) -> dict[str, str]:
    """resolve_club_id() is name-only and gender-blind, so a club id can end
    up matching two genuinely different teams -- e.g. "eintracht-frankfurt-ii"
    fields both an ffb2 *women's* side and, since the Regionalliga Suedwest
    full-league expansion, an unrelated *men's* reserve side, with different
    home grounds. Most config/stadiums.json entries are a plain "<Stadion>,
    <Stadt>" string (fine for a club tracked under one gender only); a club
    tracked under both with different venues instead uses a small
    {"men": "...", "women": "..."} dict there, resolved to this specific
    `gender` here. Also drops any club that doesn't even have a `gender`
    team in config/clubs.json in the first place -- a venue researched for
    one gender must never leak into a fixture for the other, and it's
    better to fall back to no location (None) than a confidently wrong one.
    """
    club_ids_with_gender = {club["id"] for club in clubs if gender in club.get("teams", {})}
    resolved = {}
    for club_id, value in stadiums.items():
        if club_id not in club_ids_with_gender:
            continue
        venue = value.get(gender) if isinstance(value, dict) else value
        if venue:
            resolved[club_id] = venue
    return resolved


def parse_dfb_datencenter_page(
    html_text: str, league_cfg: dict, name_to_id: dict, stadiums: dict[str, str]
) -> list[dict]:
    """Parse a DFB Datencenter page listing matches (either a league's full
    season-overview page, e.g. ffb2's ".../competitions/2-frauen-bundesliga/
    seasons/<season>", or a single team's page within a season, e.g.
    Regionalliga Suedwest's ".../teams/stuttgarter-kickers" -- both share the
    exact same match-row markup, and the team page already returns only that
    team's matches, so no extra club-filter step is needed for the
    "club-filter" scope). Every match gets a stable numeric id and matchday
    number, both embedded in the per-match result-page URL.

    Server-rendered HTML: one <div class="c-MatchTable-row"> per match, whose
    home-side column carries `id="match_<id>"` plus a date/time paragraph,
    followed by the home team's link+logo, a result link whose URL path
    already contains "<round>-spieltag/...-<id>", then the away team's
    link+logo. Match rows are located by that id anchor rather than balancing
    <div> tags (the surrounding markup nests further <div>s a regex can't
    safely bracket), slicing from each anchor to the next one (or to the end
    of the document for the last match) -- the competition/team-comparison
    links repeated further down each row don't confuse this, since we always
    take the *first* occurrence of each field within a slice, which belongs
    to that row's own match. A single malformed row is skipped with a
    warning rather than aborting the whole page, matching how a single bad
    source must never break the rest of the run (see main()).

    No per-match venue is published on either page shape, so `location` comes
    from the static `stadiums` lookup (config/stadiums.json via
    common.load_stadiums()) keyed by the *home* team's club id -- None if
    that club has no confirmed entry there, same as before this source
    existed. Not a generic assumption for every source: OpenLigaDB's own
    build_event() path (which already gets a real per-match venue from the
    API) is untouched.

    Written generically -- the league/competition slug lives in config.json's
    primarySource.url, not hardcoded here, and nothing below assumes a
    specific team count or gender -- so both ffb2 and Regionalliga Suedwest
    share this one function.
    """
    events = []
    match_anchors = list(re.finditer(r'id="match_\d+"', html_text))

    for i, anchor in enumerate(match_anchors):
        start_pos = anchor.start()
        end_pos = match_anchors[i + 1].start() if i + 1 < len(match_anchors) else len(html_text)
        block = html_text[start_pos:end_pos]

        try:
            date_match = re.search(r'dfb-Paragraph--small">\s*(.*?)\s*</p>', block, re.DOTALL)
            round_id_match = re.search(r"/(\d+)-spieltag/[a-z0-9-]+-(\d+)\"", block)
            home_div = re.search(r'team--home"[^>]*>(.*?)</div>', block, re.DOTALL)
            away_div = re.search(r'team--away"[^>]*>(.*?)</div>', block, re.DOTALL)
            if not (date_match and round_id_match and home_div and away_div):
                raise ValueError("erwartete Felder nicht gefunden (Markup geaendert?)")

            home_name_match = re.search(r"<a[^>]*>([^<]*)</a>", home_div.group(1))
            away_name_match = re.search(r"<a[^>]*>([^<]*)</a>", away_div.group(1))
            if not (home_name_match and away_name_match):
                raise ValueError("Team-Namen nicht gefunden")

            home_name = html.unescape(home_name_match.group(1)).strip()
            away_name = html.unescape(away_name_match.group(1)).strip()
            home_logo_match = re.search(r'src="([^"]+)"', home_div.group(1))
            away_logo_match = re.search(r'src="([^"]+)"', away_div.group(1))

            start, time_confirmed = parse_dfb_datencenter_date(date_match.group(1))
            round_num, match_id = round_id_match.groups()
            home_team_id = resolve_club_id(name_to_id, home_name)

            events.append(
                {
                    "id": f"football-{league_cfg['id']}-{match_id}",
                    "sport": "football",
                    "competition": league_cfg["competition"],
                    "gender": league_cfg["gender"],
                    "round": f"Spieltag {round_num}",
                    "start": start,
                    "timeConfirmed": time_confirmed,
                    # Home team's own ground -- not published per match on
                    # this page, so this is a static best-effort lookup, None
                    # if the home club has no confirmed stadiums.json entry.
                    "location": stadiums.get(home_team_id) if home_team_id else None,
                    "homeTeamId": home_team_id,
                    "homeTeamName": home_name,
                    "homeTeamLogo": home_logo_match.group(1) if home_logo_match else None,
                    "awayTeamId": resolve_club_id(name_to_id, away_name),
                    "awayTeamName": away_name,
                    "awayTeamLogo": away_logo_match.group(1) if away_logo_match else None,
                }
            )
        except Exception as exc:
            warn(f"[{league_cfg['id']}] DFB-Datencenter: Spiel bei Zeichen {start_pos} uebersprungen ({exc}).")
            continue

    return events


def dfb_season_start_year(now: datetime) -> int:
    """DFB league seasons run roughly August-May and are labelled by their
    start year (e.g. "2026-2027"); before the close season truly ends we're
    still inside the previous season's slug, hence the July cutoff (a bit
    ahead of the actual August kickoff, so this flips well before the new
    season's fixtures actually appear on the site)."""
    return now.year if now.month >= 7 else now.year - 1


def fetch_dfb_datencenter_entry(
    league_cfg: dict,
    primary_source: dict,
    now: datetime,
    clubs: list[dict],
    name_to_id: dict,
    stadiums: dict[str, str],
) -> list[dict] | None:
    season_start = dfb_season_start_year(now)
    url = primary_source["url"].format(season=season_start, seasonEnd=season_start + 1)
    merged_name_to_id = {**name_to_id, **dfb_datencenter_name_overrides(clubs)}
    scoped_stadiums = gender_scoped_stadiums(stadiums, clubs, league_cfg["gender"])

    try:
        page = http_get_text(url)
        events = parse_dfb_datencenter_page(page, league_cfg, merged_name_to_id, scoped_stadiums)
    except Exception as exc:
        warn(f"[{league_cfg['id']}] DFB-Datencenter-Quelle ({url}) fehlgeschlagen: {exc}")
        return None

    if not events:
        warn(f"[{league_cfg['id']}] DFB-Datencenter-Quelle ({url}) lieferte keine Spiele.")
        return None

    log(f"[{league_cfg['id']}] DFB-Datencenter-Quelle verwendet ({url}), {len(events)} Spiele gefunden.")
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


def fetch_entry(
    config: dict,
    get_leagues: Callable[[], list[dict]],
    league_cfg: dict,
    now: datetime,
    clubs: list[dict],
    name_to_id: dict,
    stadiums: dict[str, str],
) -> list[dict] | None:
    primary_source = league_cfg.get("primarySource")
    if primary_source and primary_source.get("source") == "dfb-datencenter":
        # Full replacement, not a fallback-on-miss: OpenLigaDB is never even
        # queried for this league -- get_leagues() (and the network request
        # it may trigger) is never even called.
        return fetch_dfb_datencenter_entry(league_cfg, primary_source, now, clubs, name_to_id, stadiums)

    current_year = now.year
    leagues = get_leagues()  # lazy: only hits OpenLigaDB once a non-primarySource league needs it
    candidates = find_league_candidates(leagues, league_cfg, current_year)
    if not candidates:
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
            # build_event() returns None for a match with no usable date
            # (logged there) rather than raising -- one bad match must not
            # take the rest of the league down with it.
            events = [e for e in (build_event(league_cfg, m, name_to_id) for m in relevant) if e is not None]
            if events and max(e["start"] for e in events) < datetime.now(timezone.utc).isoformat():
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


def make_leagues_getter(config: dict) -> Callable[[], list[dict]]:
    """Zero-arg callable that fetches OpenLigaDB's /getavailableleagues on
    first use and memoizes the result -- success or failure -- for the rest
    of the run. Lazy, since a primarySource league's fetch_dfb_datencenter_entry()
    never calls it at all; memoized so a down endpoint is hit (with its own
    internal retries) at most once per run, not once per non-primarySource
    league that needs it."""
    cache: dict[str, list[dict] | Exception] = {}

    def get_leagues() -> list[dict]:
        if "result" not in cache:
            try:
                cache["result"] = http_get_json(f"{config['football']['apiBase']}/getavailableleagues")
            except RuntimeError as exc:
                cache["result"] = exc
        result = cache["result"]
        if isinstance(result, Exception):
            raise result
        return result

    return get_leagues


def main() -> None:
    config = load_config()
    clubs = load_clubs()
    _, name_to_id = build_club_indexes(clubs)
    stadiums = load_stadiums()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    get_leagues = make_leagues_getter(config)

    for league_cfg in config["football"]["leagues"]:
        source_id = f"football-{league_cfg['id']}"
        try:
            events = fetch_entry(config, get_leagues, league_cfg, now, clubs, name_to_id, stadiums)
        except RuntimeError as exc:
            # get_leagues() failed -- only reachable for a non-primarySource
            # league (see fetch_entry()), so this never affects ffb2 /
            # Regionalliga Suedwest.
            warn(f"[{league_cfg['id']}] getavailableleagues nicht erreichbar, ueberspringe: {exc}")
            continue
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
