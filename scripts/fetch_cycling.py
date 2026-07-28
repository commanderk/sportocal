#!/usr/bin/env python3
"""Fetch Grand Tour stages and German cycling classics from Wikipedia.

There is no free, well-maintained API for cycling schedules comparable to
OpenLigaDB. After evaluating ProCyclingStats (no documented allowance for
scraping) and official race sites (no consistent structure across races),
Wikipedia was chosen: content is freely licensed (CC BY-SA), and every race
covered here publishes a year-specific article with either

  - a one-line infobox date (one-day classics), or
  - a "Route and stages" / "Schedule" wikitable with one row per stage
    (Grand Tours, Deutschland Tour)

which we parse directly from the wikitext via the MediaWiki API.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from urllib.parse import urlencode

from common import (
    clean_wikitext,
    diff_and_log,
    load_config,
    load_snapshot,
    log,
    http_get_json,
    save_snapshot,
    warn,
)

STAGE_TABLE_SECTION_HINTS = ("route and stages", "schedule", "stages", "route")
MONTHS = (
    "january february march april may june july august september october "
    "november december"
).split()


def wiki_get(api_base: str, params: dict) -> dict:
    query = urlencode({**params, "format": "json"})
    return http_get_json(f"{api_base}?{query}")


def _single_page(data: dict) -> dict:
    """`action=query` always returns exactly one page for a single `titles=`
    lookup, keyed by pageid (or "-1" for a missing title)."""
    return next(iter(data["query"]["pages"].values()))


def fetch_full_wikitext(api_base: str, title: str) -> str | None:
    """Full current wikitext via the lightweight revisions endpoint (no
    parser invocation), per MediaWiki API etiquette
    (https://www.mediawiki.org/wiki/API:Etiquette)."""
    data = wiki_get(
        api_base,
        {"action": "query", "prop": "revisions", "rvslots": "main", "rvprop": "content", "titles": title},
    )
    page = _single_page(data)
    if "missing" in page:
        return None
    return page["revisions"][0]["slots"]["main"]["*"]


def extract_section(wikitext: str, section_index: int) -> str | None:
    """Mimic MediaWiki's `section=N` extraction locally, since the
    `revisions` endpoint (unlike `action=parse`) has no section parameter.

    Section 0 is the lead (everything before the first heading). Section N
    (N >= 1) is the Nth heading in document order, including that heading
    line, up to (not including) the next heading of equal or higher level --
    the same numbering `action=parse&prop=sections` uses, which
    fetch_stage_table_section_index() still calls directly.

    Known limitation: heading detection is a plain regex over the raw
    wikitext, so it can miscount relative to MediaWiki's own parser for
    edge cases such as heading-like lines inside <!-- comments -->,
    <nowiki> blocks, or template transclusions. This is only verified
    against the two fixtures in tests/fixtures/, not against every possible
    wikitext shape.
    """
    heading_re = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$", re.MULTILINE)
    headings = list(heading_re.finditer(wikitext))
    if section_index == 0:
        end = headings[0].start() if headings else len(wikitext)
        return wikitext[:end]
    if section_index > len(headings):
        return None
    start_match = headings[section_index - 1]
    level = len(start_match.group(1))
    start = start_match.start()
    end = len(wikitext)
    for next_match in headings[section_index:]:
        if len(next_match.group(1)) <= level:
            end = next_match.start()
            break
    return wikitext[start:end]


def fetch_wikitext_section(api_base: str, title: str, section: int | None = None) -> str | None:
    wikitext = fetch_full_wikitext(api_base, title)
    if wikitext is None:
        return None
    if section is None:
        return wikitext
    return extract_section(wikitext, section)


def fetch_stage_table_section_index(api_base: str, title: str) -> int | None:
    data = wiki_get(api_base, {"action": "parse", "page": title, "prop": "sections"})
    if "error" in data:
        return None
    for section in data["parse"]["sections"]:
        if section["line"].strip().lower() in STAGE_TABLE_SECTION_HINTS:
            return int(section["index"])
    return None


def page_exists(api_base: str, title: str) -> bool:
    """Lightweight existence check (no content transfer): `action=query`
    with `prop=info` only, not `revisions`."""
    data = wiki_get(api_base, {"action": "query", "prop": "info", "titles": title})
    return "missing" not in _single_page(data)


def parse_infobox_field(wikitext: str, field: str) -> str | None:
    match = re.search(rf"^\|\s*{re.escape(field)}\s*=\s*(.+)$", wikitext, re.MULTILINE)
    if not match:
        return None
    value = clean_wikitext(match.group(1))
    return value or None


def parse_single_date(text: str, fallback_year: int) -> date | None:
    """Parse '17 August 2025' or the first half of a range like '20-24 August 2025'."""
    text = text.replace("–", "-").replace("—", "-")
    match = re.search(r"(\d{1,2})\s*(?:-\s*\d{1,2}\s*)?([A-Za-z]+)\s*(\d{4})?", text)
    if not match:
        return None
    day, month_name, year = match.groups()
    month_name_norm = month_name.strip().lower()
    if month_name_norm not in MONTHS:
        return None
    month = MONTHS.index(month_name_norm) + 1
    year_int = int(year) if year else fallback_year
    try:
        return date(year_int, month, int(day))
    except ValueError:
        return None


def strip_cell_attrs(text: str) -> str:
    """Remove a leading MediaWiki cell-attribute prefix like `style="..." |`,
    without being confused by pipes nested inside [[...]] or {{...}} that are
    part of the actual cell content."""
    depth = 0
    i, n = 0, len(text)
    while i < n:
        if text[i : i + 2] in ("[[", "{{"):
            depth += 1
            i += 2
            continue
        if text[i : i + 2] in ("]]", "}}"):
            depth = max(0, depth - 1)
            i += 2
            continue
        if text[i] == "|" and depth == 0:
            prefix = text[:i]
            return text[i + 1 :] if "=" in prefix else text
        i += 1
    return text


def strip_stage_type_suffix(stage_type: str) -> str:
    """Wikipedia's stage-type cell says e.g. "Hilly stage", but
    common.STAGE_TYPES uses the short form ("Hilly") so scraped and
    manually-entered (build_manual_cycling.py) values share one vocabulary --
    "Individual/Team time trial" already has no "stage" suffix and passes
    through unchanged."""
    return re.sub(r"\s+stage$", "", stage_type, flags=re.IGNORECASE)


def parse_stage_table(wikitext: str, year: int) -> list[dict]:
    table_match = re.search(r"\{\|.*?\n\|\}", wikitext, re.DOTALL)
    if not table_match:
        return []
    table = table_match.group(0)

    stages = []
    for row in table.split("|-")[1:]:
        row = row.strip()
        if not row or row.startswith("!") and "Total" in row:
            continue
        # Stage number/label, e.g. "! scope=\"row\" |[[...#Stage 1|1]]" or "...|P]]"
        header_match = re.search(r'!\s*scope="row"[^|]*\|(.+)', row)
        if not header_match:
            continue
        label_raw = clean_wikitext(header_match.group(1).splitlines()[0])
        if not label_raw or label_raw.lower() == "total":
            continue

        lines = [l.strip() for l in row.splitlines() if l.strip().startswith("|") and not l.strip().startswith("|-")]
        # cells layout (after the header cell already consumed above):
        # [date, course, distance, type-icon(usually empty after cleaning), type-text, winner]
        cells = [clean_wikitext(strip_cell_attrs(l[1:])) for l in lines]
        if len(cells) < 3:
            continue

        date_text, course = cells[0], cells[1]
        stage_date = parse_single_date(date_text, year)
        if not stage_date:
            continue

        stage_type = ""
        for c in cells[3:]:
            # Skip cells that are just leftover punctuation from a cleaned-out
            # icon embed (e.g. a stray "|" from "| |[[File:...]]", seen on the
            # Deutschland Tour prologue row) rather than an actual type label.
            if c and any(ch.isalpha() for ch in c):
                stage_type = strip_stage_type_suffix(c)
                break

        if " to " in course:
            start_loc, finish_loc = [p.strip() for p in course.split(" to ", 1)]
        else:
            start_loc, finish_loc = course.strip(), course.strip()

        stage_label = "Prolog" if label_raw.strip().upper() == "P" else f"Etappe {label_raw.strip()}"
        stages.append(
            {
                "label": stage_label,
                "date": stage_date,
                "start_loc": start_loc,
                "finish_loc": finish_loc,
                "type": stage_type,
            }
        )
    return stages


def build_stage_events(race: dict, year: int, stages: list[dict]) -> list[dict]:
    events = []
    for stage in stages:
        events.append(
            {
                "id": f"cycling-{race['id']}-{year}-{stage['label'].lower().replace(' ', '')}",
                "sport": "cycling",
                "competition": race["name"],
                "gender": race["gender"],
                "round": stage["label"],
                "start": stage["date"].isoformat(),
                "timeConfirmed": False,
                "location": f"{stage['start_loc']} → {stage['finish_loc']}",
                "route": {"start": stage["start_loc"], "finish": stage["finish_loc"], "type": stage["type"]},
            }
        )
    return events


def build_one_day_event(
    race: dict, year: int, event_date: date, location: str | None, route: dict | None = None
) -> dict:
    event = {
        "id": f"cycling-{race['id']}-{year}",
        "sport": "cycling",
        "competition": race["name"],
        "gender": race["gender"],
        "round": None,
        "start": event_date.isoformat(),
        "timeConfirmed": False,
        "location": location,
    }
    if route:
        event["route"] = route
    return event


def fetch_race_year(api_base: str, race: dict, year: int) -> list[dict] | None:
    title = race["wikipediaTitleTemplate"].format(year=year)
    if not page_exists(api_base, title):
        return None

    infobox_wikitext = fetch_wikitext_section(api_base, title, section=0)
    if infobox_wikitext is None:
        return None

    if race["type"] == "one-day":
        date_field = parse_infobox_field(infobox_wikitext, "date")
        if not date_field:
            warn(f"[{race['id']}] Kein Datum im Infobox von '{title}' gefunden.")
            return None
        event_date = parse_single_date(date_field, year)
        if not event_date:
            warn(f"[{race['id']}] Datum '{date_field}' aus '{title}' konnte nicht geparst werden.")
            return None
        return [build_one_day_event(race, year, event_date, None)]

    # stage-race: find and parse the stage table
    section_index = fetch_stage_table_section_index(api_base, title)
    if section_index is None:
        warn(f"[{race['id']}] Keine Etappen-Tabelle in '{title}' gefunden.")
        return None
    section_wikitext = fetch_wikitext_section(api_base, title, section=section_index)
    if not section_wikitext:
        return None
    stages = parse_stage_table(section_wikitext, year)
    if not stages:
        warn(f"[{race['id']}] Etappen-Tabelle in '{title}' konnte nicht geparst werden.")
        return None
    return build_stage_events(race, year, stages)


def fetch_race(api_base: str, race: dict, today: date) -> list[dict] | None:
    for year in (today.year, today.year + 1):
        try:
            events = fetch_race_year(api_base, race, year)
        except Exception as exc:
            warn(f"[{race['id']}] Fehler beim Verarbeiten von Jahr {year}: {exc}")
            continue
        if not events:
            continue
        last_date = max(date.fromisoformat(e["start"]) for e in events)
        if last_date >= today or year == today.year + 1:
            log(f"[{race['id']}] {len(events)} Termin(e) fuer {year} geladen.")
            return events
        log(f"[{race['id']}] Ausgabe {year} liegt bereits vollstaendig in der Vergangenheit, pruefe naechstes Jahr.")
    warn(f"[{race['id']}] Keine verwendbaren Termine gefunden (weder aktuelles noch naechstes Jahr).")
    return None


def merge_events(old_events: list[dict], new_events: list[dict]) -> list[dict]:
    """Additive merge for cycling snapshots: unlike football (season-cut by
    design, see README), a race's `id` has no season/league coupling, so a
    fetch run must never drop a past edition just because it wasn't part of
    this run's (today.year, today.year + 1) window. New/changed ids overlay
    the old snapshot; every old id that isn't in `new_events` is kept as-is."""
    by_id = {e["id"]: e for e in old_events}
    by_id.update({e["id"]: e for e in new_events})
    return sorted(by_id.values(), key=lambda e: (e["start"], e["id"]))


def main() -> None:
    config = load_config()
    api_base = config["cycling"]["wikipediaApi"]
    today = datetime.now(timezone.utc).date()
    now_iso = datetime.now(timezone.utc).isoformat()

    for race in config["cycling"]["races"]:
        if race.get("source") == "manual":
            continue  # handled by build_manual_cycling.py instead, see README

        source_id = f"cycling-{race['id']}"
        try:
            events = fetch_race(api_base, race, today)
        except Exception as exc:
            warn(f"[{race['id']}] Unerwarteter Fehler, ueberspringe: {exc}")
            continue

        if events is None:
            continue

        old_snapshot = load_snapshot(source_id)
        merged_events = merge_events(old_snapshot["events"], events)
        changed = diff_and_log(source_id, old_snapshot["events"], merged_events)
        if changed:
            log(f"[{source_id}] Aenderungen gefunden, Snapshot wird aktualisiert.")
        else:
            log(f"[{source_id}] Keine Aenderungen.")
        save_snapshot(source_id, merged_events, now_iso)


if __name__ == "__main__":
    main()
