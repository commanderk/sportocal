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


def test_league_group_label_appends_gender_when_name_does_not_say_it():
    assert calendar_ics.league_group_label({"competition": "Bundesliga", "gender": "men"}) == "Bundesliga (Männer)"
    assert calendar_ics.league_group_label({"competition": "3. Liga", "gender": "men"}) == "3. Liga (Männer)"


def test_league_group_label_leaves_name_unchanged_when_it_already_says_frauen():
    assert calendar_ics.league_group_label({"competition": "Frauen-Bundesliga", "gender": "women"}) == "Frauen-Bundesliga"


def test_league_group_label_suffixes_both_genders_of_a_shared_competition_name():
    assert calendar_ics.league_group_label({"competition": "DFB-Pokal", "gender": "men"}) == "DFB-Pokal (Männer)"
    assert calendar_ics.league_group_label({"competition": "DFB-Pokal", "gender": "women"}) == "DFB-Pokal (Frauen)"


def test_race_group_display_name_uses_speaking_group_name():
    assert calendar_ics.race_group_display_name("uci-worldtour-men") == "UCI WorldTour (Männer)"
    assert calendar_ics.race_group_display_name("grand-tour-women") == "Grand Tours (Frauen)"


def test_race_group_display_name_unknown_tier_or_key_returns_none():
    assert calendar_ics.race_group_display_name("unknown-tier-men") is None
    assert calendar_ics.race_group_display_name("no-gender-suffix") is None


def _club(cid, short_name, teams=None):
    club = {"id": cid, "shortName": short_name}
    if teams is not None:
        club["teams"] = teams
    return club


def _clubs_by_id(*clubs):
    return {c["id"]: c for c in clubs}


def test_build_calendar_name_no_items_falls_back_to_default():
    name = calendar_ics.build_calendar_name(set(), set(), set(), {}, [])
    assert name == calendar_ics.DEFAULT_CALENDAR_NAME


def test_build_calendar_name_single_club_uses_short_name():
    clubs_by_id = _clubs_by_id(_club("fc-bayern-muenchen", "FCB"))
    name = calendar_ics.build_calendar_name({("fc-bayern-muenchen", "men")}, set(), set(), clubs_by_id, [])
    assert name == "Sportocal – FCB"


def test_build_calendar_name_one_and_two_items_spelled_out_fully():
    clubs_by_id = _clubs_by_id(_club("a", "AAA"), _club("b", "BBB"))
    one = calendar_ics.build_calendar_name({("a", "men")}, set(), set(), clubs_by_id, [])
    two = calendar_ics.build_calendar_name({("a", "men"), ("b", "men")}, set(), set(), clubs_by_id, [])
    assert one == "Sportocal – AAA"
    assert two == "Sportocal – AAA, BBB"
    assert "u.a." not in two


def test_build_calendar_name_three_items_already_truncated_with_uebrigens():
    clubs_by_id = _clubs_by_id(_club("a", "AAA"), _club("b", "BBB"), _club("c", "CCC"))
    name = calendar_ics.build_calendar_name({("a", "men"), ("b", "men"), ("c", "men")}, set(), set(), clubs_by_id, [])
    assert name == "Sportocal – AAA, BBB, u.a."


def test_build_calendar_name_three_to_six_items_truncated_with_uebrigens():
    clubs_by_id = _clubs_by_id(*[_club(str(i), f"C{i}") for i in range(4)])
    name = calendar_ics.build_calendar_name({(str(i), "men") for i in range(4)}, set(), set(), clubs_by_id, [])
    assert name == "Sportocal – C0, C1, u.a."


def test_build_calendar_name_more_than_six_items_falls_back_to_default():
    clubs_by_id = _clubs_by_id(*[_club(str(i), f"C{i}") for i in range(7)])
    name = calendar_ics.build_calendar_name({(str(i), "men") for i in range(7)}, set(), set(), clubs_by_id, [])
    assert name == calendar_ics.DEFAULT_CALENDAR_NAME


def test_build_calendar_name_race_group_never_lists_individual_races():
    """A whole tier×gender subscription must collapse to one speaking group
    name, never expand to its (potentially dozens of) current member races."""
    name = calendar_ics.build_calendar_name(set(), set(), {"uci-worldtour-men"}, {}, [])
    assert name == "Sportocal – UCI WorldTour (Männer)"


def test_build_calendar_name_mixed_clubs_league_and_race_group_share_one_list_and_rule():
    clubs_by_id = _clubs_by_id(_club("fc-bayern-muenchen", "FCB"))
    leagues = [{"id": "bl1", "competition": "Bundesliga", "gender": "men"}]
    name = calendar_ics.build_calendar_name(
        {("fc-bayern-muenchen", "men")}, {"bl1:men"}, {"grand-tour-men"}, clubs_by_id, leagues
    )
    assert name == "Sportocal – Bundesliga (Männer), FCB, u.a."


def test_build_calendar_name_full_scope_league_still_collapses_to_group_label():
    clubs_by_id = _clubs_by_id(_club("fc-bayern-muenchen", "FCB"))
    leagues = [{"id": "bl1", "competition": "Bundesliga", "gender": "men", "scope": "full"}]
    name = calendar_ics.build_calendar_name(
        {("fc-bayern-muenchen", "men")}, {"bl1:men"}, set(), clubs_by_id, leagues
    )
    assert name == "Sportocal – Bundesliga (Männer), FCB"


def test_build_calendar_name_club_filter_league_expands_to_member_clubs_not_group_label():
    """Regionalliga Südwest only has Stuttgarter Kickers tracked in
    clubs.json (~18 real clubs exist) -- a league:rlsw-kickers:men token
    (which the frontend no longer produces for this league, but could still
    arrive via an old/hand-crafted URL, see league_group_label()'s
    docstring) must never render as "Regionalliga Südwest (Männer)", which
    would falsely claim the whole league was selected. It should list the
    actually-tracked member club(s) by name instead, same as if they'd been
    selected individually."""
    league = {"id": "rlsw-kickers", "competition": "Regionalliga Südwest", "gender": "men", "scope": "club-filter"}
    kickers = _club("stuttgarter-kickers", "Kickers", teams={"men": {"league": "Regionalliga Südwest"}})
    clubs_by_id = _clubs_by_id(kickers)
    name = calendar_ics.build_calendar_name(set(), {"rlsw-kickers:men"}, set(), clubs_by_id, [league])
    assert name == "Sportocal – Kickers"
    assert "Alle Vereine" not in name
    assert "Regionalliga" not in name


def test_build_calendar_name_club_filter_league_defaults_scope_to_full_when_absent():
    """Backward compatibility: a league dict without a `scope` key at all
    (e.g. an older config.json entry, or a test fixture predating this
    field) must behave like scope: "full", not silently expand/break."""
    clubs_by_id = _clubs_by_id(_club("fc-bayern-muenchen", "FCB"))
    leagues = [{"id": "bl1", "competition": "Bundesliga", "gender": "men"}]
    name = calendar_ics.build_calendar_name(set(), {"bl1:men"}, set(), clubs_by_id, leagues)
    assert name == "Sportocal – Bundesliga (Männer)"


def test_build_calendar_name_unresolvable_keys_are_ignored_not_counted():
    clubs_by_id = _clubs_by_id(_club("fc-bayern-muenchen", "FCB"))
    name = calendar_ics.build_calendar_name(
        {("fc-bayern-muenchen", "men")}, {"unknown-league-key"}, {"unknown-tier-men"}, clubs_by_id, []
    )
    assert name == "Sportocal – FCB"
