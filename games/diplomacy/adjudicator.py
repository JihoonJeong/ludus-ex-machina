"""Diplomacy order resolution (armies only, no convoys).

Pure function: given the units on the board and one order per unit, compute the
simultaneous outcome — who moves, who bounces, who is dislodged. Kept separate from
the engine so it can be unit-tested in isolation against the standard cases
(supported attacks, standoffs, support-cutting, head-to-head swaps, rotations).

Order shapes (already normalised by the engine):
  {"type": "hold"}
  {"type": "move",    "dest": "<province>"}
  {"type": "support", "target": "<province>", "from": "<origin>" | None}
      from=None  -> support the unit HOLDING at `target`
      from=<o>   -> support the move <o> -> <target>

resolve() returns:
  {
    "positions": {province: owner},        # board after movement (dislodged units removed)
    "dislodged": {origin: {owner, attacker_from, forbidden}},  # units that must retreat
    "outcomes":  {origin: "move"|"bounce"|"hold"|"support"|"support-cut"},
    "standoffs": set(provinces that bounced),  # illegal retreat targets
  }

Without convoys the only order interdependencies are movement chains, head-to-head
swaps, and rotations — all handled by the recursive resolver below. A unit may never
dislodge a unit of its own power (such an attack simply bounces).
"""

from __future__ import annotations

from .world import ADJACENCY


def _normalize(units: dict, orders: dict) -> dict:
    """Every unit gets exactly one order; anything missing/malformed becomes a hold."""
    out = {}
    for prov in units:
        o = orders.get(prov)
        if not isinstance(o, dict):
            out[prov] = {"type": "hold"}
            continue
        t = o.get("type")
        if t == "move" and o.get("dest") in ADJACENCY.get(prov, ()):
            out[prov] = {"type": "move", "dest": o["dest"]}
        elif t == "support":
            out[prov] = {"type": "support", "target": o.get("target"), "from": o.get("from")}
        else:
            out[prov] = {"type": "hold"}
    return out


def resolve(units: dict, orders: dict) -> dict:
    units = dict(units)
    order = _normalize(units, orders)

    moves = {p: o["dest"] for p, o in order.items() if o["type"] == "move"}
    supports = {p: o for p, o in order.items() if o["type"] == "support"}

    # --- 1) support legality + cutting -------------------------------------
    # A support is valid only if the supporter borders the province it supports into.
    # A support is cut if the supporter is attacked from any province other than the
    # one its support is directed at (the target).
    cut = set()
    invalid = set()
    for sp, so in supports.items():
        target = so["target"]
        if target not in ADJACENCY.get(sp, ()):
            invalid.add(sp)  # can't support into a province you don't border
            continue
        for m_origin, m_dest in moves.items():
            if m_dest == sp and m_origin != target:
                cut.add(sp)
                break

    def supports_for_move(frm, dest):
        return sum(
            1 for sp, so in supports.items()
            if sp not in cut and sp not in invalid
            and so["from"] == frm and so["target"] == dest
        )

    def supports_for_hold(at):
        return sum(
            1 for sp, so in supports.items()
            if sp not in cut and sp not in invalid
            and so["from"] is None and so["target"] == at
        )

    move_strength = {o: 1 + supports_for_move(o, d) for o, d in moves.items()}

    def hold_strength(prov):
        return 1 + supports_for_hold(prov)

    # --- 2) resolve moves (recursive, with cycle handling) ------------------
    outcome: dict[str, str] = {}   # move origin -> "move" | "bounce"
    visiting: set[str] = set()

    def succeeds(origin: str) -> bool:
        if origin in outcome:
            return outcome[origin] == "move"
        if origin in visiting:
            return True  # part of a rotation cycle -> provisionally vacates
        visiting.add(origin)
        dest = moves[origin]
        mine = move_strength[origin]

        verdict = "move"
        # must strictly beat every other unit also moving into dest
        for other, odest in moves.items():
            if other != origin and odest == dest and move_strength[other] >= mine:
                verdict = "bounce"
                break

        if verdict == "move":
            occupant = units.get(dest)
            if occupant is not None:
                head_to_head = moves.get(dest) == origin  # dest's unit moving to my origin
                if head_to_head:
                    if mine <= move_strength[dest]:
                        verdict = "bounce"
                    elif occupant == units[origin]:
                        verdict = "bounce"  # may not dislodge own unit
                elif dest in moves and succeeds(dest):
                    pass  # occupant vacates -> dest is free
                else:
                    # occupant stays and defends in place
                    if occupant == units[origin]:
                        verdict = "bounce"  # own unit, can't self-dislodge
                    elif mine <= hold_strength(dest):
                        verdict = "bounce"

        visiting.discard(origin)
        outcome[origin] = verdict
        return verdict == "move"

    for o in list(moves):
        succeeds(o)

    # --- 3) build new positions + dislodgements -----------------------------
    successful = {o: moves[o] for o in moves if outcome[o] == "move"}
    incoming = {dest: o for o, dest in successful.items()}  # winner per destination

    # provinces where ≥2 units tried to enter but none succeeded → standoff
    standoffs = set()
    dest_movers: dict[str, list[str]] = {}
    for o, d in moves.items():
        dest_movers.setdefault(d, []).append(o)
    for d, movers in dest_movers.items():
        if d not in incoming and (len(movers) > 1 or (units.get(d) is not None and outcome[movers[0]] == "bounce")):
            standoffs.add(d)

    positions: dict[str, str] = {}
    dislodged: dict[str, dict] = {}

    for prov, owner in units.items():
        if prov in successful:
            continue  # this unit left its province
        if prov in incoming:
            attacker_origin = incoming[prov]
            dislodged[prov] = {
                "owner": owner,
                "attacker_from": attacker_origin,
                "forbidden": set(),  # filled below
            }
        else:
            positions[prov] = owner

    for dest, origin in incoming.items():
        positions[dest] = units[origin]

    # retreat restrictions: can't go to attacker's origin, occupied, or standoff provinces
    for prov, info in dislodged.items():
        forbidden = set(standoffs)
        forbidden.add(info["attacker_from"])
        for nb in ADJACENCY.get(prov, ()):
            if nb in positions:
                forbidden.add(nb)
        info["forbidden"] = sorted(forbidden)  # JSON-serializable (was a set -> log crash)

    # --- 4) per-order human outcomes (for logging / rendering) --------------
    outcomes: dict[str, str] = {}
    for prov, o in order.items():
        if o["type"] == "move":
            outcomes[prov] = "move" if outcome[prov] == "move" else "bounce"
        elif o["type"] == "support":
            outcomes[prov] = "support-cut" if (prov in cut or prov in invalid) else "support"
        else:
            outcomes[prov] = "hold"

    return {
        "positions": positions,
        "dislodged": dislodged,
        "outcomes": outcomes,
        "standoffs": sorted(standoffs),
    }
