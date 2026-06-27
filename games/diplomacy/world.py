"""Diplomacy v1 map — "The Wheel": a compact, rotationally-symmetric 5-power land map.

Topology (symmetric under 72° rotation):
  - 5 Capitals (home supply centers), one per power, each tucked between its two
    flanking Marches. A capital has exactly two exits (its two Marches) — a fortress
    home with clear front lines.
  - 5 Marches (neutral supply centers) forming the outer ring between adjacent
    capitals. Each March borders its two flanking capitals, its two neighbour
    Marches (lateral movement around the ring), and the central Crown (the gateway
    inward).
  - 1 Crown (neutral supply center) at the centre, bordering all five Marches — the
    prize, reachable only by pushing through a March.

11 provinces, every one a supply center. A power wins by holding a majority (6 of 11).
Land only: every unit is an Army; there are no fleets, seas, or convoys in v1.

The map is pure data so it can be retuned (power count, names, adjacency) without
touching the engine. The engine and tests import from here; the JS renderer keeps its
own coordinate layout but reuses these province ids verbatim.
"""

from __future__ import annotations

# Powers in canonical seat order. initial_state assigns powers to seats by
# participant index, so order here == default seating (cross-machine self-assign).
POWERS: list[dict] = [
    {"id": "crimson", "name": "Crimson", "color": "#d6453d", "capital": "pyre"},
    {"id": "gold",    "name": "Gold",    "color": "#e3b23c", "capital": "solace"},
    {"id": "verdant", "name": "Verdant", "color": "#3fa34d", "capital": "thorne"},
    {"id": "azure",   "name": "Azure",   "color": "#3d7fd6", "capital": "tarn"},
    {"id": "violet",  "name": "Violet",  "color": "#9b59b6", "capital": "vael"},
]

POWER_IDS: list[str] = [p["id"] for p in POWERS]
POWER_BY_ID: dict[str, dict] = {p["id"]: p for p in POWERS}

# kind: "capital" (home SC) | "march" (neutral ring SC) | "crown" (neutral centre SC)
PROVINCES: dict[str, dict] = {
    "pyre":      {"sc": True, "home": "crimson", "kind": "capital", "label": "Pyre"},
    "solace":    {"sc": True, "home": "gold",    "kind": "capital", "label": "Solace"},
    "thorne":    {"sc": True, "home": "verdant", "kind": "capital", "label": "Thorne"},
    "tarn":      {"sc": True, "home": "azure",   "kind": "capital", "label": "Tarn"},
    "vael":      {"sc": True, "home": "violet",  "kind": "capital", "label": "Vael"},
    "ashmoor":   {"sc": True, "home": None, "kind": "march", "label": "Ashmoor"},
    "sunreach":  {"sc": True, "home": None, "kind": "march", "label": "Sunreach"},
    "wildfen":   {"sc": True, "home": None, "kind": "march", "label": "Wildfen"},
    "coldwater": {"sc": True, "home": None, "kind": "march", "label": "Coldwater"},
    "duskgate":  {"sc": True, "home": None, "kind": "march", "label": "Duskgate"},
    "crown":     {"sc": True, "home": None, "kind": "crown", "label": "The Crown"},
}

# Undirected adjacency. Must be symmetric (checked at import).
ADJACENCY: dict[str, set[str]] = {
    # capitals: two flanking marches only
    "pyre":      {"ashmoor", "duskgate"},
    "solace":    {"ashmoor", "sunreach"},
    "thorne":    {"sunreach", "wildfen"},
    "tarn":      {"wildfen", "coldwater"},
    "vael":      {"coldwater", "duskgate"},
    # marches: 2 capitals + 2 neighbour marches + crown
    "ashmoor":   {"pyre", "solace", "duskgate", "sunreach", "crown"},
    "sunreach":  {"solace", "thorne", "ashmoor", "wildfen", "crown"},
    "wildfen":   {"thorne", "tarn", "sunreach", "coldwater", "crown"},
    "coldwater": {"tarn", "vael", "wildfen", "duskgate", "crown"},
    "duskgate":  {"vael", "pyre", "coldwater", "ashmoor", "crown"},
    # crown: all five marches
    "crown":     {"ashmoor", "sunreach", "wildfen", "coldwater", "duskgate"},
}

# Supply centers needed to win outright (majority of 11).
WIN_SUPPLY_CENTERS = 6


def neighbors(province: str) -> set[str]:
    """Provinces adjacent to `province`."""
    return ADJACENCY[province]


def are_adjacent(a: str, b: str) -> bool:
    return b in ADJACENCY.get(a, ())


def is_supply_center(province: str) -> bool:
    return PROVINCES[province]["sc"]


def all_supply_centers() -> list[str]:
    return [name for name, p in PROVINCES.items() if p["sc"]]


def home_center(power_id: str) -> str:
    """The single home supply center (capital) where a power may build."""
    return POWER_BY_ID[power_id]["capital"]


def starting_supply_centers() -> dict[str, str]:
    """Map of supply-center province -> owning power at game start (capitals only)."""
    return {p["capital"]: p["id"] for p in POWERS}


def _validate() -> None:
    """Catch map typos at import: symmetry, referential integrity, symmetry of design."""
    for prov, nbrs in ADJACENCY.items():
        assert prov in PROVINCES, f"adjacency lists unknown province {prov!r}"
        for n in nbrs:
            assert n in PROVINCES, f"{prov!r} adjacent to unknown province {n!r}"
            assert prov in ADJACENCY[n], f"asymmetric adjacency: {prov}-{n}"
            assert n != prov, f"{prov!r} adjacent to itself"
    for name in PROVINCES:
        assert name in ADJACENCY, f"province {name!r} missing from adjacency"
    # every capital is a home SC owned by exactly one power
    caps = [p["capital"] for p in POWERS]
    assert len(caps) == len(set(caps)), "two powers share a capital"
    for power in POWERS:
        cap = power["capital"]
        assert PROVINCES[cap]["home"] == power["id"], f"{cap} not home of {power['id']}"
    # majority is reachable
    assert WIN_SUPPLY_CENTERS <= len(all_supply_centers())


_validate()
