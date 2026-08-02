"""Vercel Python Function: personalized, on-demand ICS generation.

GET /api/calendar.ics?t=<selection>

`t` is a comma-separated list of tokens, each either:
  - "<clubId>:men"        -- e.g. "fc-bayern-muenchen:men"
  - "<clubId>:women"      -- club ids come from config/clubs.json
  - "raceGroup:<key>"     -- e.g. "raceGroup:uci-worldtour-men", where <key>
                             is "{tier}-{gender}" (see common.race_group_key()
                             and build_site_data.py's races.json export).
  - "league:<leagueId>:<gender>" -- e.g. "league:bl1:men", a whole league's
                             worth of clubs ("Alle Vereine der Bundesliga
                             auswählen" in the picker), resolved fresh below.
                             <leagueId> comes from config.json's
                             football.leagues (same ids public/data/leagues.json
                             exposes as league.id).

Cycling selection is at the tier×gender group level, not per-race (see
README/commit history): resolving "raceGroup:<key>" against config.json's
cycling.races happens fresh on every request, not once at subscribe time --
so a race added to a group later shows up in already-subscribed calendars
without the user having to resubscribe. This replaced an earlier
per-race "race:<raceId>" token; that token is not accepted anymore (no
public subscribers existed yet at the time of the switch, so no
compatibility shim was needed -- see git history if that ever changes).

A "league:<leagueId>:<gender>" token is resolved against config/clubs.json
the same "fresh on every request" way -- whichever clubs currently have
`teams[gender].league` equal to that league's name are members, so
promotion/relegation to a new season is reflected automatically without
resubscribing. Membership only depends on the club, never on
event["competition"], so a member club's cup/UEFA fixtures are pulled in
too without any special-casing. League-group club ids are deliberately
*not* added to `perspective_club_ids` (see build_response_body()) -- only
individually selected clubs get the emoji/color treatment in the calendar
title, a league-only-covered club's matches render as plain team names
(see format_football_title() in scripts/common.py).

A whole-league selection's calendar-name label (league_group_label() below)
uses the same "Männer"/"Frauen" wording as app.js's own leagueGroupLabel(),
but a different rule: the picker UI always spells out the gender ("1.
Bundesliga Männer"), while the calendar name only appends "(Männer)"/
"(Frauen)" when the competition name doesn't already say it
("Frauen-Bundesliga" stays as-is; "DFB-Pokal", shared by both genders, gets
the suffix either way).

Stateless by design (see README): the selection lives entirely in the URL, no
server-side storage, no cookies. Reads data/*.json + config/clubs.json from
the deployment bundle (Python Functions on Vercel include all files reachable
at build time, no extra bundler config needed) and regenerates the ICS body
on every request -- no caching beyond what a redeploy naturally provides, so
a client's periodic calendar refresh always sees this deployment's data.

The whole season (past and future matches) is included; the only cut is the
implicit one from fetch_football.py always snapshotting the newest available
season, so an old season's fixtures simply aren't present anymore once a new
one starts. See scripts/common.py for the shared VEVENT/title-rendering logic
also used by the interim combined feed (scripts/build_ics.py) -- reminder
timing (absolute, DST-aware), LOCATION and the URL property all come from
there and need no per-feed handling here.

X-WR-CALNAME is built fresh per selection by build_calendar_name() below --
"Sportocal – {items}", each item as short as possible (a club's shortName, a
whole race/league group collapsed to one speaking name never its current
members) and capped so the name never turns into an unwieldy or stale-looking
member list; see that function's docstring for the exact truncation rule.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from common import (  # noqa: E402
    TIER_LABELS,
    build_calendar_text,
    load_all_events,
    load_clubs,
    load_config,
    parse_race_group_key,
    race_group_key,
)

GENDER_SUFFIXES = (":men", ":women")
RACE_GROUP_PREFIX = "raceGroup:"
LEAGUE_GROUP_PREFIX = "league:"
GENDER_LABELS = {"men": "Männer", "women": "Frauen"}
MAX_CALNAME_ITEMS = 2
MAX_CALNAME_TOTAL_ITEMS = 6
DEFAULT_CALENDAR_NAME = "Sportocal – Mein Kalender"


def parse_selection(raw: str) -> tuple[set[tuple[str, str]], set[str], set[str]]:
    """Returns (set of (clubId, gender) pairs, set of race-group keys, set of
    league-group keys). Unparseable or unknown tokens are silently dropped --
    a typo'd/renamed id should just mean "this one piece is missing", never a
    broken calendar."""
    club_tokens: set[tuple[str, str]] = set()
    race_group_keys: set[str] = set()
    league_group_keys: set[str] = set()
    for token in (t.strip() for t in raw.split(",")):
        if not token:
            continue
        if token.startswith(RACE_GROUP_PREFIX):
            race_group_keys.add(token[len(RACE_GROUP_PREFIX) :])
            continue
        if token.startswith(LEAGUE_GROUP_PREFIX):
            league_group_keys.add(token[len(LEAGUE_GROUP_PREFIX) :])
            continue
        for suffix in GENDER_SUFFIXES:
            if token.endswith(suffix):
                club_tokens.add((token[: -len(suffix)], suffix[1:]))
                break
    return club_tokens, race_group_keys, league_group_keys


def resolve_race_ids(race_group_keys: set[str], races: list[dict]) -> set[str]:
    """Race-group keys -> the *current* set of matching race ids in
    config.json, resolved fresh on every call (see module docstring)."""
    return {race["id"] for race in races if race_group_key(race["tier"], race["gender"]) in race_group_keys}


def resolve_league_club_tokens(
    league_group_keys: set[str], leagues: list[dict], clubs: list[dict]
) -> set[tuple[str, str]]:
    """League-group keys ("<leagueId>:<gender>") -> the *current* set of
    (clubId, gender) pairs for every club presently in that league, resolved
    fresh on every call against config.json/clubs.json (see module
    docstring) -- so promotion/relegation to a new season is reflected in an
    already-subscribed calendar without resubscribing."""
    leagues_by_key = {f"{league['id']}:{league['gender']}": league for league in leagues}
    matched_leagues = [leagues_by_key[key] for key in league_group_keys if key in leagues_by_key]
    tokens: set[tuple[str, str]] = set()
    for league in matched_leagues:
        gender = league["gender"]
        for club in clubs:
            team = club.get("teams", {}).get(gender)
            if team and team.get("league") == league["competition"]:
                tokens.add((club["id"], gender))
    return tokens


def league_group_label(league: dict) -> str:
    """League name for the calendar name, e.g. "Bundesliga (Männer)" -- the
    " (Männer)"/"(Frauen)" suffix is only appended when the competition name
    doesn't already say the gender itself ("Frauen-Bundesliga" stays as-is),
    since several competitions (e.g. "DFB-Pokal") share the same name across
    both genders and would otherwise be indistinguishable in the calendar
    name. Deliberately not app.js's leagueGroupLabel(), which always spells
    out the gender for the picker UI regardless of the name."""
    competition = league["competition"]
    if "Frauen" in competition:
        return competition
    return f"{competition} ({GENDER_LABELS.get(league['gender'], league['gender'])})"


def race_group_display_name(key: str) -> str | None:
    """"<tier>-<gender>" race-group key -> a short, speaking group name for
    the calendar name, e.g. "UCI WorldTour (Männer)" -- never a listing of
    the group's current individual races. A group is always resolved fresh
    against config.json (see module docstring), so naming it after whichever
    races happen to be in it right now would make the calendar's own name
    go stale the moment membership changes; the group name itself doesn't."""
    parsed = parse_race_group_key(key)
    if not parsed:
        return None
    tier, gender = parsed
    tier_label = TIER_LABELS.get(tier)
    if not tier_label:
        return None
    return f"{tier_label} ({GENDER_LABELS.get(gender, gender)})"


