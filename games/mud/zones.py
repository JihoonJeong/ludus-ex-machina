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


# ── Grimhold Keep (world #2 — fantasy dungeon-quest) ─────────────────────────
# WM axis: DEEP DEPENDENCY CHAIN (long causal tracking). Solve path:
# take charm (search sarcophagus) → use charm on gargoyle → reveals rune key →
# unlock+open reliquary → silver sigil → unlock portcullis → vault → Emberheart.
# Uses only existing engine mechanics (locks / search / interaction / npc) —
# zero engine changes (fantasy = adventure/puzzle, not combat/stats).

GRIMHOLD_KEEP = {
    "scenario_id": "grimhold_keep",
    "title": "Grimhold Keep",
    "goal": "Descend the ruined keep and claim the Emberheart from the sealed vault.",
    "goal_object": "emberheart",
    "start_room": "cell",
    "turn_limit": 50,

    "rooms": {
        "cell": {
            "name": "The Broken Cell",
            "desc": ("A damp prison cell deep in Grimhold Keep. The iron door hangs broken "
                     "on its hinges. Words are scratched into the mildewed wall."),
            "exits": {"north": {"to": "corridor"}},
        },
        "corridor": {
            "name": "The Torchlit Corridor",
            "desc": ("A long corridor of weeping stone, a few torches still guttering in "
                     "their sconces. Passages branch in several directions."),
            "exits": {"south": {"to": "cell"}, "west": {"to": "great_hall"},
                      "east": {"to": "crypt"}, "north": {"to": "chapel"}},
        },
        "great_hall": {
            "name": "The Ruined Great Hall",
            "desc": ("A vast hall of fallen banners and shattered tables. A crouching stone "
                     "gargoyle glares from a plinth, and to the north a heavy iron portcullis "
                     "bars the way to the vault."),
            "exits": {"east": {"to": "corridor"},
                      "north": {"to": "vault", "lock": "portcullis"}},
        },
        "crypt": {
            "name": "The Crypt",
            "desc": ("Rows of mouldering tombs. A cracked stone sarcophagus dominates the "
                     "chamber, and a skeletal warden slumps against the far wall."),
            "exits": {"west": {"to": "corridor"}},
        },
        "chapel": {
            "name": "The Fallen Chapel",
            "desc": ("A ruined chapel, its altar toppled among the rubble. An iron reliquary, "
                     "sealed by a rune-etched lock, stands somehow intact."),
            "exits": {"south": {"to": "corridor"}},
        },
        "vault": {
            "name": "The Sealed Vault",
            "desc": ("A cold stone vault. On a raised plinth rests the Emberheart, a gem "
                     "pulsing with trapped fire."),
            "exits": {"south": {"to": "great_hall"}},
        },
    },

    "locks": {
        "portcullis": {"locked": True, "key": "silver_sigil"},
    },

    "objects": {
        "inscription": {"name": "scratched words", "loc": "room:cell", "takeable": False, "visible": True,
                        "examine": "Words gouged into the wall: 'Only the charmed may wake the watcher of stone.'",
                        "read": "'Only the charmed may wake the watcher of stone.'"},
        "torch": {"name": "guttering torch", "loc": "room:cell", "takeable": True, "visible": True,
                  "examine": "A pitch-soaked torch, still burning — enough to see by in the dark."},
        "sarcophagus": {"name": "stone sarcophagus", "loc": "room:crypt", "takeable": False, "visible": True,
                        "examine": "A cracked sarcophagus, its lid shoved askew. Something lies within a searching hand's reach.",
                        "searchable": True},
        "bone_charm": {"name": "bone charm", "loc": "room:crypt", "takeable": True, "visible": False,
                       "examine": "A charm of carved bone, oddly warm to the touch."},
        "gargoyle": {"name": "stone gargoyle", "loc": "room:great_hall", "takeable": False, "visible": True,
                     "examine": "A crouching gargoyle of black stone. A charm-shaped socket sits empty at its breast.",
                     "state": {"awakened": False}},
        "rune_key": {"name": "rune-etched key", "loc": "room:great_hall", "takeable": True, "visible": False,
                     "examine": "A heavy iron key etched with runes."},
        "reliquary": {"name": "iron reliquary", "loc": "room:chapel", "takeable": False, "visible": True,
                      "container": True, "open": False, "locked": True, "key": "rune_key",
                      "examine": "An iron reliquary sealed by a rune-etched lock."},
        "silver_sigil": {"name": "silver sigil", "loc": "in:reliquary", "takeable": True, "visible": True,
                         "examine": "A silver sigil bearing the crest of Grimhold — shaped to seat in a great lock."},
        "emberheart": {"name": "Emberheart", "loc": "room:vault", "takeable": True, "visible": True,
                       "examine": "A gem the size of a fist, pulsing with trapped fire. The prize."},
        # flavor / distractors (examine-only or useless — a relevance check)
        "rusty_sword": {"name": "rusty longsword", "loc": "room:great_hall", "takeable": True, "visible": True,
                        "examine": "A rusted longsword, its blade snapped a hand from the hilt. Useless now."},
        "banner": {"name": "tattered banner", "loc": "room:great_hall", "takeable": False, "visible": True,
                   "examine": "A moth-eaten banner bearing a faded golden crest."},
    },

    "interactions": {
        ("bone_charm", "gargoyle"): {
            "object_state": {"gargoyle": {"awakened": True}},
            "reveal": ["rune_key"],
            "consume": "bone_charm",
            "event": ("You press the bone charm into the gargoyle's socket. Its stone eyes "
                      "kindle with a dim light and, with a grinding groan, it lifts a claw — "
                      "beneath it lies a rune-etched iron key."),
        },
    },

    "search": {
        "sarcophagus": {"reveal": ["bone_charm"],
                        "event": "You search the sarcophagus and find, clutched in withered fingers, a charm of bone."},
    },

    "npcs": {
        "warden": {
            "name": "the skeletal warden", "loc": "crypt",
            "talk": ("The warden's jaw creaks open: 'The watcher of stone guards the way, "
                     "living one. Only the charmed may wake it — and charms sleep with the "
                     "dead. Search where I have lain.'"),
        },
    },
}


