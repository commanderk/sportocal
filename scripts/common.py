"""Shared helpers for sportocal fetch/build scripts.

Generic event schema (sport-agnostic, see README):
    id, sport, competition, round, title, start, timeConfirmed,
    location, participants, lastUpdated  (+ optional sport-specific extras)
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")

USER_AGENT = "sportocal/1.0 (https://github.com/commanderk/sportocal; contact via GitHub issues)"

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PUBLIC_DIR = ROOT_DIR / "public"
CONFIG_PATH = ROOT_DIR / "config.json"
CLUBS_PATH = ROOT_DIR / "config" / "clubs.json"

# Short form (no "stage" suffix) shared by both scraped and manually-entered
# `route.type` values, so Grand Tours and the CSV-sourced races use the same
# vocabulary -- fetch_cycling.py's parser strips a trailing " stage" from
# whatever Wikipedia's wikitext cell says, and build_manual_cycling.py
# validates the manual CSV sheet against this same set. "Prologue" has no
# scraped equivalent yet (Wikipedia labels it via the stage number/heading,
# not this cell) but is included for the Deutschland Tour prologue case.
STAGE_TYPES = {
    "Flat",
    "Hilly",
    "Medium-mountain",
    "Mountain",
    "Individual time trial",
    "Team time trial",
    "Prologue",
}


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def race_group_key(tier: str, gender: str) -> str:
    """Stable, URL-safe key identifying a cycling race's tier+gender group --
    the same derivation build_site_data.py's races.json groups and app.js's
    picker both use client-side, so a group selected in the UI resolves back
    to exactly the right set of config.json races at ICS request time (see
    api/calendar_ics.py). No new config.json field: tier/gender already
    exist per race, this just names their combination."""
    return f"{tier}-{gender}"


def load_clubs() -> list[dict]:
    with CLUBS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def build_club_indexes(clubs: list[dict]) -> tuple[dict[str, dict], dict[str, str]]:
    """clubs_by_id for title rendering, plus a team-name -> club-id lookup used
    to resolve OpenLigaDB match participants against our club table. The name
    index carries both the exact OpenLigaDB team name (when known) and a
    normalized form of the club's own name, since cup-opponent name spelling
    doesn't always match the league-feed spelling exactly."""
    clubs_by_id = {club["id"]: club for club in clubs}
    name_to_id: dict[str, str] = {}
    for club in clubs:
        name_to_id[normalize_text(club["name"])] = club["id"]
        for gender in ("men", "women"):
            team = club.get("teams", {}).get(gender)
            api_name = team.get("openligadbTeamName") if team else None
            if api_name:
                name_to_id[api_name] = club["id"]
    return clubs_by_id, name_to_id


def resolve_club_id(name_to_id: dict[str, str], team_name: str) -> str | None:
    if team_name in name_to_id:
        return name_to_id[team_name]
    return name_to_id.get(normalize_text(team_name))


# Square = men, circle = women; same color order in both rows so the color
# alone still reads as "this club" regardless of which team is playing.
SQUARE_EMOJI = {
    "red": "🟥", "orange": "🟧", "yellow": "🟨", "green": "🟩", "blue": "🟦",
    "purple": "🟪", "black": "⬛", "white": "⬜", "brown": "🟫",
}
CIRCLE_EMOJI = {
    "red": "🔴", "orange": "🟠", "yellow": "🟡", "green": "🟢", "blue": "🔵",
    "purple": "🟣", "black": "⚫", "white": "⚪", "brown": "🟤",
}


def club_emoji(color_palette: str | None, gender: str | None) -> str:
    table = CIRCLE_EMOJI if gender == "women" else SQUARE_EMOJI
    return table.get(color_palette or "", "⬜" if gender != "women" else "⚪")


def club_label(club: dict, gender: str | None) -> str:
    return f"{club_emoji(club.get('colorPalette'), gender)} {club['shortName']}"


