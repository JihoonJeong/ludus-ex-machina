"""Authored zones for the MUD field. The engine is a generic interpreter over
this data; a zone defines rooms, objects, locks, interactions, search reveals,
NPCs, and the goal.

Object `loc` is one of: "room:<rid>", "inv:<aid>", or None (consumed/unplaced).
`visible: False` means hidden until a search/interaction reveals it.

16-bit adventure soul: hand-authored prose, item-on-target puzzles, scripted
NPCs with canned dialogue.
"""

from __future__ import annotations

import copy


# ── The Astronomer's Tower (MVP) ────────────────────────────────────────────
# Solve path: down→west, search globe → take saturn_ring, east→up,
# use saturn_ring on orrery → take brass_key, unlock east → east, take star_orb.

ASTRONOMER_TOWER = {
    "scenario_id": "astronomer_tower",
    "title": "The Astronomer's Tower",
    "goal": "Open the locked Observatory and claim the Star-Orb.",
    "goal_object": "star_orb",          # taking it wins
    "start_room": "study",
    "turn_limit": 60,

    "rooms": {
        "study": {
            "name": "The Astronomer's Study",
            "desc": ("Dust motes drift through a shaft of moonlight from the cracked dome above. "
                     "A brass orrery ticks on the desk, and a star-chart is pinned to the wall."),
            "exits": {"down": {"to": "landing"},
                      "east": {"to": "observatory", "lock": "observatory_door"}},
        },
        "landing": {
            "name": "The Spiral Landing",
            "desc": ("A cramped stone landing where the spiral stair turns. Cold air rises from below. "
                     "Doorways open in three directions."),
            "exits": {"up": {"to": "study"}, "west": {"to": "library"},
                      "east": {"to": "alchemy"}},
        },
        "library": {
            "name": "The Library",
            "desc": ("Sagging shelves of astronomical tomes line the walls. A great celestial globe "
                     "stands on a brass cradle in the centre, its surface pocked with tiny craters."),
            "exits": {"east": {"to": "landing"}},
        },
        "alchemy": {
            "name": "The Alchemy Lab",
            "desc": ("Bubbling retorts and the sharp smell of sulphur. A locked cabinet rattles faintly. "
                     "A glossy black raven watches you from a perch."),
            "exits": {"west": {"to": "landing"}},
        },
        "observatory": {
            "name": "The Observatory",
            "desc": ("The great telescope points at a sky of impossible stars. On a velvet plinth rests "
                     "the Star-Orb, drinking the light."),
            "exits": {"west": {"to": "study"}},
        },
    },

    "locks": {
        "observatory_door": {"locked": True, "key": "brass_key"},
    },

    "objects": {
        "orrery": {"name": "brass orrery", "loc": "room:study", "takeable": False, "visible": True,
                   "examine": "A clockwork model of the heavens — but the socket for Saturn's ring sits empty.",
                   "state": {"complete": False}},
        "star_chart": {"name": "star-chart", "loc": "room:study", "takeable": True, "visible": True,
                       "examine": "Faded constellations, and a margin note: 'The ring completes the dance; the dance opens the brass.'",
                       "read": "'The ring completes the dance; the dance opens the brass.'"},
        "globe": {"name": "celestial globe", "loc": "room:library", "takeable": False, "visible": True,
                  "examine": "A heavy globe of the night sky. Something small seems lodged in a crater.",
                  "searchable": True},
        "saturn_ring": {"name": "Saturn-ring", "loc": "room:library", "takeable": True, "visible": False,
                        "examine": "A delicate golden ring, sized for an orrery's Saturn."},
        "brass_key": {"name": "brass key", "loc": "room:study", "takeable": True, "visible": False,
                      "examine": "A heavy brass key, warm to the touch."},
        "cabinet": {"name": "locked cabinet", "loc": "room:alchemy", "takeable": False, "visible": True,
                    "examine": "A small iron cabinet. Locked. It rattles when the raven caws.",
                    "container": True, "open": False, "locked": True},
        "fig": {"name": "sugared fig", "loc": "room:alchemy", "takeable": True, "visible": True,
                "examine": "A sticky sweet fig. Ravens adore these."},
        "star_orb": {"name": "Star-Orb", "loc": "room:observatory", "takeable": True, "visible": True,
                     "examine": "A sphere of trapped starlight. The prize."},
    },

    # use <item> on <target>  →  effect
    "interactions": {
        ("saturn_ring", "orrery"): {
            # Completion lives on the object (orrery.state.complete) — no
            # redundant global flag (Ludex Cody point 5: avoid double-
            # representation; lock/open/state belong on the exit/object).
            "object_state": {"orrery": {"complete": True}},
            "reveal": ["brass_key"],
            "consume": "saturn_ring",
            "event": ("You fit the Saturn-ring into the orrery. It whirs to life, the planets spin, "
                      "and a hidden compartment springs open — revealing a brass key."),
        },
    },

    # search <target>  →  reveal hidden objects
    "search": {
        "globe": {"reveal": ["saturn_ring"],
                  "event": "You probe the globe's craters and work a Saturn-ring loose from one of them."},
    },

    "npcs": {
        "raven": {
            "name": "the raven familiar", "loc": "alchemy",
            "talk": "The raven fixes you with a beady eye and rasps: "
                    "'The ring rolled into the globe. The dance opens the brass.'",
            "give": {
                "fig": {"event": "The raven gulps the fig and croaks happily: "
                                 "'Brass opens the stars. Mind the eastern door.' Then it preens, content.",
                        "set_flags": {"raven_fed": True}},
            },
        },
    },
}


ZONES = {
    "astronomer_tower": ASTRONOMER_TOWER,
}


def get_zone(scenario_id: str) -> dict:
    if scenario_id not in ZONES:
        raise ValueError(f"unknown mud zone: {scenario_id!r} (have: {sorted(ZONES)})")
    return copy.deepcopy(ZONES[scenario_id])
