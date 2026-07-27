#!/usr/bin/env python3
"""Build cycling snapshots from the manually-maintained CSV sheet
(data/manual/stage-race.csv) for stage races whose Wikipedia article isn't
reliably scrapeable -- see scripts/tools/verify_race_sources.py and the
README section on how that decision gets made.

config.json entries with "source": "manual" have no wikipediaTitleTemplate
and are skipped by fetch_cycling.py (see its main()); this script is their
equivalent, reusing fetch_cycling.py's build_stage_events()/merge_events()
rather than reimplementing event construction or the additive-merge logic.

Not part of the weekly update.yml pipeline -- run manually whenever the CSV
sheet changes: `python scripts/build_manual_cycling.py`.

CSV columns: race_id,year,stage_label,date,start,finish,type
  - race_id: must match a "source": "manual" entry's id in config.json.
  - date: ISO format YYYY-MM-DD (manual entry, no wikitext month names to
    parse, unlike fetch_cycling.py's parse_single_date).
  - type: must be one of common.STAGE_TYPES.
A row that fails validation is skipped with a warning, never aborts the run.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone

from common import ROOT_DIR, STAGE_TYPES, diff_and_log, load_config, load_snapshot, log, save_snapshot, warn
from fetch_cycling import build_stage_events, merge_events

CSV_PATH = ROOT_DIR / "data" / "manual" / "stage-race.csv"

REQUIRED_FIELDS = ("date", "start", "finish")


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
            }
        )
    return groups


def main() -> None:
    if not CSV_PATH.exists():
        warn(f"{CSV_PATH} nicht gefunden, nichts zu tun.")
        return

    config = load_config()
    races_by_id = {race["id"]: race for race in config["cycling"]["races"]}
    now_iso = datetime.now(timezone.utc).isoformat()

    groups = group_rows(load_rows())
    for (race_id, year), stage_rows in groups.items():
        race = races_by_id.get(race_id)
        if race is None:
            warn(f"[{race_id}] Kein Eintrag in config.json (cycling.races), Zeilen fuer {year} werden uebersprungen.")
            continue

        stage_rows.sort(key=lambda s: s["date"])
        events = build_stage_events(race, year, stage_rows)

        source_id = f"cycling-{race_id}"
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
