import calendar_ics


def test_parse_selection_extracts_league_group_tokens():
    club_tokens, race_group_keys, league_group_keys = calendar_ics.parse_selection(
        "fc-bayern-muenchen:men,league:bl1:men,raceGroup:grand-tour-men"
    )
    assert club_tokens == {("fc-bayern-muenchen", "men")}
    assert race_group_keys == {"grand-tour-men"}
    assert league_group_keys == {"bl1:men"}


def test_resolve_league_club_tokens_returns_current_league_members():
    leagues = [{"id": "bl1", "competition": "Bundesliga", "gender": "men"}]
    clubs = [
        {"id": "fc-bayern-muenchen", "teams": {"men": {"league": "Bundesliga"}}},
        {"id": "borussia-dortmund", "teams": {"men": {"league": "Bundesliga"}}},
        {"id": "vfl-bochum", "teams": {"men": {"league": "2. Bundesliga"}}},
    ]

    tokens = calendar_ics.resolve_league_club_tokens({"bl1:men"}, leagues, clubs)

    assert tokens == {("fc-bayern-muenchen", "men"), ("borussia-dortmund", "men")}


def test_league_group_membership_resolved_fresh_not_from_a_snapshot():
    """Promotion/relegation: a club whose config-declared league changes must
    be picked up on the very next request -- there's no stored club-id list
    from selection time that would need to be kept in sync."""
    leagues = [{"id": "bl1", "competition": "Bundesliga", "gender": "men"}]
    clubs_before_promotion = [{"id": "vfl-bochum", "teams": {"men": {"league": "2. Bundesliga"}}}]
    clubs_after_promotion = [{"id": "vfl-bochum", "teams": {"men": {"league": "Bundesliga"}}}]

    assert calendar_ics.resolve_league_club_tokens({"bl1:men"}, leagues, clubs_before_promotion) == set()
    assert calendar_ics.resolve_league_club_tokens({"bl1:men"}, leagues, clubs_after_promotion) == {
        ("vfl-bochum", "men")
    }


def test_league_group_token_includes_cup_and_uefa_fixtures_of_member_clubs():
    """Membership is club-based (via homeTeamId/awayTeamId), never based on
    event['competition'] -- so a member club's DFB-Pokal/UEFA fixtures are
    included automatically, no special-casing for the cup/UEFA competition
    name needed."""
    leagues = [{"id": "bl1", "competition": "Bundesliga", "gender": "men"}]
    clubs = [{"id": "fc-bayern-muenchen", "teams": {"men": {"league": "Bundesliga"}}}]
    league_tokens = calendar_ics.resolve_league_club_tokens({"bl1:men"}, leagues, clubs)

    events = [
        {
            "id": "1",
            "sport": "football",
            "competition": "Bundesliga",
            "gender": "men",
            "homeTeamId": "fc-bayern-muenchen",
            "awayTeamId": "sv-werder-bremen",
            "start": "2026-08-01T18:30:00Z",
        },
        {
            "id": "2",
            "sport": "football",
            "competition": "DFB-Pokal",
            "gender": "men",
            "homeTeamId": "fc-bayern-muenchen",
            "awayTeamId": "sv-meppen",
            "start": "2026-08-02T18:30:00Z",
        },
        {
            "id": "3",
            "sport": "football",
            "competition": "UEFA Champions League",
            "gender": "men",
            "homeTeamId": "chelsea-fc",
            "awayTeamId": "fc-bayern-muenchen",
            "start": "2026-09-17T18:45:00Z",
        },
        {
            "id": "4",
            "sport": "football",
            "competition": "Bundesliga",
            "gender": "men",
            "homeTeamId": "vfl-bochum",
            "awayTeamId": "1-fc-koeln",
            "start": "2026-08-03T15:30:00Z",
        },
    ]

    filtered = calendar_ics.filter_events(events, league_tokens, set(), {})

    assert {e["id"] for e in filtered} == {"1", "2", "3"}


def test_build_response_body_league_only_club_gets_no_perspective_emoji(monkeypatch):
    """Mixing an individually selected club with a league group: the
    individually selected club keeps its emoji/color in the ICS title, a
    club covered only via the league group does not (see
    format_football_title() in scripts/common.py)."""
    clubs = [
        {
            "id": "fc-bayern-muenchen",
            "name": "FC Bayern München",
            "shortName": "FCB",
            "colorPalette": "red",
            "teams": {"men": {"league": "Bundesliga"}},
        },
        {
            "id": "sv-werder-bremen",
            "name": "SV Werder Bremen",
            "shortName": "SVW",
            "colorPalette": "green",
            "teams": {"men": {"league": "Bundesliga"}},
        },
    ]
    config = {
        "football": {"leagues": [{"id": "bl1", "competition": "Bundesliga", "gender": "men"}]},
        "cycling": {"races": []},
    }
    events = [
        {
            "id": "1",
            "sport": "football",
            "competition": "Bundesliga",
            "gender": "men",
            "homeTeamId": "fc-bayern-muenchen",
            "homeTeamName": "FC Bayern München",
            "awayTeamId": "sv-werder-bremen",
            "awayTeamName": "SV Werder Bremen",
            "start": "2026-08-01T18:30:00Z",
            "timeConfirmed": True,
        }
    ]

    monkeypatch.setattr(calendar_ics, "load_clubs", lambda: clubs)
    monkeypatch.setattr(calendar_ics, "load_config", lambda: config)
    monkeypatch.setattr(calendar_ics, "load_all_events", lambda: events)

    body = calendar_ics.build_response_body("fc-bayern-muenchen:men,league:bl1:men").decode("utf-8")

    assert "🟥" in body  # Bayern individually selected -> keeps its emoji
    assert "FCB" in body
    assert "SV Werder Bremen" in body  # Werder covered only via the league group -> plain name
    assert "🟩" not in body  # Werder's own square emoji must not appear
