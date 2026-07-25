"""Vercel Python Function: personalized, on-demand ICS generation.

GET /api/calendar.ics?t=<selection>

`t` is a comma-separated list of tokens, each either:
  - "<clubId>:men"   -- e.g. "fc-bayern-muenchen:men"
  - "<clubId>:women" -- club ids come from config/clubs.json
  - "race:<raceId>"  -- e.g. "race:tour-de-france", race ids from config.json's cycling.races

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
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from common import (  # noqa: E402
    build_calendar_text,
    load_all_events,
    load_clubs,
    load_config,
)

GENDER_SUFFIXES = (":men", ":women")


def parse_selection(raw: str) -> tuple[set[tuple[str, str]], set[str]]:
    """Returns (set of (clubId, gender) pairs, set of race ids). Unparseable
    or unknown tokens are silently dropped -- a typo'd/renamed id should just
    mean "this one piece is missing", never a broken calendar."""
    club_tokens: set[tuple[str, str]] = set()
    race_ids: set[str] = set()
    for token in (t.strip() for t in raw.split(",")):
        if not token:
            continue
        if token.startswith("race:"):
            race_ids.add(token[len("race:") :])
            continue
        for suffix in GENDER_SUFFIXES:
            if token.endswith(suffix):
                club_tokens.add((token[: -len(suffix)], suffix[1:]))
                break
    return club_tokens, race_ids


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
    club_tokens, race_ids = parse_selection(raw_selection)
    clubs_by_id = {c["id"]: c for c in load_clubs()}
    config = load_config()
    race_names = {r["id"]: r["name"] for r in config["cycling"]["races"]}

    events = filter_events(load_all_events(), club_tokens, race_ids, race_names)
    selected_club_ids = {cid for cid, _ in club_tokens}
    calendar_name = f"sportocal – {selection_summary(club_tokens, race_ids, clubs_by_id, race_names)}"
    calendar_text = build_calendar_text(
        events, clubs_by_id, calendar_name=calendar_name, perspective_club_ids=selected_club_ids
    )
    return calendar_text.encode("utf-8")


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        raw_selection = (query.get("t") or [""])[0]

        if not raw_selection.strip():
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "Fehlender oder leerer Parameter 't' (Vereins-/Renn-Auswahl).".encode("utf-8")
            )
            return

        body = build_response_body(raw_selection)

        self.send_response(200)
        self.send_header("Content-Type", "text/calendar; charset=utf-8")
        self.send_header("Content-Disposition", 'inline; filename="sportocal.ics"')
        # Generated fresh on every request from this deployment's bundled
        # data -- no caching beyond that, so calendar-client auto-refreshes
        # always see whatever the last weekly redeploy picked up.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        return
