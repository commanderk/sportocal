from datetime import datetime, timezone
from pathlib import Path

import common
import fetch_football

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


LEAGUE_CFG = {
    "id": "ffb2",
    "competition": "2. Frauen-Bundesliga",
    "gender": "women",
    "scope": "full",
    "roundFormat": "spieltag",
}

# Minimal club table covering just the fixture's 6 teams -- kept local to
# this test rather than loading the real config/clubs.json, so the test
# doesn't drift if the real file's content changes. Two of these (Ingolstadt,
# Turbine Potsdam) only resolve via the dfbDatencenterTeamName override, the
# other four resolve through common.build_club_indexes()'s normal name match.
CLUBS = [
    {
        "id": "fc-ingolstadt-04",
        "name": "FC Ingolstadt 04",
        "teams": {"women": {"dfbDatencenterTeamName": "FC Ingolstadt"}},
    },
    {
        "id": "1-ffc-turbine-potsdam",
        "name": "1. FFC Turbine Potsdam",
        "teams": {"women": {"dfbDatencenterTeamName": "Turbine Potsdam"}},
    },
    {"id": "sgs-essen", "name": "SGS Essen", "teams": {"women": {}}},
    {"id": "eintracht-frankfurt-ii", "name": "Eintracht Frankfurt II", "teams": {"women": {}}},
    {"id": "vfl-bochum", "name": "VfL Bochum", "teams": {"women": {}}},
    {"id": "hertha-bsc", "name": "Hertha BSC", "teams": {"women": {}}},
]

# Only VfL Bochum has a confirmed venue in this test double -- matches
# config/stadiums.json's real "vfl-bochum" entry, deliberately left out of
# the others so tests can distinguish "resolved club with a stadium" from
# "resolved club without one" from "unresolved club".
STADIUMS = {"vfl-bochum": "Lohrheidestadion, Bochum"}


def build_name_to_id() -> dict[str, str]:
    _, name_to_id = common.build_club_indexes(CLUBS)
    return {**name_to_id, **fetch_football.dfb_datencenter_name_overrides(CLUBS)}


# --- parse_dfb_datencenter_date(): the two date formats the site uses ----


def test_parse_dfb_datencenter_date_confirmed_time_converts_berlin_to_utc():
    # Sonntag 14:00 in August is CEST (UTC+2) -> 12:00 UTC.
    start, confirmed = fetch_football.parse_dfb_datencenter_date("Sonntag, 02.08.2026 14:00 Uhr")
    assert start == "2026-08-02T12:00:00Z"
    assert confirmed is True


def test_parse_dfb_datencenter_date_window_borrows_year_from_end_date():
    """The provisional window omits the start date's year ("02.10. ~
    04.10.2026") -- only the window's *start* date is used, per the same
    "don't guess a time we don't have" rule as OpenLigaDB's 00:00 placeholder
    handling in build_event()."""
    start, confirmed = fetch_football.parse_dfb_datencenter_date("*02.10. ~ 04.10.2026*")
    assert start == "2026-10-02"
    assert confirmed is False


def test_parse_dfb_datencenter_date_window_with_explicit_start_year():
    start, confirmed = fetch_football.parse_dfb_datencenter_date("02.10.2026 ~ 04.10.2026")
    assert start == "2026-10-02"
    assert confirmed is False


def test_parse_dfb_datencenter_date_unparseable_raises():
    import pytest

    with pytest.raises(ValueError):
        fetch_football.parse_dfb_datencenter_date("Termin folgt")


# --- dfb_season_start_year(): season-slug cutoff --------------------------


def test_dfb_season_start_year_in_season():
    assert fetch_football.dfb_season_start_year(datetime(2026, 8, 24, tzinfo=timezone.utc)) == 2026


def test_dfb_season_start_year_before_july_is_still_previous_season():
    assert fetch_football.dfb_season_start_year(datetime(2027, 3, 1, tzinfo=timezone.utc)) == 2026


def test_dfb_season_start_year_july_already_counts_as_new_season():
    assert fetch_football.dfb_season_start_year(datetime(2026, 7, 1, tzinfo=timezone.utc)) == 2026


