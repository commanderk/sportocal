from datetime import date
from pathlib import Path

import common
import fetch_cycling

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# --- one-day race: infobox parsing -------------------------------------


def test_parse_infobox_field_finds_date():
    wikitext = load_fixture("one_day_infobox.txt")
    date_field = fetch_cycling.parse_infobox_field(wikitext, "date")
    assert date_field == "17 August 2025"


def test_parse_single_date_from_infobox_field():
    wikitext = load_fixture("one_day_infobox.txt")
    date_field = fetch_cycling.parse_infobox_field(wikitext, "date")
    parsed = fetch_cycling.parse_single_date(date_field, fallback_year=2025)
    assert parsed == date(2025, 8, 17)


# --- stage race: section extraction + stage table parsing ---------------


def test_extract_section_lead_stops_before_first_heading():
    wikitext = load_fixture("stage_race_schedule.txt")
    lead = fetch_cycling.extract_section(wikitext, 0)
    assert "Infobox cycling race report" in lead
    assert "== Teams ==" not in lead


def test_extract_section_schedule_stops_before_stages_heading():
    wikitext = load_fixture("stage_race_schedule.txt")
    schedule = fetch_cycling.extract_section(wikitext, 2)
    assert schedule.startswith("== Schedule ==")
    assert "wikitable" in schedule
    assert "== Stages ==" not in schedule
    assert "Prologue ===" not in schedule


def test_parse_stage_table_from_extracted_section():
    wikitext = load_fixture("stage_race_schedule.txt")
    schedule = fetch_cycling.extract_section(wikitext, 2)
    stages = fetch_cycling.parse_stage_table(schedule, year=2025)

    assert [s["label"] for s in stages] == ["Prolog", "Etappe 1", "Etappe 2", "Etappe 3", "Etappe 4"]
    assert [s["date"] for s in stages] == [
        date(2025, 8, 20),
        date(2025, 8, 21),
        date(2025, 8, 22),
        date(2025, 8, 23),
        date(2025, 8, 24),
    ]
    assert stages[0]["start_loc"] == "Essen"
    assert stages[0]["finish_loc"] == "Essen"
    assert stages[1]["start_loc"] == "Essen"
    assert stages[1]["finish_loc"] == "Herford"
    assert stages[4]["start_loc"] == "Halle (Saale)"
    assert stages[4]["finish_loc"] == "Magdeburg"


def test_parse_stage_table_strips_stage_suffix_from_type():
    """Wikitext says "Hilly stage"/"Flat stage" (with suffix), but
    common.STAGE_TYPES uses the short form so scraped and manually-entered
    (build_manual_cycling.py) values share one vocabulary. "Individual time
    trial" has no suffix to begin with and must pass through unchanged."""
    wikitext = load_fixture("stage_race_schedule.txt")
    schedule = fetch_cycling.extract_section(wikitext, 2)
    stages = fetch_cycling.parse_stage_table(schedule, year=2025)

    assert [s["type"] for s in stages] == ["Individual time trial", "Hilly", "Hilly", "Hilly", "Flat"]
    assert all(s["type"] in common.STAGE_TYPES for s in stages)


def test_strip_stage_type_suffix_is_case_insensitive():
    assert fetch_cycling.strip_stage_type_suffix("Mountain Stage") == "Mountain"
    assert fetch_cycling.strip_stage_type_suffix("Individual time trial") == "Individual time trial"


def test_stage_types_includes_prologue_for_deutschland_tour():
    assert "Prologue" in common.STAGE_TYPES


# --- build_stage_events(): optional per-stage start time -----------------

TEST_RACE = {"id": "test-race", "name": "Test Race", "gender": "men"}


def _stage(**overrides):
    stage = {"label": "Etappe 1", "date": date(2026, 8, 3), "start_loc": "A", "finish_loc": "B", "type": "Flat"}
    stage.update(overrides)
    return stage


