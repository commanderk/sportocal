from datetime import datetime, timezone

import common


def test_reminder_trigger_0800_berlin_in_winter_is_0700_utc():
    """CET (UTC+1) applies outside DST."""
    trigger = common.reminder_trigger_utc({"start": "2026-01-15"})
    assert trigger == datetime(2026, 1, 15, 7, 0, tzinfo=timezone.utc)


def test_reminder_trigger_0800_berlin_in_summer_is_0600_utc():
    """CEST (UTC+2) applies during DST."""
    trigger = common.reminder_trigger_utc({"start": "2026-07-15"})
    assert trigger == datetime(2026, 7, 15, 6, 0, tzinfo=timezone.utc)


def test_reminder_trigger_dst_spring_boundary():
    """2026-03-29 is the last Sunday of March -- Europe/Berlin springs
    forward to CEST at 02:00 local that day, so 08:00 local is already
    CEST (UTC+2) on the transition date itself, while the day before is
    still CET (UTC+1)."""
    before = common.reminder_trigger_utc({"start": "2026-03-28"})
    on_transition_day = common.reminder_trigger_utc({"start": "2026-03-29"})
    assert before == datetime(2026, 3, 28, 7, 0, tzinfo=timezone.utc)
    assert on_transition_day == datetime(2026, 3, 29, 6, 0, tzinfo=timezone.utc)


def test_reminder_trigger_dst_autumn_boundary():
    """2026-10-25 is the last Sunday of October -- Europe/Berlin falls back
    to CET at 03:00 CEST local that day, so 08:00 local is already CET
    (UTC+1) on the transition date itself, while the day before is still
    CEST (UTC+2)."""
    before = common.reminder_trigger_utc({"start": "2026-10-24"})
    on_transition_day = common.reminder_trigger_utc({"start": "2026-10-25"})
    assert before == datetime(2026, 10, 24, 6, 0, tzinfo=timezone.utc)
    assert on_transition_day == datetime(2026, 10, 25, 7, 0, tzinfo=timezone.utc)


def test_reminder_trigger_same_day_for_all_day_and_timed_variant():
    """A bare date and a full ISO timestamp for the same calendar day must
    produce the same reminder trigger -- the absolute trigger is anchored to
    "the event's day", not whatever DTSTART time happens to be."""
    all_day = common.reminder_trigger_utc({"start": "2026-07-15"})
    timed = common.reminder_trigger_utc({"start": "2026-07-15T18:30:00Z"})
    assert all_day == timed


def test_normalize_stage_type_strips_stage_suffix_case_insensitively():
    assert common.normalize_stage_type("Mountain stage") == "Mountain"
    assert common.normalize_stage_type("Mountain STAGE") == "Mountain"
    assert common.normalize_stage_type("Individual time trial") == "Individual time trial"


def test_normalize_stage_type_unrecognized_or_missing_returns_none():
    assert common.normalize_stage_type(None) is None
    assert common.normalize_stage_type("") is None
    assert common.normalize_stage_type("Cobbled climb") is None


def _cycling_event(**overrides):
    event = {
        "id": "cycling-test-1",
        "sport": "cycling",
        "competition": "Vuelta a España",
        "round": "Etappe 18",
        "start": "2026-09-10T13:00:00Z",
        "timeConfirmed": True,
        "gender": "men",
        "route": {"start": "A", "finish": "B", "type": "Individual time trial"},
    }
    event.update(overrides)
    return event


def test_build_vevent_includes_valarm_with_absolute_trigger():
    lines = common.build_vevent(_cycling_event(), {})
    assert "BEGIN:VALARM" in lines
    assert "ACTION:DISPLAY" in lines
    assert any(line.startswith("TRIGGER;VALUE=DATE-TIME:") for line in lines)
    assert not any(line.startswith("TRIGGER;VALUE=DURATION") for line in lines)
    trigger_line = next(line for line in lines if line.startswith("TRIGGER;VALUE=DATE-TIME:"))
    expected = common.reminder_trigger_utc(_cycling_event())
    assert trigger_line == f"TRIGGER;VALUE=DATE-TIME:{expected.strftime('%Y%m%dT%H%M%SZ')}"


def test_build_vevent_description_includes_translated_stage_type():
    lines = common.build_vevent(_cycling_event(), {})
    description_line = next(line for line in lines if line.startswith("DESCRIPTION:"))
    assert "Etappe: Einzelzeitfahren" in description_line


def test_build_vevent_description_omits_stage_type_line_when_route_type_missing():
    """One-day races typically have no route.type -- no 'Etappe: ...' line
    should be invented for them."""
    event = _cycling_event(route={"start": "A", "finish": "B"})
    lines = common.build_vevent(event, {})
    description_line = next(line for line in lines if line.startswith("DESCRIPTION:"))
    assert "Etappe:" not in description_line


def _football_event(**overrides):
    event = {
        "id": "football-test-1",
        "sport": "football",
        "competition": "Bundesliga",
        "round": "Spieltag 1",
        "gender": "men",
        "start": "2026-08-01T18:30:00Z",
        "timeConfirmed": True,
        "homeTeamName": "FC Bayern München",
        "awayTeamName": "SV Werder Bremen",
        "location": "Allianz Arena, München",
    }
    event.update(overrides)
    return event


def test_event_location_football_uses_location_field_directly():
    assert common.event_location(_football_event()) == "Allianz Arena, München"


def test_event_location_football_missing_returns_none():
    assert common.event_location(_football_event(location=None)) is None


def test_event_location_cycling_uses_route_finish_not_the_arrow_string():
    event = _cycling_event(location="El Puerto de Santa María → Jerez de la Frontera")
    assert common.event_location(event) == "B"  # route.finish from _cycling_event()'s default route


def test_event_location_cycling_missing_route_finish_returns_none():
    """A manually entered one-day race can have route.finish blank pending
    confirmation -- LOCATION must be omitted, not fall back to the raw
    "start → finish" location string."""
    event = _cycling_event(route={"start": "A", "finish": "", "type": "Individual time trial"})
    assert common.event_location(event) is None


def test_build_vevent_location_line_uses_event_location_helper():
    lines = common.build_vevent(_football_event(), {})
    # escape_text() escapes the comma per RFC 5545.
    assert "LOCATION:Allianz Arena\\, München" in lines

    lines = common.build_vevent(_football_event(location=None), {})
    assert not any(line.startswith("LOCATION:") for line in lines)


def test_build_vevent_includes_url_property():
    lines = common.build_vevent(_football_event(), {})
    assert "URL:https://sportocal.de" in lines


def test_build_vevent_description_ends_with_sportocal_footer():
    lines = common.build_vevent(_cycling_event(), {})
    description_line = next(line for line in lines if line.startswith("DESCRIPTION:"))
    assert description_line.endswith("— via sportocal.de")