# --- dfb_datencenter_name_overrides() --------------------------------------


def test_dfb_datencenter_name_overrides_only_includes_clubs_with_the_field():
    overrides = fetch_football.dfb_datencenter_name_overrides(CLUBS)
    assert overrides == {"FC Ingolstadt": "fc-ingolstadt-04", "Turbine Potsdam": "1-ffc-turbine-potsdam"}


# --- gender_scoped_stadiums(): a club id can mean two different genders' --


def test_gender_scoped_stadiums_keeps_a_club_with_a_matching_gender_team():
    stadiums = {"vfl-bochum": "Lohrheidestadion, Bochum"}
    clubs = [{"id": "vfl-bochum", "teams": {"women": {}}}]
    assert fetch_football.gender_scoped_stadiums(stadiums, clubs, "women") == stadiums


def test_gender_scoped_stadiums_drops_a_club_without_a_matching_gender_team():
    """The exact bug this guards against: "eintracht-frankfurt-ii" is
    tracked here only for its ffb2 *women's* side, but resolve_club_id() is
    name-only and gender-blind, so the same id would also (mis)match an
    unrelated men's "Eintracht Frankfurt II" reserve side that shows up as
    an opponent in Regionalliga Suedwest -- the venue must not leak there."""
    stadiums = {"eintracht-frankfurt-ii": "Sportanlage Riederwald, Frankfurt am Main"}
    clubs = [{"id": "eintracht-frankfurt-ii", "teams": {"women": {}}}]  # no "men" team
    assert fetch_football.gender_scoped_stadiums(stadiums, clubs, "men") == {}


# --- parse_dfb_datencenter_page(): full-page parsing -----------------------


def test_parse_dfb_datencenter_page_parses_every_match_in_the_fixture():
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, build_name_to_id(), STADIUMS)

    assert [e["id"] for e in events] == [
        "football-ffb2-2424700",
        "football-ffb2-2424705",
        "football-ffb2-2424899",
    ]


def test_parse_dfb_datencenter_page_round_comes_from_result_url_not_header():
    """Matchday 9 in the fixture's 3rd match has no matchday header nearby at
    all (this fixture is trimmed to bare match rows) -- round must still come
    out right because it's read from the result-link URL, not a section
    heading."""
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, build_name_to_id(), STADIUMS)

    assert [e["round"] for e in events] == ["Spieltag 1", "Spieltag 1", "Spieltag 9"]


def test_parse_dfb_datencenter_page_confirmed_and_window_dates_both_present():
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, build_name_to_id(), STADIUMS)

    assert events[0]["start"] == "2026-08-02T12:00:00Z"
    assert events[0]["timeConfirmed"] is True
    assert events[2]["start"] == "2026-10-02"
    assert events[2]["timeConfirmed"] is False


def test_parse_dfb_datencenter_page_resolves_club_ids_via_name_override():
    """FC Ingolstadt / Turbine Potsdam only resolve through the
    dfbDatencenterTeamName override -- see config/clubs.json."""
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, build_name_to_id(), STADIUMS)

    assert events[0]["homeTeamId"] == "fc-ingolstadt-04"
    assert events[0]["awayTeamId"] == "1-ffc-turbine-potsdam"


def test_parse_dfb_datencenter_page_resolves_club_ids_via_plain_name_match():
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, build_name_to_id(), STADIUMS)

    assert events[1]["homeTeamId"] == "sgs-essen"
    assert events[1]["awayTeamId"] == "eintracht-frankfurt-ii"
    assert events[2]["homeTeamId"] == "vfl-bochum"
    assert events[2]["awayTeamId"] == "hertha-bsc"


def test_parse_dfb_datencenter_page_captures_team_logos():
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, build_name_to_id(), STADIUMS)

    assert events[0]["homeTeamLogo"].endswith("original_FC_Ingolstadt_Logo.jpg")
    assert events[0]["awayTeamLogo"].endswith("original_Turbine_Potsdam_Logo.jpg")