def test_build_stage_events_without_start_time_stays_all_day_unconfirmed():
    """Wikipedia's stage tables never publish start times, so a scraped
    stage's dict has no "start_time" key at all -- must behave exactly like
    before this feature existed."""
    events = fetch_cycling.build_stage_events(TEST_RACE, 2026, [_stage()])
    assert events[0]["start"] == "2026-08-03"
    assert events[0]["timeConfirmed"] is False


def test_build_stage_events_with_empty_start_time_string_stays_unconfirmed():
    """The manual CSV's start_time column exists on every row once any stage
    in the sheet uses it (see build_manual_cycling.py), but is blank for
    stages whose time isn't published yet -- must behave identically to the
    key being absent entirely."""
    events = fetch_cycling.build_stage_events(TEST_RACE, 2026, [_stage(start_time="")])
    assert events[0]["start"] == "2026-08-03"
    assert events[0]["timeConfirmed"] is False


def test_build_stage_events_with_start_time_produces_confirmed_utc_datetime():
    """14:35 Europe/Berlin on a summer (CEST, UTC+2) date -> 12:35 UTC."""
    events = fetch_cycling.build_stage_events(TEST_RACE, 2026, [_stage(date=date(2026, 8, 4), start_time="14:35")])
    assert events[0]["start"] == "2026-08-04T12:35:00Z"
    assert events[0]["timeConfirmed"] is True


def test_build_stage_events_with_start_time_is_dst_aware_not_a_fixed_offset():
    """A winter (CET, UTC+1) date must convert with a different offset than
    the summer case above -- same DST-aware Europe/Berlin conversion
    convention as common.reminder_trigger_utc(), not a hardcoded +2h."""
    events = fetch_cycling.build_stage_events(TEST_RACE, 2026, [_stage(date=date(2026, 1, 10), start_time="14:00")])
    assert events[0]["start"] == "2026-01-10T13:00:00Z"


# --- revisions-API response parsing (mocked, no network) ----------------

REVISIONS_OK = {
    "query": {
        "pages": {
            "123": {
                "pageid": 123,
                "ns": 0,
                "title": "Some Race 2025",
                "revisions": [
                    {"slots": {"main": {"contentmodel": "wikitext", "contentformat": "text/x-wiki", "*": "hello wikitext"}}}
                ],
            }
        }
    }
}

# Real shape captured from a live `action=query&prop=revisions...` call
# against a nonexistent title.
REVISIONS_MISSING = {"query": {"pages": {"-1": {"ns": 0, "title": "Does Not Exist", "missing": ""}}}}

# Real shape captured from a live `action=query&prop=info...` call.
INFO_OK = {
    "query": {
        "pages": {
            "123": {
                "pageid": 123,
                "ns": 0,
                "title": "Some Race 2025",
                "contentmodel": "wikitext",
                "pagelanguage": "en",
                "lastrevid": 1,
                "length": 100,
            }
        }
    }
}
INFO_MISSING = {
    "query": {
        "pages": {
            "-1": {
                "ns": 0,
                "title": "Does Not Exist",
                "missing": "",
                "contentmodel": "wikitext",
                "pagelanguage": "en",
                "pagelanguagehtmlcode": "en",
                "pagelanguagedir": "ltr",
            }
        }
    }
}


def fake_http_get_json(responses_by_marker):
    def fake(url: str):
        for marker, response in responses_by_marker.items():
            if marker in url:
                return response
        raise AssertionError(f"unexpected URL in test: {url}")

    return fake


def test_fetch_full_wikitext_returns_content(monkeypatch):
    monkeypatch.setattr(fetch_cycling, "http_get_json", fake_http_get_json({"prop=revisions": REVISIONS_OK}))
    assert fetch_cycling.fetch_full_wikitext("https://en.wikipedia.org/w/api.php", "Some Race 2025") == "hello wikitext"


