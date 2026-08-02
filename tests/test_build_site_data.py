import build_site_data


def race(id_, name, gender, tier, country=None, short=None):
    entry = {
        "id": id_,
        "name": name,
        "shortName": short or id_[:3].upper(),
        "type": "stage-race",
        "gender": gender,
        "tier": tier,
    }
    if country:
        entry["country"] = country
    return entry


def test_single_gender_tier_gets_no_gender_suffix():
    config = {
        "cycling": {
            "races": [
                race("deutschland-tour", "Deutschland Tour", "men", "uci-proseries", country="DE"),
                race("muensterland-giro", "Sparkassen Münsterland Giro", "men", "uci-proseries", country="DE"),
            ]
        }
    }

    groups = build_site_data.build_race_groups_payload(config)

    assert len(groups) == 1
    group = groups[0]
    assert group["tier"] == "uci-proseries"
    assert group["gender"] == "men"
    assert group["label"] == "UCI ProSeries"
    assert [r["id"] for r in group["races"]] == ["deutschland-tour", "muensterland-giro"]
    assert group["races"][0]["country"] == "DE"


def test_mixed_gender_tier_splits_into_two_labeled_groups():
    config = {
        "cycling": {
            "races": [
                race("tour-de-france", "Tour de France", "men", "grand-tour"),
                race("giro-d-italia", "Giro d'Italia", "men", "grand-tour"),
                race("tour-de-france-femmes", "Tour de France Femmes", "women", "grand-tour"),
            ]
        }
    }

    groups = build_site_data.build_race_groups_payload(config)

    assert len(groups) == 2
    men_group, women_group = groups
    assert men_group["label"] == "Grand Tours Männer"
    assert [r["id"] for r in men_group["races"]] == ["tour-de-france", "giro-d-italia"]
    assert women_group["label"] == "Grand Tours Frauen"
    assert [r["id"] for r in women_group["races"]] == ["tour-de-france-femmes"]


def test_groups_ordered_by_tier_then_gender():
    config = {
        "cycling": {
            "races": [
                race("deutschland-tour", "Deutschland Tour", "men", "uci-proseries"),
                race("itzulia-women", "Itzulia Women", "women", "uci-worldtour"),
                race("paris-nice", "Paris-Nice", "men", "uci-worldtour"),
                race("tour-de-france", "Tour de France", "men", "grand-tour"),
            ]
        }
    }

    groups = build_site_data.build_race_groups_payload(config)

    assert [(g["tier"], g["gender"]) for g in groups] == [
        ("grand-tour", "men"),
        ("uci-worldtour", "men"),
        ("uci-worldtour", "women"),
        ("uci-proseries", "men"),
    ]


def test_country_omitted_when_not_present():
    config = {"cycling": {"races": [race("tour-de-france", "Tour de France", "men", "grand-tour")]}}

    groups = build_site_data.build_race_groups_payload(config)

    assert "country" not in groups[0]["races"][0]


def test_empty_tier_produces_no_group():
    config = {"cycling": {"races": [race("tour-de-france", "Tour de France", "men", "grand-tour")]}}

    groups = build_site_data.build_race_groups_payload(config)

    assert all(g["tier"] != "regional" for g in groups)


def test_short_name_passed_through_to_race_entry():
    config = {
        "cycling": {
            "races": [race("tour-de-france", "Tour de France", "men", "grand-tour", short="TDF")]
        }
    }

    groups = build_site_data.build_race_groups_payload(config)

    assert groups[0]["races"][0]["shortName"] == "TDF"