def test_parse_dfb_datencenter_page_unresolved_club_name_gives_null_id_not_crash():
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    # Empty name_to_id -- nothing resolves, but parsing must still succeed.
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, {}, STADIUMS)

    assert len(events) == 3
    assert all(e["homeTeamId"] is None and e["awayTeamId"] is None for e in events)


def test_parse_dfb_datencenter_page_skips_one_malformed_match_without_dropping_the_rest():
    """A single row missing an expected field (markup drift, mid-scrape
    truncation, ...) must not take down the whole page -- mirrors the
    single-bad-source resilience rule main() applies at the league level."""
    good_match = """
      <div class="c-MatchTable-row">
        <div class="c-MatchTable-col c-MatchTable-info c-MatchTable-info--home" id="match_1">
          <div class="c-MatchTable-description">
            <p class="dfb-Paragraph dfb-Paragraph--small">Sonntag, 02.08.2026 14:00 Uhr</p>
          </div>
        </div>
        <div class="c-MatchTable-col c-MatchTable-team c-MatchTable-team--home" data-team-kind="club">
          <a href="https://datencenter.dfb.de/x">SGS Essen</a>
        </div>
        <div class="c-MatchTable-col c-MatchTable-center">
          <div class="c-MatchTable-score">
            <a href="https://datencenter.dfb.de/datencenter/2-frauen-bundesliga/2026-2027/1-spieltag/sgs-essen-x-1">- : -</a>
          </div>
        </div>
        <div class="c-MatchTable-col c-MatchTable-team c-MatchTable-team--away" data-team-kind="club">
          <a href="https://datencenter.dfb.de/x">Hertha BSC</a>
        </div>
      </div>
    """
    broken_match = """
      <div class="c-MatchTable-row">
        <div class="c-MatchTable-col c-MatchTable-info c-MatchTable-info--home" id="match_2">
          <div class="c-MatchTable-description">
            <p class="dfb-Paragraph dfb-Paragraph--small">Termin folgt</p>
          </div>
        </div>
        <div class="c-MatchTable-col c-MatchTable-team c-MatchTable-team--home" data-team-kind="club">
          <a href="https://datencenter.dfb.de/x">VfL Bochum</a>
        </div>
      </div>
    """
    events = fetch_football.parse_dfb_datencenter_page(
        good_match + broken_match, LEAGUE_CFG, build_name_to_id(), STADIUMS
    )

    assert len(events) == 1
    assert events[0]["id"] == "football-ffb2-1"


# --- parse_dfb_datencenter_page(): location fallback via stadiums.json ---


def test_parse_dfb_datencenter_page_location_from_home_team_stadium():
    """3rd fixture match: home=VfL Bochum, which has a STADIUMS entry."""
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, build_name_to_id(), STADIUMS)

    assert events[2]["homeTeamName"] == "VfL Bochum"
    assert events[2]["location"] == "Lohrheidestadion, Bochum"


def test_parse_dfb_datencenter_page_location_none_when_home_club_has_no_stadium_entry():
    """1st fixture match: home=FC Ingolstadt, resolved to a club id but that
    id has no entry in STADIUMS -- location stays None, not a KeyError."""
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, build_name_to_id(), STADIUMS)

    assert events[0]["homeTeamName"] == "FC Ingolstadt"
    assert events[0]["location"] is None


def test_parse_dfb_datencenter_page_location_ignores_away_teams_stadium():
    """A stadium entry for the *away* side must never leak into location --
    only the home team hosts. Swap the roles: give Hertha (away in match 3)
    a stadium entry the away side must not pick up."""
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    stadiums = {"hertha-bsc": "Stadion auf dem Wurfplatz, Berlin"}
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, build_name_to_id(), stadiums)

    assert events[2]["awayTeamName"] == "Hertha BSC"
    assert events[2]["location"] is None


def test_parse_dfb_datencenter_page_location_none_when_home_team_unresolved():
    html_text = load_fixture("dfb_datencenter_ffb2_fragment.html")
    events = fetch_football.parse_dfb_datencenter_page(html_text, LEAGUE_CFG, {}, STADIUMS)

    assert all(e["location"] is None for e in events)


# --- parse_dfb_datencenter_page() reused for a team-page shape (Regionalliga
# Suedwest / Stuttgarter Kickers), not just a full-season overview page ----


