import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

TOOLS_DIR = SCRIPTS_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


import pytest  # noqa: E402

# Synthetic partial-coverage league (scope != "full") -- since #12 every real
# league in config.json is scope: "full", so tests for the club-filter code
# paths (build_calendar_name()'s scope branch, league-token filtering) use
# this instead of depending on live config. Names make it unmistakably test
# data; the E2E counterpart lives in tests-e2e/incomplete-league.spec.js.
CLUB_FILTER_LEAGUE = {
    "id": "test-teilabdeckung",
    "competition": "Testliga Teilabdeckung",
    "gender": "men",
    "scope": "club-filter",
}
CLUB_FILTER_CLUB = {
    "id": "test-verein",
    "name": "Test-Verein",
    "shortName": "Test-Verein",
    "colorPalette": "blue",
    "teams": {"men": {"league": "Testliga Teilabdeckung"}},
}


@pytest.fixture
def club_filter_league():
    return dict(CLUB_FILTER_LEAGUE)


@pytest.fixture
def club_filter_club():
    return {**CLUB_FILTER_CLUB, "teams": {"men": dict(CLUB_FILTER_CLUB["teams"]["men"])}}
