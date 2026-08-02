#!/usr/bin/env python3
"""Build cycling snapshots from the manually-maintained CSV sheets
(data/manual/stage-race.csv, data/manual/one-day.csv) for races whose
Wikipedia article isn't reliably scrapeable -- see
scripts/tools/verify_race_sources.py and the README section on how that
decision gets made.

config.json entries with "source": "manual" have no wikipediaTitleTemplate
and are skipped by fetch_cycling.py (see its main()); this script is their
equivalent, reusing fetch_cycling.py's build_stage_events()/build_one_day_event()/
merge_events() rather than reimplementing event construction or the
additive-merge logic.

Not part of the weekly update.yml pipeline -- run manually whenever a CSV
sheet changes: `python scripts/build_manual_cycling.py`.

data/manual/stage-race.csv columns: race_id,year,stage_label,date,start,finish,type,start_time
  - race_id: must match a "source": "manual" entry's id in config.json.
  - date: ISO format YYYY-MM-DD (manual entry, no wikitext month names to
    parse, unlike fetch_cycling.py's parse_single_date).
  - type: must be one of common.STAGE_TYPES.
  - start_time: optional, "HH:MM" 24h, Europe/Berlin local time (source
    listings report CET/CEST). When given, the stage gets a real timed
    DTSTART and timeConfirmed: true instead of the all-day/unconfirmed
    default -- see build_stage_events() in fetch_cycling.py, which this
    script reuses directly. Leave blank when no start time is published yet
    (typical for Grand Tours, published only ~1-2 weeks out).

data/manual/one-day.csv columns: race_id,year,date,start,finish,type
  - same race_id/date/type rules as above; unlike a stage race, one row is
    one edition (no stage_label), and start/finish may be left blank when
    not yet confirmed -- location falls back to whichever of the two is set,
    or None if both are blank.

A row that fails validation is skipped with a warning, never aborts the run.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone

from common import ROOT_DIR, STAGE_TYPES, diff_and_log, load_config, load_snapshot, log, save_snapshot, warn
from fetch_cycling import build_one_day_event, build_stage_events, merge_events

CSV_PATH = ROOT_DIR / "data" / "manual" / "stage-race.csv"
ONE_DAY_CSV_PATH = ROOT_DIR / "data" / "manual" / "one-day.csv"

REQUIRED_FIELDS = ("date", "start", "finish")
ONE_DAY_REQUIRED_FIELDS = ("date",)


def load_rows() -> list[dict]:
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _row_label(row: dict) -> str:
    return f"{row.get('race_id', '?')}/{row.get('year', '?')}"


def validate_row(row: dict) -> bool:
    for field in REQUIRED_FIELDS:
        if not (row.get(field) or "").strip():
            warn(f"[{_row_label(row)}] Pflichtfeld '{field}' fehlt, Zeile wird uebersprungen.")
            return False
    stage_type = (row.get("type") or "").strip()
    if stage_type not in STAGE_TYPES:
        warn(f"[{_row_label(row)}] Unbekannter Etappentyp '{stage_type}', Zeile wird uebersprungen.")
        return False
    return True


def group_rows(rows: list[dict]) -> dict[tuple[str, int], list[dict]]:
    """Validated rows grouped by (race_id, year) into build_stage_events()'s
    expected stage-dict shape (label/date/start_loc/finish_loc/type)."""
    groups: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        if not validate_row(row):
            continue
        try:
            year = int(row["year"])
            stage_date = date.fromisoformat(row["date"].strip())
        except ValueError as exc:
            warn(f"[{_row_label(row)}] Ungueltiger Wert ({exc}), Zeile wird uebersprungen.")
            continue

        key = (row["race_id"].strip(), year)
        groups.setdefault(key, []).append(
            {
                "label": (row.get("stage_label") or "").strip(),
                "date": stage_date,
                "start_loc": row["start"].strip(),
                "finish_loc": row["finish"].strip(),
                "type": row["type"].strip(),
                "start_time": (row.get("start_time") or "").strip(),
            }
        )
    return groups


def load_one_day_rows() -> list[dict]:
    with ONE_DAY_CSV_PATH.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def validate_one_day_row(row: dict) -> bool:
    for field in ONE_DAY_REQUIRED_FIELDS:
        if not (row.get(field) or "").strip():
            warn(f"[{_row_label(row)}] Pflichtfeld '{field}' fehlt, Zeile wird uebersprungen.")
            return False
    race_type = (row.get("type") or "").strip()
    if race_type not in STAGE_TYPES:
        warn(f"[{_row_label(row)}] Unbekannter Renntyp '{race_type}', Zeile wird uebersprungen.")
        return False
    return True


def group_one_day_rows(rows: list[dict]) -> dict[tuple[str, int], dict]:
    """Validated one-day rows keyed by (race_id, year) -- unlike a stage race,
    one edition is a single row, not a list of stages, so a later duplicate
    row for the same key overwrites the earlier one rather than appending."""
    groups: dict[tuple[str, int], dict] = {}
    for row in rows:
        if not validate_one_day_row(row):
            continue
        try:
            year = int(row["year"])
            event_date = date.fromisoformat(row["date"].strip())
        except ValueError as exc:
            warn(f"[{_row_label(row)}] Ungueltiger Wert ({exc}), Zeile wird uebersprungen.")
            continue

        key = (row["race_id"].strip(), year)
        groups[key] = {
            "date": event_date,
            "start": (row.get("start") or "").strip(),
            "finish": (row.get("finish") or "").strip(),
            "type": row["type"].strip(),
        }
    return groups


def build_one_day_event_from_row(race: dict, year: int, entry: dict) -> dict:
    start_loc, finish_loc = entry["start"], entry["finish"]
    if start_loc and finish_loc:
        location = f"{start_loc} → {finish_loc}"
    else:
        location = start_loc or finish_loc or None
    route = {"start": start_loc, "finish": finish_loc, "type": entry["type"]}
    return build_one_day_event(race, year, entry["date"], location, route=route)


def sync_snapshot(source_id: str, events: list[dict], now_iso: str) -> None:
    old_snapshot = load_snapshot(source_id)
    merged_events = merge_events(old_snapshot["events"], events)
    changed = diff_and_log(source_id, old_snapshot["events"], merged_events)
    if changed:
        log(f"[{source_id}] Aenderungen gefunden, Snapshot wird aktualisiert.")
    else:
        log(f"[{source_id}] Keine Aenderungen.")
    save_snapshot(source_id, merged_events, now_iso)


def process_stage_races(races_by_id: dict[str, dict], now_iso: str) -> None:
    if not CSV_PATH.exists():
        warn(f"{CSV_PATH} nicht gefunden, ueberspringe Etappenrennen.")
        return

    groups = group_rows(load_rows())
    for (race_id, year), stage_rows in groups.items():
        race = races_by_id.get(race_id)
        if race is None:
            warn(f"[{race_id}] Kein Eintrag in config.json (cycling.races), Zeilen fuer {year} werden uebersprungen.")
            continue

        stage_rows.sort(key=lambda s: s["date"])
        events = build_stage_events(race, year, stage_rows)
        sync_snapshot(f"cycling-{race_id}", events, now_iso)


def process_one_day_races(races_by_id: dict[str, dict], now_iso: str) -> None:
    if not ONE_DAY_CSV_PATH.exists():
        warn(f"{ONE_DAY_CSV_PATH} nicht gefunden, ueberspringe Eintagesrennen.")
        return

    groups = group_one_day_rows(load_one_day_rows())
    for (race_id, year), entry in groups.items():
        race = races_by_id.get(race_id)
        if race is None:
            warn(f"[{race_id}] Kein Eintrag in config.json (cycling.races), Zeile fuer {year} wird uebersprungen.")
            continue

        events = [build_one_day_event_from_row(race, year, entry)]
        sync_snapshot(f"cycling-{race_id}", events, now_iso)


def main() -> None:
    config = load_config()
    races_by_id = {race["id"]: race for race in config["cycling"]["races"]}
    now_iso = datetime.now(timezone.utc).isoformat()

    process_stage_races(races_by_id, now_iso)
    process_one_day_races(races_by_id, now_iso)


if __name__ == "__main__":
    main()