def test_parse_dfb_datencenter_page_works_for_a_single_team_page_too():
    """Same function, different DFB Datencenter page shape: a team's own
    page (".../teams/stuttgarter-kickers") instead of a full-season
    overview -- verifies the function is genuinely reusable across both
    ffb2 (full league) and Regionalliga Suedwest (single club) as intended,
    not accidentally season-page-specific."""
    html_text = load_fixture("dfb_datencenter_kickers_fragment.html")
    league_cfg = {"id": "rlsw-kickers", "competition": "Regionalliga Südwest", "gender": "men"}
    kickers_clubs = [{"id": "stuttgarter-kickers", "name": "Stuttgarter Kickers", "teams": {"men": {}}}]
    _, name_to_id = common.build_club_indexes(kickers_clubs)
    stadiums = {"stuttgarter-kickers": "GAZi-Stadion auf der Waldau, Stuttgart"}

    events = fetch_football.parse_dfb_datencenter_page(html_text, league_cfg, name_to_id, stadiums)

    assert [e["id"] for e in events] == ["football-rlsw-kickers-2426295", "football-rlsw-kickers-2426306"]
    assert [e["round"] for e in events] == ["Spieltag 1", "Spieltag 2"]
    # Match 1: Kickers at home -> their own stadium. Match 2: Kickers away
    # (Eintracht Frankfurt II host) -> no stadium entry for the opponent,
    # location stays None rather than guessing.
    assert events[0]["location"] == "GAZi-Stadion auf der Waldau, Stuttgart"
    assert events[1]["location"] is None
    assert events[0]["homeTeamId"] == "stuttgarter-kickers"
    assert events[1]["awayTeamId"] == "stuttgarter-kickers"


def test_fetch_dfb_datencenter_entry_gender_scopes_stadiums_before_parsing(monkeypatch):
    """End-to-end regression test for the venue leak found via the manual
    stichprobe (Spieltag 2, Eintracht Frankfurt II - Stuttgarter Kickers):
    a stadiums.json entry researched for ffb2's *women's* Eintracht Frankfurt
    II must not surface in this *men's* Regionalliga Suedwest fixture just
    because both happen to resolve to the same club id by name."""
    monkeypatch.setattr(
        fetch_football, "http_get_text", lambda url: load_fixture("dfb_datencenter_kickers_fragment.html")
    )
    league_cfg = {"id": "rlsw-kickers", "competition": "Regionalliga Südwest", "gender": "men"}
    clubs = [
        {"id": "stuttgarter-kickers", "name": "Stuttgarter Kickers", "teams": {"men": {}}},
        {"id": "eintracht-frankfurt-ii", "name": "Eintracht Frankfurt II", "teams": {"women": {}}},
    ]
    _, name_to_id = common.build_club_indexes(clubs)
    stadiums = {
        "stuttgarter-kickers": "GAZi-Stadion auf der Waldau, Stuttgart",
        "eintracht-frankfurt-ii": "Sportanlage Riederwald, Frankfurt am Main",  # the women's venue
    }
    primary_source = {"source": "dfb-datencenter", "url": "https://example.invalid/{season}-{seasonEnd}"}
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)

    events = fetch_football.fetch_dfb_datencenter_entry(league_cfg, primary_source, now, clubs, name_to_id, stadiums)

    assert events[1]["homeTeamName"] == "Eintracht Frankfurt II"
    assert events[1]["location"] is None  # not the leaked women's-team venue
    assert events[0]["location"] == "GAZi-Stadion auf der Waldau, Stuttgart"  # Kickers unaffected, has a men's team


# --- fetch_dfb_datencenter_entry() / fetch_entry() dispatch ---------------