# ── Derelict: SS Erebus (world #3 — sci-fi) ──────────────────────────────────
# WM axis: MUTABLE / REVERSIBLE STATE. The goal needs a *configuration*, reached
# in order: inject coolant → ignite reactor (requires coolant) → route power to
# the bridge (requires reactor online) → bridge door unlocks (requires power) →
# take the Nav-Core. Uses the new interaction `requires` flag-gate (ordering) +
# existing lock/interaction/search — a small engine add, no combat/stats.
#
# Solve: (cargo) take canister → (engineering) use canister on coolant_port →
# use igniter on reactor → (corridor→) route power at power_console →
# go to bridge (door now powered/open) → take nav_core.

SS_EREBUS = {
    "scenario_id": "ss_erebus",
    "title": "Derelict: SS Erebus",
    "goal": "Restore power and recover the Nav-Core from the bridge.",
    "goal_object": "nav_core",
    "start_room": "airlock",
    "turn_limit": 55,

    "rooms": {
        "airlock": {
            "name": "The Airlock",
            "desc": ("Emergency lighting bathes the airlock in dim red. A hatch leads inward "
                     "to the ship's spine. A cracked datapad floats tethered to the wall."),
            "exits": {"in": {"to": "corridor"}},
        },
        "corridor": {
            "name": "The Spinal Corridor",
            "desc": ("A long dead corridor, gravity plating flickering. Hatches branch fore "
                     "and aft. A wall-mounted power console blinks a sullen amber, and the "
                     "forward blast door to the bridge is sealed, unpowered."),
            "exits": {"out": {"to": "airlock"},
                      "aft": {"to": "cargo"}, "port": {"to": "engineering"},
                      "fore": {"to": "bridge", "lock": "bridge_door"}},
        },
        "cargo": {
            "name": "The Cargo Bay",
            "desc": ("Toppled crates drift in the low gravity. Most are junk, but a rack of "
                     "labelled canisters is bolted to the bulkhead."),
            "exits": {"fore": {"to": "corridor"}},
        },
        "engineering": {
            "name": "Engineering",
            "desc": ("The reactor housing dominates the room, dark and cold. A coolant port "
                     "gapes empty beside it, and a plasma igniter rests in a cradle."),
            "exits": {"starboard": {"to": "corridor"}},
        },
        "bridge": {
            "name": "The Bridge",
            "desc": ("The command bridge, viewports black with dead stars. In a receiver slot "
                     "on the helm console sits the Nav-Core, faintly humming now that power "
                     "has returned."),
            "exits": {"aft": {"to": "corridor"}},
        },
    },

    "locks": {
        # Unsealed by routing power (the nav_lever→power_console interaction sets
        # locked:false via unlock_lock), never by a carried key.
        "bridge_door": {"locked": True, "key": None},
    },

    "objects": {
        "datapad": {"name": "cracked datapad", "loc": "room:airlock", "takeable": True, "visible": True,
                    "examine": "A cracked datapad. Last log: 'Reactor scrammed. Cold-start needs coolant "
                               "BEFORE ignition, then route power forward. Do it in that order or she won't light.'",
                    "read": "'Cold-start: coolant first, THEN ignite. Then route power to the bridge.'"},
        "canister": {"name": "coolant canister", "loc": "room:cargo", "takeable": True, "visible": True,
                     "examine": "A pressurized canister marked COOLANT — reactor-grade."},
        "junk_crate": {"name": "battered crate", "loc": "room:cargo", "takeable": False, "visible": True,
                       "examine": "A battered crate of ration packs and worthless salvage.", "searchable": True},
        "coolant_port": {"name": "coolant port", "loc": "room:engineering", "takeable": False, "visible": True,
                         "examine": "An intake port for reactor coolant. Empty.", "state": {"filled": False}},
        "reactor": {"name": "reactor housing", "loc": "room:engineering", "takeable": False, "visible": True,
                    "examine": "The main reactor. Cold and dark. It needs coolant, then an ignition source.",
                    "state": {"online": False}},
        "igniter": {"name": "plasma igniter", "loc": "room:engineering", "takeable": True, "visible": True,
                    "examine": "A handheld plasma igniter — enough to spark a reactor cold-start."},
        "power_console": {"name": "power console", "loc": "room:corridor", "takeable": False, "visible": True,
                          "examine": "A power-routing console. It can direct reactor output forward to the "
                                     "bridge — but only once the reactor is online. A manual routing lever slots here.",
                          "state": {"routed": False}},
        "nav_lever": {"name": "routing lever", "loc": "room:cargo", "takeable": True, "visible": True,
                      "examine": "A manual routing lever. Slot it into the power console to direct output."},
        "nav_core": {"name": "Nav-Core", "loc": "room:bridge", "takeable": True, "visible": True,
                     "examine": "The ship's navigation core, humming softly. The prize."},
    },

    "interactions": {
        # 1. coolant first
        ("canister", "coolant_port"): {
            "set_flags": {"coolant_loaded": True},
            "object_state": {"coolant_port": {"filled": True}},
            "consume": "canister",
            "event": "You lock the canister into the coolant port; reactor-grade coolant floods the lines.",
        },
        # 2. ignite — REQUIRES coolant (mutable-state ordering)
        ("igniter", "reactor"): {
            "requires": {"coolant_loaded": True},
            "requires_event": ("You spark the igniter against the reactor, but with no coolant it "
                               "overheats and auto-scrams. Nothing lights."),
            "set_flags": {"reactor_online": True},
            "object_state": {"reactor": {"online": True}},
            "event": ("Coolant hisses, the igniter flares, and the reactor catches with a rising "
                      "hum. Power returns to the ship's spine."),
        },
        # 3. route power — REQUIRES reactor online; unseals the bridge door
        ("nav_lever", "power_console"): {
            "requires": {"reactor_online": True},
            "requires_event": ("You throw the routing lever, but the console is dead — the reactor "
                               "isn't online, so there's no power to route."),
            "set_flags": {"bridge_powered": True},
            "object_state": {"power_console": {"routed": True}},
            "unlock_lock": "bridge_door",
            "consume": "nav_lever",
            "event": ("You slot the lever and throw it. The console lights green and power surges "
                      "forward — the bridge blast door unseals with a heavy clunk."),
        },
    },

    "search": {
        "junk_crate": {"reveal": [], "event": "You rummage the crate: ration packs, a cracked mug. Nothing useful."},
    },

    "npcs": {},
}


