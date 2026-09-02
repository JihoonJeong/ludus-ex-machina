"""The door audit must stay loud about what it has not already explained.

Its danger is the opposite of its purpose. An audit that suppresses known
findings drifts toward suppressing everything: widen a known range by one,
mark a door as expected-messy, and the first real loss arrives already
silenced. So the tests here mostly attack the allow-list — a new gap adjacent
to a known one must still shout, and an explained finding must remain visible
in the report rather than disappearing from it.
"""

from __future__ import annotations

import json

import pytest

from scripts import door_audit
from scripts.door_audit import scan


def _door(tmp_path, side, name, entries):
    """entries: {seq: signer_id}. Writes minimal envelope quads."""
    d = tmp_path / side / name
    d.mkdir(parents=True, exist_ok=True)
    for seq, signer in entries.items():
        (d / f"{seq:03d}-envelope.json").write_text(
            json.dumps({"signer": {"id": signer, "key_id": "k1", "key_epoch": 1}}),
            encoding="utf-8")
    return d


def test_a_clean_door_reports_nothing_new(tmp_path):
    _door(tmp_path, "inbox", "from-alpha", {1: "lab:alpha", 2: "lab:alpha"})
    r = scan(tmp_path)
    assert r["new_foreign"] == [] and r["new_gaps"] == []
    assert r["doors"]["from-alpha"]["holes"] == []


def test_a_foreign_envelope_is_caught(tmp_path):
    _door(tmp_path, "inbox", "from-alpha", {1: "lab:alpha", 2: "lab:beta"})
    r = scan(tmp_path)
    assert r["new_foreign"] == [
        {"door": "from-alpha", "seq": 2, "signer": "lab:beta", "expected": "lab:alpha"}]


def test_a_missing_middle_number_is_caught(tmp_path):
    _door(tmp_path, "inbox", "from-alpha", {1: "lab:alpha", 3: "lab:alpha"})
    r = scan(tmp_path)
    assert r["new_gaps"] == [{"door": "from-alpha", "seq": 2}]


def test_a_known_gap_is_reported_but_not_raised(tmp_path, monkeypatch):
    monkeypatch.setitem(door_audit.KNOWN_GAPS, "from-alpha", [(2, 2, "explained")])
    _door(tmp_path, "inbox", "from-alpha", {1: "lab:alpha", 3: "lab:alpha"})
    r = scan(tmp_path)
    assert r["new_gaps"] == [], "an explained gap must not cry wolf"
    assert r["doors"]["from-alpha"]["holes"] == [2], \
        "but it must stay in the report — a suppressed finding is an invisible one"


def test_a_new_gap_beside_a_known_one_still_shouts(tmp_path, monkeypatch):
    """The failure this guards: a known range quietly absorbing its neighbours,
    so the door that already had an explanation stops being audited at all."""
    monkeypatch.setitem(door_audit.KNOWN_GAPS, "from-alpha", [(2, 2, "explained")])
    _door(tmp_path, "inbox", "from-alpha", {1: "lab:alpha", 5: "lab:alpha"})
    r = scan(tmp_path)
    assert [g["seq"] for g in r["new_gaps"]] == [3, 4]


def test_a_known_foreign_envelope_does_not_excuse_its_neighbour(tmp_path, monkeypatch):
    monkeypatch.setitem(door_audit.KNOWN_FOREIGN, ("from-alpha", 2), "explained")
    _door(tmp_path, "inbox", "from-alpha",
          {1: "lab:alpha", 2: "lab:beta", 3: "lab:beta"})
    r = scan(tmp_path)
    assert [f["seq"] for f in r["new_foreign"]] == [3]
    assert len(r["doors"]["from-alpha"]["foreign"]) == 2, "both stay visible"


def test_an_unreadable_envelope_is_a_finding_not_a_skip(tmp_path):
    """Corruption must not read as absence. A file that cannot be parsed is
    exactly when a door most needs to be noisy."""
    d = _door(tmp_path, "inbox", "from-alpha", {1: "lab:alpha"})
    (d / "002-envelope.json").write_text("{not json", encoding="utf-8")
    r = scan(tmp_path)
    assert [f["seq"] for f in r["new_foreign"]] == [2]
    assert r["doors"]["from-alpha"]["holes"] == [], "002 exists; it is broken, not missing"


def test_our_own_outbox_is_audited_too(tmp_path):
    """The host is not exempt. If from-lxm ever carried someone else's envelope
    we would want to hear it from our own instrument first."""
    _door(tmp_path, "inbox", "from-alpha", {1: "lab:alpha"})
    _door(tmp_path, "outbox", "from-lxm", {1: "lab:lxm", 2: "lab:ludex"})
    r = scan(tmp_path)
    assert "from-lxm" in r["doors"]
    assert [f["door"] for f in r["new_foreign"]] == ["from-lxm"]


@pytest.mark.parametrize("seq,expected", [(25, False), (26, True), (36, True), (37, False)])
def test_the_shipped_phantom_range_covers_exactly_what_it_says(seq, expected):
    """The real allow-list, not a fixture: the 08-26 incident left 026-036 of
    from-ludex explained. One number either side must remain auditable."""
    assert door_audit._explained("from-ludex", seq) is expected


# The 09-02 incident: four envelopes signed with lab:ludex's real key, on its
# real machine, by an agent Ludex never delegated. The class is invisible to
# every check this instrument has — which is precisely why KNOWN_VOID exists,
# and why these tests pin the record rather than a detector.


def test_a_void_class_envelope_raises_nothing_which_is_why_the_table_exists(tmp_path):
    """The defining property: genuine signature in its own door, so the scan
    is silent. If this test ever fails, the instrument learned to detect the
    class and the table can retire into a detector's allow-list."""
    _door(tmp_path, "inbox", "from-ludex",
          {75: "lab:ludex", 76: "lab:ludex", 77: "lab:ludex",
           78: "lab:ludex", 79: "lab:ludex"})
    r = scan(tmp_path)
    assert r["new_foreign"] == [] and r["new_gaps"] == []


def test_the_shipped_void_table_holds_exactly_the_confessed_four():
    """Maru's confession names 076-079 and nothing else. A table that widens
    quietly voids someone's real mail; one that shrinks forgets the incident."""
    assert set(door_audit.KNOWN_VOID) == {("from-ludex", n) for n in (76, 77, 78, 79)}


def test_void_entries_print_every_round_and_do_not_dirty_the_report(tmp_path, capsys, monkeypatch):
    """Visibility without alarm: the record must appear in both output modes,
    and must not flip the exit code — it is explained history, not a finding."""
    import sys
    _door(tmp_path, "inbox", "from-ludex", {76: "lab:ludex"})
    monkeypatch.setattr(sys, "argv", ["door_audit.py", "--state", str(tmp_path)])
    assert door_audit.main() == 0
    out = capsys.readouterr().out
    assert "076 VOID" in out and "no authority" in out

    monkeypatch.setattr(sys, "argv", ["door_audit.py", "--state", str(tmp_path), "--json"])
    assert door_audit.main() == 0
    j = json.loads(capsys.readouterr().out)
    assert j["clean"] is True
    assert {"door": "from-ludex", "seq": 76,
            "why": door_audit.KNOWN_VOID[("from-ludex", 76)]} in j["void"]