def test_fetch_dfb_datencenter_entry_builds_url_from_now_and_returns_events(monkeypatch):
    captured_urls = []

    def fake_http_get_text(url):
        captured_urls.append(url)
        return load_fixture("dfb_datencenter_ffb2_fragment.html")

    monkeypatch.setattr(fetch_football, "http_get_text", fake_http_get_text)

    primary_source = {
        "source": "dfb-datencenter",
        "url": "https://datencenter.dfb.de/competitions/2-frauen-bundesliga/seasons/{season}-{seasonEnd}",
    }
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)

    events = fetch_football.fetch_dfb_datencenter_entry(
        LEAGUE_CFG, primary_source, now, CLUBS, build_name_to_id(), STADIUMS
    )

    assert captured_urls == ["https://datencenter.dfb.de/competitions/2-frauen-bundesliga/seasons/2026-2027"]
    assert len(events) == 3


def test_fetch_dfb_datencenter_entry_threads_stadiums_through_to_the_parser(monkeypatch):
    monkeypatch.setattr(fetch_football, "http_get_text", lambda url: load_fixture("dfb_datencenter_ffb2_fragment.html"))
    primary_source = {"source": "dfb-datencenter", "url": "https://example.invalid/{season}-{seasonEnd}"}
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)

    events = fetch_football.fetch_dfb_datencenter_entry(
        LEAGUE_CFG, primary_source, now, CLUBS, build_name_to_id(), STADIUMS
    )

    assert events[2]["location"] == "Lohrheidestadion, Bochum"


def test_fetch_dfb_datencenter_entry_returns_none_on_http_error(monkeypatch):
    def fake_http_get_text(url):
        raise RuntimeError("boom")

    monkeypatch.setattr(fetch_football, "http_get_text", fake_http_get_text)
    primary_source = {"source": "dfb-datencenter", "url": "https://example.invalid/{season}-{seasonEnd}"}
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)

    events = fetch_football.fetch_dfb_datencenter_entry(
        LEAGUE_CFG, primary_source, now, CLUBS, build_name_to_id(), STADIUMS
    )

    assert events is None


def test_fetch_dfb_datencenter_entry_returns_none_when_page_has_no_matches(monkeypatch):
    monkeypatch.setattr(fetch_football, "http_get_text", lambda url: "<html><body>no matches here</body></html>")
    primary_source = {"source": "dfb-datencenter", "url": "https://example.invalid/{season}-{seasonEnd}"}
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)

    events = fetch_football.fetch_dfb_datencenter_entry(
        LEAGUE_CFG, primary_source, now, CLUBS, build_name_to_id(), STADIUMS
    )

    assert events is None


def test_fetch_entry_dfb_datencenter_source_never_touches_openligadb(monkeypatch):
    """A primarySource league is a full replacement, not a fallback-on-miss
    -- OpenLigaDB must never even be queried, and get_leagues() (the lazy
    /getavailableleagues gate) must never even be called."""

    def boom(*args, **kwargs):
        raise AssertionError("OpenLigaDB must not be queried for a primarySource league")

    monkeypatch.setattr(fetch_football, "find_league_candidates", boom)
    monkeypatch.setattr(fetch_football, "fetch_league_matches", boom)
    monkeypatch.setattr(fetch_football, "http_get_text", lambda url: load_fixture("dfb_datencenter_ffb2_fragment.html"))

    league_cfg = {
        **LEAGUE_CFG,
        "primarySource": {
            "source": "dfb-datencenter",
            "url": "https://datencenter.dfb.de/competitions/2-frauen-bundesliga/seasons/{season}-{seasonEnd}",
        },
    }
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)

    events = fetch_football.fetch_entry({}, boom, league_cfg, now, CLUBS, build_name_to_id(), STADIUMS)

    assert len(events) == 3


def test_fetch_entry_without_primary_source_still_uses_openligadb_path(monkeypatch):
    """Sanity check that the new dispatch doesn't break the existing
    OpenLigaDB-backed leagues (bl1 etc.), which have no primarySource key."""
    monkeypatch.setattr(fetch_football, "find_league_candidates", lambda leagues, league_cfg, current_year: [])

    league_cfg = {**LEAGUE_CFG, "id": "bl1", "leagueNameKeywords": [], "knownGap": None}
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)

    events = fetch_football.fetch_entry({}, lambda: [], league_cfg, now, CLUBS, build_name_to_id(), STADIUMS)

    assert events is None  # no candidates, no fallback configured -> None, not a crash