def format_football_title(
    event: dict, clubs_by_id: dict[str, dict], perspective_club_ids: set[str] | None = None
) -> str:
    """Renders the calendar title from raw fields -- never stored, so a future
    format change needs no data migration. Without `perspective_club_ids`
    (e.g. the combined multi-club feed) both sides get a color/emoji label
    when we know the club; with a set (a personalized calendar for specific
    clubs), only sides in that set get the emoji and the other side is a
    plain name -- so if two of the user's own selected clubs happen to play
    each other, both still get their emoji, not just one arbitrarily."""
    gender = event.get("gender")
    home_club = clubs_by_id.get(event.get("homeTeamId"))
    away_club = clubs_by_id.get(event.get("awayTeamId"))

    def label_for(club: dict | None, team_id: str | None, raw_name: str) -> str:
        if perspective_club_ids is not None:
            return club_label(club, gender) if club and team_id in perspective_club_ids else raw_name
        return club_label(club, gender) if club else raw_name

    home_label = label_for(home_club, event.get("homeTeamId"), event["homeTeamName"])
    away_label = label_for(away_club, event.get("awayTeamId"), event["awayTeamName"])

    title = f"{home_label} - {away_label} – {event['competition']}"
    if event.get("round"):
        title += f" – {event['round']}"
    return title


# Distinguishes men's/women's races in both the ICS title and the web list
# (see app.js's CYCLING_GENDER_EMOJI) -- several men's/women's one-day
# classics share the exact same competition name (e.g. "Ronde Van Brugge"),
# so the emoji is the only visual gender cue, not just decoration. Falls
# back to the plain bicycle for any event missing a gender (older snapshots
# from before this field existed, until they're next refreshed).
CYCLING_GENDER_EMOJI = {"men": "🚴‍♂️", "women": "🚴‍♀️"}


def format_cycling_title(event: dict) -> str:
    emoji = CYCLING_GENDER_EMOJI.get(event.get("gender"), "🚴")
    if event.get("round"):
        route = event.get("route") or {}
        return f"{emoji} {event['competition']} – {event['round']}: {route.get('start', '')} → {route.get('finish', '')}"
    year = event["start"][:4]
    return f"{emoji} {event['competition']} {year}"


def format_event_title(
    event: dict, clubs_by_id: dict[str, dict], perspective_club_ids: set[str] | None = None
) -> str:
    if event["sport"] == "football":
        return format_football_title(event, clubs_by_id, perspective_club_ids)
    if event["sport"] == "cycling":
        return format_cycling_title(event)
    raise ValueError(f"Unbekannte Sportart: {event['sport']!r}")


# --- ICS rendering -----------------------------------------------------
# Shared by the weekly combined-feed build (scripts/build_ics.py) and the
# on-demand personalized feed (api/calendar_ics.py), so the two never drift
# apart on VEVENT structure or line folding.


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
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_vevent(event: dict, clubs_by_id: dict, perspective_club_ids: set[str] | None = None) -> list[str]:
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

    lines.append(f"SUMMARY:{escape_text(format_event_title(event, clubs_by_id, perspective_club_ids))}")
    lines.append(f"DESCRIPTION:{escape_text(chr(10).join(description_parts))}")
    if event.get("location"):
        lines.append(f"LOCATION:{escape_text(event['location'])}")
    lines.append(f"CATEGORIES:{event['sport'].upper()}")
    lines.append("END:VEVENT")
    return lines


def build_calendar_text(
    events: list[dict],
    clubs_by_id: dict,
    calendar_name: str = "sportocal",
    perspective_club_ids: set[str] | None = None,
) -> str:
    """Renders a full VCALENDAR document (CRLF line endings, folded) from a
    list of events, already filtered/sorted by the caller."""
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//sportocal//kalender//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{calendar_name}",
        "X-WR-TIMEZONE:Europe/Berlin",
    ]
    for event in events:
        vevent_lines = build_vevent(event, clubs_by_id, perspective_club_ids)
        vevent_lines.insert(1, f"DTSTAMP:{now_stamp}")
        lines.extend(vevent_lines)
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_line(l) for l in lines) + "\r\n"


