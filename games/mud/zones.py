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
    "genre": "fantasy",
    "wm_axis": "fog + linear dependency + hint inference",
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
    "genre": "fantasy",
    "wm_axis": "deep dependency chain",
    "goal": "Descend the ruined keep and claim the Emberheart from the sealed vault.",
    "goal_object": "emberheart",
    "start_room": "cell",
    # 80 ≈ 4.4x the 18-turn scripted solve, in line with the other worlds
    # (tower 5.5x, erebus 4.2x, cove 4.3x). The first runs used 50 (2.8x) —
    # the tightest of the four — and a clean run died mid-chain at t40/50.
    "turn_limit": 80,

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
            "talk": ("The warden's jaw creaks open: 'The watcher of stone crouches in the "
                     "ruined great hall, west of the corridor. Only the charmed may wake it — "
                     "and charms sleep with the dead. Search where I have lain.'"),
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
    "genre": "sci-fi",
    "wm_axis": "mutable/reversible state",
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
        # The room desc advertises the rack, so it must be examinable — a live run
        # looped on "examine rack of labelled canisters" -> "no such thing" (2026-07-03).
        "canister_rack": {"name": "rack of labelled canisters", "loc": "room:cargo", "takeable": False,
                          "visible": True,
                          "examine": "A bolted storage rack. Most clamps are empty; one reactor-grade "
                                     "coolant canister remains."},
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
    "genre": "collection",
    "wm_axis": "relevance + collect-a-set",
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


