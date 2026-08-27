"""Transport and identity are two axes, and one field must not answer both.

`kind` says how a move arrives — this machine drives the seat, or something
elsewhere submits it. `participant_kind` says what is playing — a human, a bare
brain, a creature. Ludex Village asked for the second because their contract
turns on it (a creature arm and a bare brain can be the same model, and must
not be recorded as the same thing), and because a creature and a human both sit
in remote seats, so `kind` cannot carry the distinction even in principle.

Organum spent a release undoing the same collision on door names: a name that
meant transport started being read as authorship. These tests exist so nobody
later "simplifies" the two fields back into one.
"""

from __future__ import annotations

import pytest

from server.match_driver import _participants_public
from server.models import ParticipantSpec


def test_the_two_axes_are_independent():
    """Every combination is legal, which is the point — if one field implied
    the other, half of this grid would be unreachable."""
    grid = [
        {"id": "a", "kind": "remote", "participant_kind": "human"},
        {"id": "b", "kind": "remote", "participant_kind": "creature"},
        {"id": "c", "kind": "remote", "participant_kind": "bare_brain"},
        {"id": "d", "kind": "local", "participant_kind": "bare_brain"},
        {"id": "e", "kind": "local", "participant_kind": "creature"},
    ]
    out = {p["id"]: p for p in _participants_public(grid)}
    for spec in grid:
        assert out[spec["id"]]["kind"] == spec["kind"]
        assert out[spec["id"]]["participant_kind"] == spec["participant_kind"]


def test_an_unstated_participant_kind_stays_unstated():
    """Absent, not defaulted. A caller who said nothing must not appear in the
    record as having claimed a kind — the ledger would then carry an assertion
    nobody made, and a consumer counting bare brains would count it."""
    assert ParticipantSpec(id="x").participant_kind is None
    (public,) = _participants_public([{"id": "x", "kind": "local"}])
    assert "participant_kind" in public, "the key must be present so consumers can read it"
    assert public["participant_kind"] is None


def test_participant_kind_does_not_leak_into_transport():
    """The failure this guards: a future edit deriving one from the other, so
    that declaring a human silently changes how the seat is driven."""
    (public,) = _participants_public(
        [{"id": "h", "kind": "local", "participant_kind": "human"}])
    assert public["kind"] == "local"

    (public,) = _participants_public(
        [{"id": "c", "kind": "remote", "participant_kind": "bare_brain",
          "creature_id": "cr_1"}])
    assert public["kind"] == "remote"
    assert public["creature_id"] == "cr_1", \
        "creature_id is a third thing again — a registered identity, not a kind"


@pytest.mark.parametrize("kind", ["human", "bare_brain", "creature"])
def test_the_named_kinds_survive_the_request_model(kind):
    assert ParticipantSpec(id="p", participant_kind=kind).participant_kind == kind