def load_all_events(data_dir: Path | None = None) -> list[dict]:
    events = []
    for path in sorted((data_dir or DATA_DIR).glob("*.json")):
        with path.open(encoding="utf-8") as f:
            snapshot = json.load(f)
        events.extend(snapshot.get("events", []))
    return events


def http_get_text(url: str, retries: int = 3, timeout: int = 20) -> str:
    """GET a URL and return the raw response body as text, with basic retry."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_error}")


def http_get_json(url: str, retries: int = 3, timeout: int = 20) -> Any:
    """GET a URL and parse it as JSON, with basic retry on transient failures."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last_error}")


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"WARNUNG: {message}", file=sys.stderr, flush=True)


def load_snapshot(source_id: str) -> dict:
    path = DATA_DIR / f"{source_id}.json"
    if not path.exists():
        return {"events": [], "lastChecked": None}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(source_id: str, events: list[dict], now_iso: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{source_id}.json"
    payload = {"events": events, "lastChecked": now_iso}
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")


_DIFF_IGNORED_FIELDS = {"id", "lastUpdated"}


def _event_label(event: dict) -> str:
    home = event.get("homeTeamName")
    away = event.get("awayTeamName")
    if home and away:
        return f"{home} - {away}"
    return event.get("round") or event.get("competition") or event.get("id", "?")


def diff_and_log(source_id: str, old_events: list[dict], new_events: list[dict]) -> bool:
    """Compare old vs new event lists by id, log human-readable changes.

    Diffs whatever raw fields an event happens to carry (sport-specific extras
    included) rather than a fixed field list, since the title itself is no
    longer stored -- it's generated at build time from these same fields.
    Returns True if anything changed (added/removed/modified).
    """
    old_by_id = {e["id"]: e for e in old_events}
    new_by_id = {e["id"]: e for e in new_events}

    changed = False

    for event_id, new_event in new_by_id.items():
        old_event = old_by_id.get(event_id)
        if old_event is None:
            changed = True
            log(f"[{source_id}] NEU: {_event_label(new_event)} ({new_event.get('start')})")
            continue
        fields = (set(old_event) | set(new_event)) - _DIFF_IGNORED_FIELDS
        for field in sorted(fields):
            old_value = old_event.get(field)
            new_value = new_event.get(field)
            if old_value != new_value:
                changed = True
                log(
                    f"[{source_id}] {_event_label(new_event)}: "
                    f"{field} von {old_value!r} auf {new_value!r} geändert"
                )

    for event_id, old_event in old_by_id.items():
        if event_id not in new_by_id:
            changed = True
            log(f"[{source_id}] ENTFERNT: {_event_label(old_event)} ({old_event.get('start')})")

    return changed


def normalize_text(text: str) -> str:
    """Lowercase, strip umlauts/punctuation for loose fuzzy matching."""
    import re

    text = text.lower()
    for umlaut, plain in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "ss")):
        text = text.replace(umlaut, plain)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_keyword(haystack: str, keyword: str) -> bool:
    """Substring match, except purely numeric keywords which need a digit
    boundary so e.g. keyword '2' doesn't accidentally match inside '2025'."""
    import re

    if keyword.isdigit():
        return re.search(rf"(?<!\d){re.escape(keyword)}(?!\d)", haystack) is not None
    return keyword in haystack


def clean_wikitext(text: str) -> str:
    """Best-effort conversion of a small wikitext fragment to plain text."""
    import re

    if text is None:
        return ""
    # Drop file/image embeds entirely (icons etc. have no useful text value).
    text = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", text, flags=re.IGNORECASE)
    # Strip simple (non-nested) templates a few passes to handle mild nesting.
    for _ in range(3):
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    # [[target|display]] -> display, [[target]] -> target
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"'''?", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
