import json

import common


def test_load_stadiums_returns_empty_dict_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(common, "STADIUMS_PATH", tmp_path / "does-not-exist.json")
    assert common.load_stadiums() == {}


def test_load_stadiums_reads_club_id_to_location_mapping(monkeypatch, tmp_path):
    path = tmp_path / "stadiums.json"
    path.write_text(
        json.dumps({"sgs-essen": "Stadion Essen-West, Essen", "vfl-bochum": "Lohrheidestadion, Bochum"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(common, "STADIUMS_PATH", path)

    stadiums = common.load_stadiums()

    assert stadiums == {"sgs-essen": "Stadion Essen-West, Essen", "vfl-bochum": "Lohrheidestadion, Bochum"}


def test_real_stadiums_json_loads_and_only_has_string_values():
    """Sanity check against the actual config/stadiums.json shipped in the
    repo -- catches an accidental typo (wrong type, trailing comma, ...)
    without pinning its exact contents, so entries can be added freely."""
    stadiums = common.load_stadiums()
    assert isinstance(stadiums, dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in stadiums.items())
