import csv
import io
from datetime import date

import build_manual_cycling
import fetch_cycling


def rows_from_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_reuses_fetch_cycling_merge_events_directly():
    """No reimplementation of the additive-merge logic from Section 8 --
    build_manual_cycling.merge_events must be the exact same function object."""
    assert build_manual_cycling.merge_events is fetch_cycling.merge_events


def test_group_rows_groups_by_race_id_and_year():
    csv_text = (
        "race_id,year,stage_label,date,start,finish,type\n"
        "paris-nice,2026,Etappe 1,2026-03-08,Paris,Nemours,Flat\n"
        "paris-nice,2026,Etappe 2,2026-03-09,Nemours,Ligny-en-Barrois,Hilly\n"
    )

    groups = build_manual_cycling.group_rows(rows_from_csv(csv_text))

    assert list(groups.keys()) == [("paris-nice", 2026)]
    stages = groups[("paris-nice", 2026)]
    assert [s["label"] for s in stages] == ["Etappe 1", "Etappe 2"]
    assert stages[0]["date"] == date(2026, 3, 8)
    assert stages[0]["start_loc"] == "Paris"
    assert stages[0]["finish_loc"] == "Nemours"
    assert stages[0]["type"] == "Flat"


def test_group_rows_skips_row_with_unknown_stage_type():
    csv_text = (
        "race_id,year,stage_label,date,start,finish,type\n"
        "paris-nice,2026,Etappe 1,2026-03-08,Paris,Nemours,Not A Real Type\n"
    )

    groups = build_manual_cycling.group_rows(rows_from_csv(csv_text))

    assert groups == {}


def test_group_rows_skips_row_with_missing_required_field():
    csv_text = (
        "race_id,year,stage_label,date,start,finish,type\n"
        "paris-nice,2026,Etappe 1,,Paris,Nemours,Flat\n"
    )

    groups = build_manual_cycling.group_rows(rows_from_csv(csv_text))

    assert groups == {}


def test_group_rows_skips_row_with_malformed_date():
    csv_text = (
        "race_id,year,stage_label,date,start,finish,type\n"
        "paris-nice,2026,Etappe 1,08 March 2026,Paris,Nemours,Flat\n"
    )

    groups = build_manual_cycling.group_rows(rows_from_csv(csv_text))

    assert groups == {}


def test_group_rows_keeps_valid_rows_alongside_invalid_ones():
    csv_text = (
        "race_id,year,stage_label,date,start,finish,type\n"
        "paris-nice,2026,Etappe 1,2026-03-08,Paris,Nemours,Flat\n"
        "paris-nice,2026,Etappe 2,2026-03-09,Nemours,Ligny-en-Barrois,Not A Real Type\n"
    )

    groups = build_manual_cycling.group_rows(rows_from_csv(csv_text))

    stages = groups[("paris-nice", 2026)]
    assert len(stages) == 1
    assert stages[0]["label"] == "Etappe 1"


def test_main_writes_merged_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(build_manual_cycling, "CSV_PATH", tmp_path / "stage-race.csv")
    (tmp_path / "stage-race.csv").write_text(
        "race_id,year,stage_label,date,start,finish,type\n"
        "paris-nice,2026,Etappe 1,2026-03-08,Paris,Nemours,Flat\n",
        encoding="utf-8",
    )

    import common

    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        build_manual_cycling,
        "load_config",
        lambda: {"cycling": {"races": [{"id": "paris-nice", "name": "Paris-Nice", "type": "stage-race", "source": "manual"}]}},
    )

    build_manual_cycling.main()

    snapshot = common.load_snapshot("cycling-paris-nice")
    assert len(snapshot["events"]) == 1
    assert snapshot["events"][0]["round"] == "Etappe 1"
    assert snapshot["events"][0]["start"] == "2026-03-08"