def test_fetch_full_wikitext_returns_none_for_missing_page(monkeypatch):
    monkeypatch.setattr(fetch_cycling, "http_get_json", fake_http_get_json({"prop=revisions": REVISIONS_MISSING}))
    assert fetch_cycling.fetch_full_wikitext("https://en.wikipedia.org/w/api.php", "Does Not Exist") is None


def test_page_exists_true(monkeypatch):
    monkeypatch.setattr(fetch_cycling, "http_get_json", fake_http_get_json({"prop=info": INFO_OK}))
    assert fetch_cycling.page_exists("https://en.wikipedia.org/w/api.php", "Some Race 2025") is True


def test_page_exists_false_for_missing_page(monkeypatch):
    monkeypatch.setattr(fetch_cycling, "http_get_json", fake_http_get_json({"prop=info": INFO_MISSING}))
    assert fetch_cycling.page_exists("https://en.wikipedia.org/w/api.php", "Does Not Exist") is False


# --- additive snapshot merge (cycling keeps every past edition -- no
# season-cut the way football has, see README) --------------------------


def test_merge_events_adds_new_id_and_keeps_old_one():
    old = [{"id": "cycling-x-2026-etappe1", "start": "2026-08-01"}]
    new = [{"id": "cycling-x-2027-etappe1", "start": "2027-08-01"}]

    merged = fetch_cycling.merge_events(old, new)

    assert [e["id"] for e in merged] == ["cycling-x-2026-etappe1", "cycling-x-2027-etappe1"]


def test_merge_events_updates_existing_id_in_place():
    old = [{"id": "cycling-x-2026-etappe1", "start": "2026-08-01", "location": "A"}]
    new = [{"id": "cycling-x-2026-etappe1", "start": "2026-08-01", "location": "B"}]

    merged = fetch_cycling.merge_events(old, new)

    assert len(merged) == 1
    assert merged[0]["location"] == "B"


def test_merge_events_never_drops_an_old_id_missing_from_new():
    old = [
        {"id": "cycling-x-2025-etappe1", "start": "2025-08-01"},
        {"id": "cycling-x-2026-etappe1", "start": "2026-08-01"},
    ]
    new = [{"id": "cycling-x-2026-etappe1", "start": "2026-08-01"}]  # this run only re-fetched 2026

    merged = fetch_cycling.merge_events(old, new)

    assert {e["id"] for e in merged} == {"cycling-x-2025-etappe1", "cycling-x-2026-etappe1"}


def test_main_merges_snapshots_additively_across_consecutive_runs(monkeypatch, tmp_path):
    """Two consecutive main() runs (one per year, as happens once the 2026
    edition falls out of fetch_race()'s (today, today+1) window and the 2027
    edition enters it) must leave both editions in the saved snapshot -- not
    just the most recently fetched one."""
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        fetch_cycling,
        "load_config",
        lambda: {
            "cycling": {
                "wikipediaApi": "https://en.wikipedia.org/w/api.php",
                "races": [{"id": "testrace", "name": "Test Race", "type": "stage-race"}],
            }
        },
    )
    yearly_events = iter(
        [
            [
                {
                    "id": "cycling-testrace-2026-etappe1",
                    "sport": "cycling",
                    "competition": "Test Race",
                    "round": "Etappe 1",
                    "start": "2026-08-01",
                    "timeConfirmed": False,
                    "location": "A",
                }
            ],
            [
                {
                    "id": "cycling-testrace-2027-etappe1",
                    "sport": "cycling",
                    "competition": "Test Race",
                    "round": "Etappe 1",
                    "start": "2027-08-01",
                    "timeConfirmed": False,
                    "location": "A",
                }
            ],
        ]
    )
    monkeypatch.setattr(fetch_cycling, "fetch_race", lambda api_base, race, today: next(yearly_events))

    fetch_cycling.main()
    fetch_cycling.main()

    snapshot = common.load_snapshot("cycling-testrace")
    assert [e["id"] for e in snapshot["events"]] == [
        "cycling-testrace-2026-etappe1",
        "cycling-testrace-2027-etappe1",
    ]