def build_calendar_name(
    club_tokens: set[tuple[str, str]],
    league_group_keys: set[str],
    race_group_keys: set[str],
    clubs_by_id: dict,
    leagues: list[dict],
) -> str:
    """X-WR-CALNAME for a personalized feed: "Sportocal – {items}", each item
    as short as it reasonably can be -- a club's shortName (not its full
    name), a whole race/league group collapsed to one speaking group name
    (never a listing of its current members, see race_group_display_name()/
    league_group_label()). A single shared item list and truncation rule
    covers every combination (clubs only, groups only, or mixed): more than
    MAX_CALNAME_ITEMS items truncates to the first few + ", u.a."; more than
    MAX_CALNAME_TOTAL_ITEMS, or nothing resolvable at all, falls back to a
    generic name rather than an unwieldy or empty one."""
    items = []
    for cid, _ in club_tokens:
        club = clubs_by_id.get(cid)
        if club and club.get("shortName"):
            items.append(club["shortName"])

    leagues_by_key = {f"{league['id']}:{league['gender']}": league for league in leagues}
    for key in league_group_keys:
        league = leagues_by_key.get(key)
        if league:
            items.append(league_group_label(league))

    for key in race_group_keys:
        name = race_group_display_name(key)
        if name:
            items.append(name)

    items = sorted(set(items))
    if not items or len(items) > MAX_CALNAME_TOTAL_ITEMS:
        return DEFAULT_CALENDAR_NAME
    if len(items) > MAX_CALNAME_ITEMS:
        return f"Sportocal – {', '.join(items[:MAX_CALNAME_ITEMS])}, u.a."
    return f"Sportocal – {', '.join(items)}"


