import json
from pathlib import Path

PRICE_TABLE_PATH = Path("data/price_table.json")

EXPECTED_PARTS = [
    "front-bumper",
    "back-bumper",
    "hood",
    "trunk",
    "front-door",
    "back-door",
    "fender",
    "quarter-panel",
    "rocker-panel",
    "windshield",
    "back-windshield",
    "front-window",
    "back-window",
    "headlight",
    "tail-light",
    "license-plate",
    "mirror",
    "roof",
    "grille",
    "front-wheel",
    "back-wheel",
]

EXPECTED_DAMAGES = [
    "scratch",
    "dent",
    "crack",
    "glass shatter",
    "lamp broken",
    "tire flat",
]


def test_price_table_loads_and_has_metadata():
    assert PRICE_TABLE_PATH.exists()
    with open(PRICE_TABLE_PATH, "r") as f:
        data = json.load(f)

    assert "metadata" in data
    assert data["metadata"]["currency"] == "USD"
    assert "default_fallback" in data
    assert "components" in data


def test_default_fallback_covers_all_damages():
    with open(PRICE_TABLE_PATH, "r") as f:
        data = json.load(f)

    fallback = data["default_fallback"]
    for dmg in EXPECTED_DAMAGES:
        assert dmg in fallback, f"Missing fallback for damage: {dmg}"
        entry = fallback[dmg]
        assert 0 < entry["min_cost"] <= entry["max_cost"]
        assert entry["action"] in {"repair", "replace"}


def test_components_cover_all_parts_and_damages():
    with open(PRICE_TABLE_PATH, "r") as f:
        data = json.load(f)

    components = data["components"]
    for part in EXPECTED_PARTS:
        assert part in components, f"Missing component in price table: {part}"
        comp_entry = components[part]
        assert "damages" in comp_entry

        for dmg in EXPECTED_DAMAGES:
            assert dmg in comp_entry["damages"], f"Missing damage '{dmg}' for part '{part}'"
            item = comp_entry["damages"][dmg]
            assert 0 < item["min_cost"] <= item["max_cost"], f"Invalid cost range for {part}:{dmg}"
            assert item["action"] in {"repair", "replace"}, f"Invalid action for {part}:{dmg}"