# ── Critter Cove (world #4 — collection) ─────────────────────────────────────
# WM axis: RELEVANCE + collection. Catch all THREE critters (goal_objects set).
# Each hides until lured with the RIGHT bait (matching bait→critter is the
# relevance test — wrong bait is a clear no-op), then can be taken. Baits are
# scattered; a warden NPC hints the pairings. Uses the multi-collect win-set +
# the `requires`/reveal interaction machinery — small collect-goal engine add.
#
# Pairings: sugar_fig→glimmermoth (grove) · silver_fish→tide_newt (tidepool) ·
#           honey_comb→ember_vole (burrow). Solve = for each: take bait → use
#           bait on lure spot (reveals critter) → take critter.

CRITTER_COVE = {
    "scenario_id": "critter_cove",
    "title": "Critter Cove",
    "goal": "Catch all three critters of the cove: the glimmermoth, the tide-newt, and the ember-vole.",
    "goal_objects": ["glimmermoth", "tide_newt", "ember_vole"],
    "start_room": "beach",
    "turn_limit": 60,

    "rooms": {
        "beach": {
            "name": "The Sun-Warmed Beach",
            "desc": ("A crescent of golden sand. A weathered ranger's hut sits above the tideline, "
                     "and a driftwood sign points inland. Paths lead to a grove, a tidepool, and a burrow."),
            "exits": {"north": {"to": "grove"}, "east": {"to": "tidepool"}, "west": {"to": "burrow"}},
        },
        "grove": {
            "name": "The Glimmer Grove",
            "desc": ("A grove of pale trees whose leaves catch the light. Something flutters just out "
                     "of sight among the blossoms — glimmermoths love sweet fruit."),
            "exits": {"south": {"to": "beach"}},
        },
        "tidepool": {
            "name": "The Tidepool Shallows",
            "desc": ("Clear pools among barnacled rocks. Ripples suggest something small and quick "
                     "hides beneath — tide-newts dart after little fish."),
            "exits": {"west": {"to": "beach"}},
        },
        "burrow": {
            "name": "The Warm Burrow",
            "desc": ("A snug hollow beneath tree roots, oddly warm. A pair of eyes glints deep in the "
                     "dark — ember-voles are drawn to sweetness."),
            "exits": {"east": {"to": "beach"}},
        },
    },

    "objects": {
        "sign": {"name": "driftwood sign", "loc": "room:beach", "takeable": False, "visible": True,
                 "examine": "Painted on driftwood: 'Cove critters are shy. Lure each with the treat it "
                            "loves — moths to figs, newts to fish, voles to honey. Ask the ranger if unsure.'",
                 "read": "'Moths to figs, newts to fish, voles to honey.'"},
        # baits (scattered — the collector must bring the RIGHT one to each spot)
        "sugar_fig": {"name": "sugar fig", "loc": "room:beach", "takeable": True, "visible": True,
                      "examine": "A sweet sugared fig. Something with a sweet tooth might love it."},
        "silver_fish": {"name": "silver fish", "loc": "room:tidepool", "takeable": True, "visible": True,
                        "examine": "A wriggling little silver fish."},
        "honey_comb": {"name": "honey comb", "loc": "room:burrow", "takeable": True, "visible": True,
                       "examine": "A dripping piece of honeycomb."},
        # lure spots (targets for `use bait on <spot>`)
        "blossoms": {"name": "sweet blossoms", "loc": "room:grove", "takeable": False, "visible": True,
                     "examine": "Fragrant blossoms where a glimmermoth flits, just out of reach."},
        "pool": {"name": "clear pool", "loc": "room:tidepool", "takeable": False, "visible": True,
                 "examine": "A clear tidepool; a tide-newt darts among the rocks."},
        "den": {"name": "dark den", "loc": "room:burrow", "takeable": False, "visible": True,
                "examine": "A warm dark den where an ember-vole hides."},
        # the critters — hidden until the right bait is used
        "glimmermoth": {"name": "glimmermoth", "loc": "room:grove", "takeable": True, "visible": False,
                        "examine": "A moth with shimmering, light-catching wings. Caught!"},
        "tide_newt": {"name": "tide-newt", "loc": "room:tidepool", "takeable": True, "visible": False,
                      "examine": "A quick little newt, still glistening. Caught!"},
        "ember_vole": {"name": "ember-vole", "loc": "room:burrow", "takeable": True, "visible": False,
                       "examine": "A warm, russet vole with ember-bright eyes. Caught!"},
    },

    "interactions": {
        ("sugar_fig", "blossoms"): {
            "reveal": ["glimmermoth"], "consume": "sugar_fig",
            "event": "You set the sugar fig on a blossom. A glimmermoth drifts down to feed — now within reach!",
        },
        ("silver_fish", "pool"): {
            "reveal": ["tide_newt"], "consume": "silver_fish",
            "event": "You dangle the silver fish over the pool. A tide-newt surfaces to snap at it — within reach!",
        },
        ("honey_comb", "den"): {
            "reveal": ["ember_vole"], "consume": "honey_comb",
            "event": "You leave the honeycomb by the den. An ember-vole creeps out to nibble — within reach!",
        },
    },

    "npcs": {
        "ranger": {
            "name": "the cove ranger", "loc": "beach",
            "talk": ("The ranger tips her hat: 'Three critters, three treats. The glimmermoth wants "
                     "the sugar fig, the tide-newt a silver fish, and the ember-vole loves honeycomb. "
                     "Bring the right treat to the right spot, or they'll not show.'"),
        },
    },
}


ZONES = {
    "astronomer_tower": ASTRONOMER_TOWER,
    "grimhold_keep": GRIMHOLD_KEEP,
    "ss_erebus": SS_EREBUS,
    "critter_cove": CRITTER_COVE,
}


def get_zone(scenario_id: str) -> dict:
    if scenario_id not in ZONES:
        raise ValueError(f"unknown mud zone: {scenario_id!r} (have: {sorted(ZONES)})")
    return copy.deepcopy(ZONES[scenario_id])