def filter_events(events: list[dict], club_tokens: set[tuple[str, str]], race_ids: set[str], race_names: dict) -> list[dict]:
    selected_race_names = {race_names[r] for r in race_ids if r in race_names}
    filtered = []
    for event in events:
        if event["sport"] == "football":
            if any(
                (event.get("homeTeamId") == cid or event.get("awayTeamId") == cid) and event.get("gender") == gender
                for cid, gender in club_tokens
            ):
                filtered.append(event)
        elif event["sport"] == "cycling" and event["competition"] in selected_race_names:
            filtered.append(event)
    filtered.sort(key=lambda e: e["start"])
    return filtered


def build_response_body(raw_selection: str) -> bytes:
    club_tokens, race_group_keys, league_group_keys = parse_selection(raw_selection)
    clubs = load_clubs()
    clubs_by_id = {c["id"]: c for c in clubs}
    config = load_config()
    races = config["cycling"]["races"]
    leagues = config["football"]["leagues"]
    race_ids = resolve_race_ids(race_group_keys, races)
    race_names = {r["id"]: r["name"] for r in races}
    league_club_tokens = resolve_league_club_tokens(league_group_keys, leagues, clubs)

    # Visibility uses the union of explicitly selected clubs and whoever a
    # selected league currently contains; the calendar title's emoji/color
    # ("perspective") stays scoped to *only* the explicitly selected clubs --
    # see module docstring and format_football_title() in scripts/common.py.
    events = filter_events(load_all_events(), club_tokens | league_club_tokens, race_ids, race_names)
    selected_club_ids = {cid for cid, _ in club_tokens}
    calendar_name = build_calendar_name(club_tokens, league_group_keys, race_group_keys, clubs_by_id, leagues)
    calendar_text = build_calendar_text(
        events, clubs_by_id, calendar_name=calendar_name, perspective_club_ids=selected_club_ids
    )
    return calendar_text.encode("utf-8")


def app(environ, start_response):
    """Plain WSGI app (stdlib only, no framework) -- Vercel's Python runtime
    expects an ASGI/WSGI callable named `app` as the function entrypoint
    (see pyproject.toml's [tool.vercel] entrypoint)."""
    query = parse_qs(environ.get("QUERY_STRING", ""))
    raw_selection = (query.get("t") or [""])[0]

    if not raw_selection.strip():
        body = "Fehlender oder leerer Parameter 't' (Vereins-/Renn-Auswahl).".encode("utf-8")
        start_response("400 Bad Request", [("Content-Type", "text/plain; charset=utf-8")])
        return [body]

    body = build_response_body(raw_selection)
    headers = [
        ("Content-Type", "text/calendar; charset=utf-8"),
        ("Content-Disposition", 'inline; filename="sportocal.ics"'),
        # Generated fresh on every request from this deployment's bundled
        # data -- no caching beyond that, so calendar-client auto-refreshes
        # always see whatever the last weekly redeploy picked up.
        ("Cache-Control", "no-store"),
    ]
    start_response("200 OK", headers)
    return [body]