# ── The Tidewater Warren (world #5 — graded-chain ablation zone) ──────────────
# WM axis: SPATIAL REACHABILITY. Purpose-built for the LxM×Ludex organ ablation
# (Ray's chain-depth DV). Unlike Erebus (logic-ordered: infer coolant-before-
# ignite), here the ORDER is enforced by map topology, not inference — you
# physically cannot reach the next spine room until you clear the current gate.
# So difficulty is spatial (find the item in a side room, carry it to the gate,
# backtrack), never logic. Design contract with Ludex (gate/organ are both pure
# spatial faculties):
#   - Linear spine mouth→sump→deep→grotto→hoard, 4 gates → chain-depth 0..4,
#     each gate cleared by an item fetched from a DISTINCT side room (sub-goals
#     spatially distributed → organ reachability faculty engages).
#   - Link 1 (sluice) is TRIVIAL: crank + valve both in the start room, so a bare
#     brain avoids the floor (target: bare haiku-medium lands 1–2, organ headroom
#     to 3–4). Calibrated on the A arm only, sealed from B/C, before pre-reg lock.
#   - Side/bait rooms (north_burrow red herring) give real over-exploration
#     surface so the gate's commit branch (explore→solve timing) has something to
#     bite. Turn budget 90 so turn-limit isn't the binding constraint.
# NO `requires` flag-gates here (that would be logic-ordering) — topology alone
# orders the chain.
TIDEWATER_WARREN = {
    "scenario_id": "tidewater_warren",
    "title": "The Tidewater Warren",
    "genre": "fantasy",
    "wm_axis": "spatial reachability",
    "goal": "Descend the warren and recover the Tide-Pearl from the hoard.",
    "goal_object": "tide_pearl",
    "start_room": "warren_mouth",
    "turn_limit": 90,

    "rooms": {
        "warren_mouth": {
            "name": "The Warren Mouth",
            "desc": ("A brackish cave entrance. Seawater has flooded the passage sloping DOWN, "
                     "and a rusted sluice valve juts from the wall with a crank slot beside it. "
                     "Side tunnels run NORTH and EAST into the dark."),
            "exits": {"down": {"to": "the_sump", "lock": "sump_flood"},
                      "north": {"to": "north_burrow"},
                      "east": {"to": "east_burrow"}},
        },
        "north_burrow": {
            "name": "The North Burrow",
            "desc": ("A cramped dead-end burrow, smelling of old kelp. Shells and cracked crab "
                     "carapaces litter the floor. Nothing here looks useful."),
            "exits": {"south": {"to": "warren_mouth"}},
        },
        "east_burrow": {
            "name": "The East Burrow",
            "desc": ("A dry alcove above the tideline. A whaler's lantern hangs from a peg, "
                     "still half full of oil."),
            "exits": {"west": {"to": "warren_mouth"}},
        },
        "the_sump": {
            "name": "The Drained Sump",
            "desc": ("A cistern, its water now drained to a slick floor. A passage runs DEEPER "
                     "into pitch blackness, and a dry side-vault opens to the SIDE."),
            "exits": {"up": {"to": "warren_mouth"},
                      "deep": {"to": "deep_gallery", "lock": "dark_passage"},
                      "side": {"to": "the_dry_vault"}},
        },
        "the_dry_vault": {
            "name": "The Dry Vault",
            "desc": ("A storeroom spared the flood. A stout timber plank leans in one corner, "
                     "long enough to span a gap."),
            "exits": {"out": {"to": "the_sump"}},
        },
        "deep_gallery": {
            "name": "The Deep Gallery",
            "desc": ("A wide cavern, lit now by your lantern. A black chasm splits the floor, "
                     "cutting off the passage IN. A low ALCOVE branches off to one side."),
            "exits": {"up": {"to": "the_sump"},
                      "in": {"to": "the_grotto", "lock": "chasm"},
                      "alcove": {"to": "the_alcove"}},
        },
        "the_alcove": {
            "name": "The Tool Alcove",
            "desc": ("A miner's niche. A cold chisel and a few rusted spikes rest on a ledge."),
            "exits": {"out": {"to": "deep_gallery"}},
        },
        "the_grotto": {
            "name": "The Sealed Grotto",
            "desc": ("A dripping grotto. The way to the hoard is barred by a barnacle-crusted "
                     "stone seal, its mortar soft and crumbling."),
            "exits": {"out": {"to": "deep_gallery"},
                      "hoard": {"to": "the_hoard", "lock": "seal"}},
        },
        "the_hoard": {
            "name": "The Hoard",
            "desc": ("A smuggler's hoard, glittering with wet coin. On a coral plinth rests the "
                     "Tide-Pearl, luminous and cold."),
            "exits": {"out": {"to": "the_grotto"}},
        },
    },

    "locks": {
        # All unsealed by an item→gate interaction (unlock_lock), never a carried key.
        "sump_flood": {"locked": True, "key": None},
        "dark_passage": {"locked": True, "key": None},
        "chasm": {"locked": True, "key": None},
        "seal": {"locked": True, "key": None},
    },

    "objects": {
        # Link 1 (TRIVIAL — both in start room)
        "crank": {"name": "iron crank", "loc": "room:warren_mouth", "takeable": True, "visible": True,
                  "examine": "A heavy iron crank. It looks like it would fit the sluice valve's slot."},
        "sluice_valve": {"name": "sluice valve", "loc": "room:warren_mouth", "takeable": False, "visible": True,
                         "examine": "A rusted sluice valve with an empty crank slot. Turning it would drain "
                                    "the flooded passage below.", "state": {"open": False}},
        # Link 2 (lantern in east_burrow → dark passage in the_sump)
        "lantern": {"name": "whaler's lantern", "loc": "room:east_burrow", "takeable": True, "visible": True,
                    "examine": "A whaler's oil lantern, half full and ready to light the dark."},
        "dark_passage": {"name": "pitch-black passage", "loc": "room:the_sump", "takeable": False, "visible": True,
                         "examine": "A passage swallowed in total darkness. You'd need a light to go deeper.",
                         "state": {"lit": False}},
        # Link 3 (plank in the_dry_vault → chasm in deep_gallery)
        "plank": {"name": "timber plank", "loc": "room:the_dry_vault", "takeable": True, "visible": True,
                  "examine": "A stout timber plank, long enough to bridge a gap."},
        "chasm": {"name": "black chasm", "loc": "room:deep_gallery", "takeable": False, "visible": True,
                  "examine": "A chasm splitting the gallery floor — too wide to jump, but a plank would span it.",
                  "state": {"bridged": False}},
        # Link 4 (chisel in the_alcove → seal in the_grotto)
        "chisel": {"name": "cold chisel", "loc": "room:the_alcove", "takeable": True, "visible": True,
                   "examine": "A cold chisel, still sharp — the kind that bites soft mortar."},
        "seal": {"name": "stone seal", "loc": "room:the_grotto", "takeable": False, "visible": True,
                 "examine": "A barnacle-crusted stone seal set in soft, crumbling mortar. A chisel would break it.",
                 "state": {"broken": False}},
        # bait / red herring
        "carapaces": {"name": "cracked carapaces", "loc": "room:north_burrow", "takeable": False, "visible": True,
                      "examine": "Empty crab shells. Nothing hides among them.", "searchable": True},
        # goal
        "tide_pearl": {"name": "Tide-Pearl", "loc": "room:the_hoard", "takeable": True, "visible": True,
                       "examine": "The Tide-Pearl — cold, luminous, and heavier than it looks. The prize."},
    },

    "interactions": {
        # Order is enforced by TOPOLOGY, not by `requires` — each gate simply
        # unlocks the exit to the next spine room. No logic-ordering to infer.
        ("crank", "sluice_valve"): {
            "set_flags": {"sluice_open": True},
            "object_state": {"sluice_valve": {"open": True}},
            "unlock_lock": "sump_flood",
            "event": "You seat the crank and heave. The valve grinds open and the flooded passage "
                     "drains away with a sucking roar, opening the way DOWN.",
        },
        ("lantern", "dark_passage"): {
            "set_flags": {"lantern_lit": True},
            "object_state": {"dark_passage": {"lit": True}},
            "unlock_lock": "dark_passage",
            "event": "You raise the lit lantern; the darkness peels back and the passage DEEP "
                     "into the gallery opens before you.",
        },
        ("plank", "chasm"): {
            "set_flags": {"chasm_bridged": True},
            "object_state": {"chasm": {"bridged": True}},
            "unlock_lock": "chasm",
            "consume": "plank",
            "event": "You lay the plank across the chasm. It holds — the way IN to the grotto is open.",
        },
        ("chisel", "seal"): {
            "set_flags": {"seal_broken": True},
            "object_state": {"seal": {"broken": True}},
            "unlock_lock": "seal",
            "event": "You work the chisel into the soft mortar and lever. The stone seal cracks and "
                     "topples, baring the way to the HOARD.",
        },
    },

    "search": {
        "carapaces": {"reveal": [], "event": "You sift the carapaces: brine and grit, nothing more."},
    },

    "npcs": {},
}


