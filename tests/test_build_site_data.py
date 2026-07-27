import build_site_data


def test_build_races_payload_includes_gender_and_tier():
    config = {
        "cycling": {
            "races": [
                {"id": "tour-de-france", "name": "Tour de France", "type": "stage-race", "gender": "men", "tier": "grand-tour"},
            ]
        }
    }

    races = build_site_data.build_races_payload(config)

    assert races == [{"id": "tour-de-france", "name": "Tour de France", "gender": "men", "tier": "grand-tour"}]


def test_build_races_payload_includes_country_only_when_present():
    config = {
        "cycling": {
            "races": [
                {"id": "deutschland-tour", "name": "Deutschland Tour", "type": "stage-race", "gender": "men", "tier": "uci-proseries", "country": "DE"},
                {"id": "tour-de-france", "name": "Tour de France", "type": "stage-race", "gender": "men", "tier": "grand-tour"},
            ]
        }
    }

    races = build_site_data.build_races_payload(config)

    assert races[0]["country"] == "DE"
    assert "country" not in races[1]
