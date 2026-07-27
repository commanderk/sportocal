import fetch_cycling
import verify_race_sources as vrs

API_BASE = "https://en.wikipedia.org/w/api.php"


def test_guess_title_uses_standard_pattern():
    assert vrs.guess_title("Paris-Nice", 2026) == "2026 Paris-Nice"


def test_guess_title_returns_none_for_unclear_names():
    assert vrs.guess_title("Tour de France Femmes avec Zwift", 2026) is None


def test_classify_title_ok(monkeypatch):
    monkeypatch.setattr(fetch_cycling, "page_exists", lambda api_base, title: True)
    monkeypatch.setattr(fetch_cycling, "fetch_stage_table_section_index", lambda api_base, title: 2)
    monkeypatch.setattr(fetch_cycling, "fetch_wikitext_section", lambda api_base, title, section=None: "wikitext")
    monkeypatch.setattr(fetch_cycling, "parse_stage_table", lambda wikitext, year: [{"label": "Etappe 1"}])

    assert vrs.classify_title(API_BASE, "2026 Paris-Nice", 2026) == vrs.STATUS_OK


def test_classify_title_article_missing(monkeypatch):
    monkeypatch.setattr(fetch_cycling, "page_exists", lambda api_base, title: False)

    assert vrs.classify_title(API_BASE, "2026 Some Race", 2026) == vrs.STATUS_ARTICLE_MISSING


def test_classify_title_unparseable_no_section(monkeypatch):
    monkeypatch.setattr(fetch_cycling, "page_exists", lambda api_base, title: True)
    monkeypatch.setattr(fetch_cycling, "fetch_stage_table_section_index", lambda api_base, title: None)

    assert vrs.classify_title(API_BASE, "2026 Some Race", 2026) == vrs.STATUS_UNPARSEABLE


def test_classify_title_unparseable_empty_table(monkeypatch):
    monkeypatch.setattr(fetch_cycling, "page_exists", lambda api_base, title: True)
    monkeypatch.setattr(fetch_cycling, "fetch_stage_table_section_index", lambda api_base, title: 2)
    monkeypatch.setattr(fetch_cycling, "fetch_wikitext_section", lambda api_base, title, section=None: "wikitext")
    monkeypatch.setattr(fetch_cycling, "parse_stage_table", lambda wikitext, year: [])

    assert vrs.classify_title(API_BASE, "2026 Some Race", 2026) == vrs.STATUS_UNPARSEABLE


def test_verify_candidate_title_unclear_skips_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("should not make a network call for a title-unclear name")

    monkeypatch.setattr(fetch_cycling, "page_exists", fail)
    candidate = {"name": "Tour de France Femmes avec Zwift", "gender": "women", "tier": "grand-tour"}

    result = vrs.verify_candidate(API_BASE, candidate, [2026, 2027])

    assert result["results"] == {2026: vrs.STATUS_TITLE_UNCLEAR, 2027: vrs.STATUS_TITLE_UNCLEAR}
    assert result["recommendation"] == "Manuell"


def test_verify_candidate_recommends_scraper_only_if_both_years_ok(monkeypatch):
    monkeypatch.setattr(fetch_cycling, "page_exists", lambda api_base, title: True)
    monkeypatch.setattr(fetch_cycling, "fetch_stage_table_section_index", lambda api_base, title: 2)
    monkeypatch.setattr(fetch_cycling, "fetch_wikitext_section", lambda api_base, title, section=None: "wikitext")
    monkeypatch.setattr(fetch_cycling, "parse_stage_table", lambda wikitext, year: [{"label": "Etappe 1"}])
    candidate = {"name": "Paris-Nice", "gender": "men", "tier": "uci-worldtour"}

    result = vrs.verify_candidate(API_BASE, candidate, [2026, 2027])

    assert result["recommendation"] == "Scraper"


def test_verify_candidate_recommends_manuell_if_one_year_fails(monkeypatch):
    exists_by_year = {2026: True, 2027: False}
    monkeypatch.setattr(fetch_cycling, "page_exists", lambda api_base, title: exists_by_year[int(title[:4])])
    # 2026 has an article but no parseable stage table -- neither year is "ok",
    # so both branches are exercised without any real network call.
    monkeypatch.setattr(fetch_cycling, "fetch_stage_table_section_index", lambda api_base, title: None)
    candidate = {"name": "Paris-Nice", "gender": "men", "tier": "uci-worldtour"}

    result = vrs.verify_candidate(API_BASE, candidate, [2026, 2027])

    assert result["results"][2026] == vrs.STATUS_UNPARSEABLE
    assert result["results"][2027] == vrs.STATUS_ARTICLE_MISSING
    assert result["recommendation"] == "Manuell"