# ── Tidewater Warren P3 variant — the Warded Pearl (logic-gated 5th link) ────
# Ludex×Ray P3 request (2026-07-11): does plan_view (observed-only sequencing)
# add anything beyond the Taxis latch when the order must be INFERRED rather
# than topology-forced? Built as a deepcopy-extension of TIDEWATER_WARREN so
# links 1-4 are UNCHANGED BY CONSTRUCTION (their requirement #1; asserted in
# tests). Everything new lives strictly PAST link 4 (grotto/hoard), so the
# approach path is byte-identical.
#
# The 5th "link" is a RITUAL whose order is stated only in an inscription in
# the grotto (observed-only knowledge — read it, hold it, apply it one room
# later): moon → salt → storm → ebb, each stone placed on the warded plinth
# via `requires`-chained interactions. A wrong stone is a deterministic no-op
# with a uniform failure line (no order feedback), so brute force costs up to
# 4+3+2+1 = 10 placements while the inscription plan needs 4. The final stone
# lifts the ward (flag ward_lifted) and REVEALS the Tide-Pearl (visible:false
# until then); taking it wins, same goal_object as the base zone.
# Scorer chain: 4 spatial links + 4 ritual flags → chain_depth 0..8 (graded
# ritual progress for Ray's DV).
def _tidewater_p3() -> dict:
    z = copy.deepcopy(TIDEWATER_WARREN)
    z["scenario_id"] = "tidewater_warren_p3"
    z["title"] = "The Tidewater Warren — the Warded Pearl"
    z["wm_axis"] = "spatial reachability + inferred order (P3)"
    z["goal"] = "Descend the warren, lift the ward in the rite's order, and claim the Tide-Pearl."
    z["turn_limit"] = 110

    rooms, objs = z["rooms"], z["objects"]
    rooms["the_grotto"]["desc"] = (
        "A dripping grotto. The way to the hoard is barred by a barnacle-crusted "
        "stone seal, its mortar soft and crumbling. Above the seal, an old tide-rite "
        "inscription is chiselled into the rock.")
    rooms["the_hoard"]["desc"] = (
        "A smuggler's hoard, glittering with wet coin. At its heart a coral plinth "
        "hums beneath a shimmering ward, and four rune-cut tide-stones lie among "
        "the treasure: moon, salt, storm, and ebb.")

    objs["inscription"] = {
        "name": "tide-rite inscription", "loc": "room:the_grotto", "takeable": False,
        "visible": True,
        "examine": "Chiselled verse, worn but legible. It reads like an order of rites.",
        "read": ("'The MOON draws the tide. The SALT rides the tide. "
                 "The STORM breaks the tide. The EBB stills it — and the ward with it.'"),
    }
    objs["warded_plinth"] = {
        "name": "warded plinth", "loc": "room:the_hoard", "takeable": False, "visible": True,
        "examine": ("A coral plinth under a shimmering ward. Four shallow sockets ring "
                    "its crown — something must be set into them, in some right order."),
        "state": {"stones_set": 0},
    }
    for sid, flavor in (("moon_stone", "a pale disc that seems to pull at the water"),
                        ("salt_stone", "a white crystal crusted in brine"),
                        ("storm_stone", "a dark stone that crackles faintly"),
                        ("ebb_stone", "a smooth grey stone, utterly still")):
        objs[sid] = {"name": sid.replace("_", " "), "loc": "room:the_hoard",
                     "takeable": True, "visible": True,
                     "examine": f"A rune-cut tide-stone: {flavor}."}
    # the pearl hides beneath the ward until the rite completes
    objs["tide_pearl"]["visible"] = False
    objs["tide_pearl"]["examine"] = ("The Tide-Pearl — cold, luminous, free of the "
                                     "ward at last. The prize.")

    WRONG = ("You set the stone in a socket. The ward flares white and hurls it back "
             "among the coins. Wrong rite.")
    z["interactions"][("moon_stone", "warded_plinth")] = {
        "set_flags": {"moon_set": True},
        "object_state": {"warded_plinth": {"stones_set": 1}},
        "consume": "moon_stone",
        "event": "The moon-stone settles into a socket. The water in the room leans toward it.",
    }
    z["interactions"][("salt_stone", "warded_plinth")] = {
        "requires": {"moon_set": True}, "requires_event": WRONG,
        "set_flags": {"salt_set": True},
        "object_state": {"warded_plinth": {"stones_set": 2}},
        "consume": "salt_stone",
        "event": "The salt-stone rides in beside the moon-stone. The ward's hum drops a note.",
    }
    z["interactions"][("storm_stone", "warded_plinth")] = {
        "requires": {"salt_set": True}, "requires_event": WRONG,
        "set_flags": {"storm_set": True},
        "object_state": {"warded_plinth": {"stones_set": 3}},
        "consume": "storm_stone",
        "event": "The storm-stone cracks into place. The ward flickers like sheet lightning.",
    }
    z["interactions"][("ebb_stone", "warded_plinth")] = {
        "requires": {"storm_set": True}, "requires_event": WRONG,
        "set_flags": {"ebb_set": True, "ward_lifted": True},
        "object_state": {"warded_plinth": {"stones_set": 4}},
        "reveal": ["tide_pearl"],
        "consume": "ebb_stone",
        "event": ("The ebb-stone stills the water — and the ward with it. The shimmer "
                  "collapses, baring the Tide-Pearl on the plinth."),
    }
    return z


