from datetime import date
from pathlib import Path

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