def test_fetch_entry_without_primary_source_propagates_get_leagues_failure(monkeypatch):
    """When get_leagues() fails (OpenLigaDB down), a non-primarySource
    league's fetch_entry() must let that exception surface -- main() is what
    turns it into a per-league warn()+skip, not fetch_entry() itself."""

    def failing_get_leagues():
        raise RuntimeError("getavailableleagues nicht erreichbar")

    league_cfg = {**LEAGUE_CFG, "id": "bl1", "leagueNameKeywords": [], "knownGap": None}
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)

    import pytest

    with pytest.raises(RuntimeError, match="getavailableleagues nicht erreichbar"):
        fetch_football.fetch_entry({}, failing_get_leagues, league_cfg, now, CLUBS, build_name_to_id(), STADIUMS)


# --- make_leagues_getter(): lazy + memoized /getavailableleagues ---------


def _raise_getavailableleagues_down(url):
    raise RuntimeError("getavailableleagues down")


def test_make_leagues_getter_does_not_hit_the_network_until_called(monkeypatch):
    monkeypatch.setattr(fetch_football, "http_get_json", _raise_getavailableleagues_down)
    # Building the getter alone must not raise -- only calling it does.
    fetch_football.make_leagues_getter({"football": {"apiBase": "https://api.example.invalid"}})


def test_make_leagues_getter_memoizes_a_successful_result(monkeypatch):
    calls = []

    def fake_http_get_json(url):
        calls.append(url)
        return [{"leagueName": "x"}]

    monkeypatch.setattr(fetch_football, "http_get_json", fake_http_get_json)
    get_leagues = fetch_football.make_leagues_getter({"football": {"apiBase": "https://api.example.invalid"}})

    assert get_leagues() == [{"leagueName": "x"}]
    assert get_leagues() == [{"leagueName": "x"}]
    assert len(calls) == 1  # one network call, reused across every subsequent get_leagues() call


def test_make_leagues_getter_memoizes_a_failure_without_retrying(monkeypatch):
    import pytest

    calls = []

    def fake_http_get_json(url):
        calls.append(url)
        raise RuntimeError("down")

    monkeypatch.setattr(fetch_football, "http_get_json", fake_http_get_json)
    get_leagues = fetch_football.make_leagues_getter({"football": {"apiBase": "https://api.example.invalid"}})

    with pytest.raises(RuntimeError):
        get_leagues()
    with pytest.raises(RuntimeError):
        get_leagues()

    assert len(calls) == 1  # the failure itself is cached, not just the success case


# --- main(): primarySource leagues survive a dead getavailableleagues ----


def test_main_lets_primary_source_leagues_run_when_getavailableleagues_is_down(monkeypatch, tmp_path):
    """The scenario this whole change exists for: OpenLigaDB's
    /getavailableleagues is down, but ffb2 (primarySource) never needed it
    in the first place and must still get its snapshot written; a
    non-primarySource league (bl1) must be skipped with a warning instead of
    aborting the whole run."""
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_football, "http_get_json", _raise_getavailableleagues_down)
    monkeypatch.setattr(fetch_football, "http_get_text", lambda url: load_fixture("dfb_datencenter_ffb2_fragment.html"))

    test_config = {
        "football": {
            "apiBase": "https://api.openligadb.de",
            "leagues": [
                {
                    **LEAGUE_CFG,
                    "primarySource": {
                        "source": "dfb-datencenter",
                        "url": "https://datencenter.dfb.de/competitions/2-frauen-bundesliga/seasons/{season}-{seasonEnd}",
                    },
                },
                {**LEAGUE_CFG, "id": "bl1", "leagueNameKeywords": [], "knownGap": None},
            ],
        }
    }
    monkeypatch.setattr(fetch_football, "load_config", lambda: test_config)

    fetch_football.main()

    ffb2_snapshot = common.load_snapshot("football-ffb2")
    assert len(ffb2_snapshot["events"]) == 3  # primarySource league unaffected by the dead endpoint

    bl1_snapshot = common.load_snapshot("football-bl1")
    assert bl1_snapshot == {"events": [], "lastChecked": None}  # never written -- skipped, not crashed