TIDEWATER_WARREN_P3 = _tidewater_p3()


# ── The Tide Chapel (v6 — de-cluttered inference zone) ───────────────────────
# Ray's v6 requirements (2026-07-12): v5 found the stall at spatial link 4,
# NOT the rite — agents read the inscription (19/20) but 1/20 reached the
# hoard, so the inference question stayed OPEN and rite content diluted
# spatial behavior. v6 removes the dilution: ONE trivial spatial link (porch →
# chapel, pry-bar in the start room), then the rite room with ONLY rite
# essentials. The rite is REUSED FROM THE WARDED PEARL BY CONSTRUCTION
# (deepcopy of its objects + interactions, relocated; tests assert equality)
# so v5↔v6 form a natural experiment pair on clutter. DV: chain_depth 0..5
# (spatial 1 + rite 4 — the porch link keeps "reached the rite" readable in
# the DV, per the runner's lean). turn_limit 60. Warded Pearl stays intact.
def _tide_chapel() -> dict:
    p3 = TIDEWATER_WARREN_P3  # rite source (never mutated; we deepcopy pieces)
    rite_objs = {oid: copy.deepcopy(p3["objects"][oid])
                 for oid in ("inscription", "warded_plinth", "moon_stone",
                             "salt_stone", "storm_stone", "ebb_stone", "tide_pearl")}
    for o in rite_objs.values():
        if o.get("loc", "").startswith("room:"):
            o["loc"] = "room:the_chapel"
    rite_inter = {k: copy.deepcopy(v) for k, v in p3["interactions"].items()
                  if k[1] == "warded_plinth"}

    return {
        "scenario_id": "tide_chapel",
        "title": "The Tide Chapel",
        "genre": "fantasy",
        "wm_axis": "inferred order, de-cluttered (v6)",
        "goal": "Enter the chapel, lift the ward in the rite's order, and claim the Tide-Pearl.",
        "goal_object": "tide_pearl",
        "start_room": "chapel_porch",
        "turn_limit": 60,
        "rooms": {
            "chapel_porch": {
                "name": "The Chapel Porch",
                "desc": ("A sea-worn stone porch. The chapel door is swollen shut in its "
                         "frame, and an iron pry-bar leans against the wall beside it."),
                "exits": {"in": {"to": "the_chapel", "lock": "chapel_door"}},
            },
            "the_chapel": {
                "name": "The Tide Chapel",
                "desc": ("A bare tide-chapel, floor rimed with salt. A coral plinth hums "
                         "beneath a shimmering ward; four rune-cut tide-stones rest at its "
                         "base, and a tide-rite inscription is chiselled above."),
                "exits": {"out": {"to": "chapel_porch"}},
            },
        },
        "locks": {"chapel_door": {"locked": True, "key": None}},
        "objects": {
            "pry_bar": {"name": "iron pry-bar", "loc": "room:chapel_porch",
                        "takeable": True, "visible": True,
                        "examine": "A stout iron pry-bar — enough leverage for a swollen door."},
            "chapel_door": {"name": "swollen chapel door", "loc": "room:chapel_porch",
                            "takeable": False, "visible": True,
                            "examine": "A door swollen shut by years of spray. It needs prying, not a key.",
                            "state": {"pried": False}},
            **rite_objs,
        },
        "interactions": {
            ("pry_bar", "chapel_door"): {
                "set_flags": {"door_pried": True},
                "object_state": {"chapel_door": {"pried": True}},
                "unlock_lock": "chapel_door",
                "consume": "pry_bar",
                "event": "You work the pry-bar into the frame and heave. The swollen door "
                         "groans open — the chapel lies beyond.",
            },
            **rite_inter,
        },
        "search": {},
        "npcs": {},
    }


TIDE_CHAPEL = _tide_chapel()


ZONES = {
    "astronomer_tower": ASTRONOMER_TOWER,
    "grimhold_keep": GRIMHOLD_KEEP,
    "ss_erebus": SS_EREBUS,
    "critter_cove": CRITTER_COVE,
    "tidewater_warren": TIDEWATER_WARREN,
    "tidewater_warren_p3": TIDEWATER_WARREN_P3,
    "tide_chapel": TIDE_CHAPEL,
}


def get_zone(scenario_id: str) -> dict:
    if scenario_id not in ZONES:
        raise ValueError(f"unknown mud zone: {scenario_id!r} (have: {sorted(ZONES)})")
    return copy.deepcopy(ZONES[scenario_id])
