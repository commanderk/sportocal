"""Vercel Python Function: personalized, on-demand ICS generation.

GET /api/calendar.ics?t=<selection>

`t` is a comma-separated list of tokens, each either:
  - "<clubId>:men"        -- e.g. "fc-bayern-muenchen:men"
  - "<clubId>:women"      -- club ids come from config/clubs.json
  - "raceGroup:<key>"     -- e.g. "raceGroup:uci-worldtour-men", where <key>
                             is "{tier}-{gender}" (see common.race_group_key()
                             and build_site_data.py's races.json export).

Cycling selection is at the tier×gender group level, not per-race (see
README/commit history): resolving "raceGroup:<key>" against config.json's
cycling.races happens fresh on every request, not once at subscribe time --
so a race added to a group later shows up in already-subscribed calendars
without the user having to resubscribe. This replaced an earlier
per-race "race:<raceId>" token; that token is not accepted anymore (no
public subscribers existed yet at the time of the switch, so no
compatibility shim was needed -- see git history if that ever changes).

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
also used by the interim combined feed (scripts/build_ics.py).
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from common import (  # noqa: E402
    build_calendar_text,
    load_all_events,
    load_clubs,
    load_config,
    race_group_key,
)

GENDER_SUFFIXES = (":men", ":women")
RACE_GROUP_PREFIX = "raceGroup:"


def parse_selection(raw: str) -> tuple[set[tuple[str, str]], set[str]]:
    """Returns (set of (clubId, gender) pairs, set of race-group keys).
    Unparseable or unknown tokens are silently dropped -- a typo'd/renamed id
    should just mean "this one piece is missing", never a broken calendar."""
    club_tokens: set[tuple[str, str]] = set()
    race_group_keys: set[str] = set()
    for token in (t.strip() for t in raw.split(",")):
        if not token:
            continue
        if token.startswith(RACE_GROUP_PREFIX):
            race_group_keys.add(token[len(RACE_GROUP_PREFIX) :])
            continue
        for suffix in GENDER_SUFFIXES:
            if token.endswith(suffix):
                club_tokens.add((token[: -len(suffix)], suffix[1:]))
                break
    return club_tokens, race_group_keys


def resolve_race_ids(race_group_keys: set[str], races: list[dict]) -> set[str]:
    """Race-group keys -> the *current* set of matching race ids in
    config.json, resolved fresh on every call (see module docstring)."""
    return {race["id"] for race in races if race_group_key(race["tier"], race["gender"]) in race_group_keys}


def selection_summary(club_tokens: set[tuple[str, str]], race_ids: set[str], clubs_by_id: dict, race_names: dict) -> str:
    names = [clubs_by_id[cid]["name"] for cid, _ in club_tokens if cid in clubs_by_id]
    names += [race_names[rid] for rid in race_ids if rid in race_names]
    return ", ".join(sorted(names)) or "(keine bekannten Vereine/Rennen in der Auswahl)"


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
    club_tokens, race_group_keys = parse_selection(raw_selection)
    clubs_by_id = {c["id"]: c for c in load_clubs()}
    config = load_config()
    races = config["cycling"]["races"]
    race_ids = resolve_race_ids(race_group_keys, races)
    race_names = {r["id"]: r["name"] for r in races}

    events = filter_events(load_all_events(), club_tokens, race_ids, race_names)
    selected_club_ids = {cid for cid, _ in club_tokens}
    calendar_name = f"sportocal – {selection_summary(club_tokens, race_ids, clubs_by_id, race_names)}"
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
