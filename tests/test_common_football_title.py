import common


def _clubs_by_id():
    return {
        "fc-bayern-muenchen": {"id": "fc-bayern-muenchen", "shortName": "FCB", "colorPalette": "red"},
        "sv-werder-bremen": {"id": "sv-werder-bremen", "shortName": "SVW", "colorPalette": "green"},
    }


def _event():
    return {
        "sport": "football",
        "competition": "Bundesliga",
        "gender": "men",
        "homeTeamId": "fc-bayern-muenchen",
        "homeTeamName": "FC Bayern München",
        "awayTeamId": "sv-werder-bremen",
        "awayTeamName": "SV Werder Bremen",
    }


def test_perspective_none_gives_both_sides_an_emoji():
    title = common.format_football_title(_event(), _clubs_by_id(), perspective_club_ids=None)
    assert title.startswith("🟥 FCB - 🟩 SVW")


def test_perspective_set_with_one_club_gives_only_that_side_an_emoji():
    title = common.format_football_title(_event(), _clubs_by_id(), perspective_club_ids={"fc-bayern-muenchen"})
    assert title.startswith("🟥 FCB - SV Werder Bremen")


def test_perspective_empty_set_gives_neither_side_an_emoji():
    """A league-only-covered game (see api/calendar_ics.py's league:<id>:<gender>
    token) passes an *empty* (not None) perspective_club_ids set -- both
    sides must fall back to the plain raw team name, same as the web view's
    unbadged style, not the emoji/color treatment reserved for individually
    selected clubs."""
    title = common.format_football_title(_event(), _clubs_by_id(), perspective_club_ids=set())
    assert title.startswith("FC Bayern München - SV Werder Bremen")
    assert "🟥" not in title
    assert "🟩" not in title
