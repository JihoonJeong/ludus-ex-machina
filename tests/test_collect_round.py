"""The round must not depend on the operator's memory of which trees exist.

Twice in one week a hand-typed round pulled hub-ops and forgot the plaza.
These tests pin the property that replaced the memory: the facility's own
channel list is the plan, every door in it is pulled, a door never seen
starts from zero, and a tree the operator has no directory for yet is in the
plan rather than silently absent. A pull that fails must say so — an empty
"pulled" list from a dead connection would look exactly like a quiet day.
"""

from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

import pytest

from scripts import collect_round as cr
from scripts.collect_round import Pull, plan_pulls

CH = {
    "hub-ops": ["from-lxm", "from-ray"],
    "bbs-plaza": ["from-lxm", "from-ray"],
    "brand-new": ["from-ray"],
}


def _env(dest: Path, n: int, signer: str = "lab:ray") -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{n:03d}-envelope.json").write_text(
        json.dumps({"signer": {"id": signer, "key_id": "k1", "key_epoch": 1}}),
        encoding="utf-8")


def test_every_door_of_every_tree_is_planned_even_without_a_local_dir(tmp_path):
    plan = plan_pulls(CH, tmp_path, "from-lxm")
    assert {p.label for p in plan} == {
        "hub-ops/from-ray", "bbs-plaza/from-lxm", "bbs-plaza/from-ray", "brand-new/from-ray"}


def test_hub_ops_keeps_the_flat_layout_and_boards_get_their_own_tree(tmp_path):
    by = {p.label: p for p in plan_pulls(CH, tmp_path, "from-lxm")}
    assert by["hub-ops/from-ray"].dest == tmp_path / "inbox" / "from-ray"
    assert by["bbs-plaza/from-ray"].dest == tmp_path / "bbs-plaza" / "inbox" / "from-ray"


def test_own_hub_ops_door_is_skipped_but_own_board_door_is_read_back(tmp_path):
    labels = {p.label for p in plan_pulls(CH, tmp_path, "from-lxm")}
    assert "hub-ops/from-lxm" not in labels
    assert "bbs-plaza/from-lxm" in labels


def test_a_door_never_pulled_starts_from_zero_and_a_known_door_keeps_its_cursor(tmp_path):
    _env(tmp_path / "inbox" / "from-ray", 7)
    by = {p.label: p for p in plan_pulls(CH, tmp_path, "from-lxm")}
    assert by["hub-ops/from-ray"].since is None
    assert by["brand-new/from-ray"].since == "000"


def test_an_empty_local_dir_still_counts_as_never_pulled(tmp_path):
    (tmp_path / "brand-new" / "inbox" / "from-ray").mkdir(parents=True)
    by = {p.label: p for p in plan_pulls(CH, tmp_path, "from-lxm")}
    assert by["brand-new/from-ray"].since == "000"


def test_audit_covers_every_tree_that_has_an_inbox_and_forwards_gaps(tmp_path):
    _env(tmp_path / "inbox" / "from-ray", 1)
    _env(tmp_path / "inbox" / "from-ray", 3)          # 2 is missing
    _env(tmp_path / "bbs-plaza" / "inbox" / "from-ray", 1)
    audits = cr.audit_trees(CH, tmp_path)
    assert set(audits) == {"hub-ops", "bbs-plaza"}    # brand-new has no inbox yet
    assert audits["hub-ops"]["new_gaps"] == [{"door": "from-ray", "seq": 2}]
    assert audits["bbs-plaza"]["new_gaps"] == []


def test_headline_reads_a_markdown_title_and_a_board_event(tmp_path):
    md = tmp_path / "001-body.md"
    md.write_text("\n\n# [회신] hello\nbody", encoding="utf-8")
    assert cr.headline(md) == "# [회신] hello"
    js = tmp_path / "002-body.json"
    js.write_text(json.dumps({"kind": "board.post", "post_id": "x-1",
                              "reply_to": "p-4", "text": "first line\nsecond"}),
                  encoding="utf-8")
    assert cr.headline(js) == "board.post x-1 re=p-4 first line"


def test_a_pull_that_dies_is_a_failure_not_a_quiet_day(tmp_path):
    fake = tmp_path / "hub"
    fake.write_text("#!/bin/sh\necho 'TLS EOF' >&2\nexit 1\n")
    fake.chmod(0o755)
    p = Pull("hub-ops", "from-ray", tmp_path / "inbox" / "from-ray", None)
    pulled, err = cr.run_pull(fake, "https://x", tmp_path / "tok", 5, p)
    assert pulled == []
    assert err is not None and "TLS EOF" in err


def test_a_pull_that_answers_in_json_reports_its_numbers_and_passes_since(tmp_path):
    fake = tmp_path / "hub"
    fake.write_text('#!/bin/sh\necho "$@" > "$(dirname "$0")/argv"\n'
                    'echo \'{"pulled": ["004", "005"], "dest": "x"}\'\n')
    fake.chmod(0o755)
    p = Pull("brand-new", "from-ray", tmp_path / "brand-new" / "inbox" / "from-ray", "000")
    pulled, err = cr.run_pull(fake, "https://x", tmp_path / "tok", 5, p)
    assert (pulled, err) == (["004", "005"], None)
    argv = (tmp_path / "argv").read_text()
    assert "--since 000" in argv and "--no-warmup" in argv
    assert "https://x/v0/brand-new/from-ray" in argv


def test_headline_names_a_creature_letters_author_and_recipient(tmp_path):
    js = tmp_path / "001-body.json"
    js.write_text(json.dumps({"kind": "creature.letter", "author": {"lab": "lab:ludex", "id": "Ohn", "epoch": 1},
                              "to": {"lab_id": "lab:ludex-village", "to_id": "Moss", "to_epoch": 1},
                              "text": "hello Moss\nsecond line"}), encoding="utf-8")
    assert cr.headline(js) == "creature.letter lab:ludex/Ohn -> lab:ludex-village/Moss no-voice hello Moss"


def test_a_letters_tree_is_pulled_into_its_own_state_tree(tmp_path):
    plan = cr.plan_pulls({"hub-ops": ["from-ludex", "from-lxm"], "letters": ["from-ludex"]}, tmp_path, "from-lxm")
    labels = {p.label: p for p in plan}
    assert "letters/from-ludex" in labels and "hub-ops/from-lxm" not in labels
    assert labels["letters/from-ludex"].dest == tmp_path / "letters" / "inbox" / "from-ludex"
    assert labels["letters/from-ludex"].since == "000"          # a door never pulled starts at 000


# ── asking again for numbers below the door's maximum ───────────────────────
# The pull's cursor is the local maximum. hub-ops/from-ludex 026 and 027 were
# written after a stray 037 had raised that maximum, and no round ever asked
# for them: 39 days on the drop, absent here, and inside a range the audit had
# already explained as phantom.

def _quad(n: int, body: bytes | None = b"# title\n", signer: str = "lab:ray") -> dict:
    env = json.dumps({"signer": {"id": signer}, "seq": n}).encode()
    q = {"n": f"{n:03d}", "envelope_b64": base64.b64encode(env).decode(), "sig": f"{n:02x}" * 64}
    if body is not None:
        q |= {"body_name": "body.md", "body_b64": base64.b64encode(body).decode()}
    return q


class _Door:
    """A door that answers ?since= the way the drop does: ascending, 20 a page."""

    def __init__(self, numbers, signer: str = "lab:ray"):
        self.quads, self.asked = {n: _quad(n, signer=signer) for n in numbers}, []

    def fetch(self, since: str) -> dict:
        self.asked.append(since)
        later = [self.quads[n] for n in sorted(self.quads) if n > int(since)]
        return {"quads": later[:20], "more": len(later) > 20}


def test_hole_ranges_start_at_001_and_group_runs(tmp_path):
    for n in (3, 4, 7, 8, 12):
        _env(tmp_path, n)
    assert cr.hole_ranges(tmp_path) == [(1, 2), (5, 6), (9, 11)]
    assert cr.hole_ranges(tmp_path / "never-pulled") == []


def test_a_number_that_arrived_below_the_maximum_is_fetched_and_written_like_a_pull(tmp_path):
    for n in (1, 2, 5):
        _env(tmp_path, n)
    door = _Door([1, 2, 3, 4, 5, 6])
    assert cr.probe_hole(door.fetch, tmp_path, 3, 4) == ["003", "004"]
    assert door.asked == ["002"]                                   # one request for the whole run
    assert json.loads((tmp_path / "003-envelope.json").read_text())["seq"] == 3
    assert (tmp_path / "003-sig.txt").read_text() == "03" * 64 + "\n"
    assert (tmp_path / "004-body.md").read_bytes() == b"# title\n"
    assert not (tmp_path / "006-envelope.json").exists()            # above the hole is the pull's business
    assert cr.hole_ranges(tmp_path) == []


def test_a_hole_the_door_does_not_have_either_costs_one_request_and_writes_nothing(tmp_path):
    for n in (1, 2, 5):
        _env(tmp_path, n)
    before = sorted(f.name for f in tmp_path.iterdir())
    door = _Door([1, 2, 5, 6])
    assert cr.probe_hole(door.fetch, tmp_path, 3, 4) == []
    assert door.asked == ["002"] and sorted(f.name for f in tmp_path.iterdir()) == before


def test_a_hole_longer_than_a_page_is_followed_to_its_end_and_no_further(tmp_path):
    _env(tmp_path, 1)
    _env(tmp_path, 60)
    door = _Door(range(1, 91))
    filled = cr.probe_hole(door.fetch, tmp_path, 2, 59)
    assert filled == [f"{n:03d}" for n in range(2, 60)]
    assert door.asked == ["001", "021", "041"]                      # stops on the page that passes 059
    assert not (tmp_path / "061-envelope.json").exists()


def test_a_quad_without_a_body_is_two_files(tmp_path):
    _env(tmp_path, 2)
    door = _Door([])
    door.quads = {1: _quad(1, body=None), 2: _quad(2)}
    assert cr.probe_hole(door.fetch, tmp_path, 1, 1) == ["001"]
    assert sorted(f.name for f in tmp_path.glob("001-*")) == ["001-envelope.json", "001-sig.txt"]


@pytest.mark.parametrize("bad", [{"n": "3"}, {"n": "003\n"}, {"n": "001"}, {"body_name": "../x"}, {"body_name": "body.md\n"}])
def test_a_door_that_answers_out_of_shape_is_an_error_and_nothing_is_written(tmp_path, bad):
    _env(tmp_path, 1)
    _env(tmp_path, 5)
    before = sorted(f.name for f in tmp_path.iterdir())
    with pytest.raises(ValueError):
        cr.probe_hole(lambda since: {"quads": [_quad(3) | bad], "more": False}, tmp_path, 2, 4)
    assert sorted(f.name for f in tmp_path.iterdir()) == before


def test_the_round_asks_explained_holes_too_and_reports_what_came_late(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state"
    for n in list(range(1, 26)) + [37, 38]:                         # the 2026-10-04 shape of from-ludex
        _env(state / "inbox" / "from-ludex", n, signer="lab:ludex")
    door = _Door(list(range(1, 28)) + [37, 38], signer="lab:ludex")  # 026 and 027 are on the drop
    monkeypatch.setattr(cr, "fetch_channels", lambda *a: {"hub-ops": ["from-ludex", "from-lxm"]})
    monkeypatch.setattr(cr, "run_pull", lambda *a: ([], None))      # nothing above the maximum
    monkeypatch.setattr(cr, "door_fetcher", lambda *a: door.fetch)
    monkeypatch.setattr("sys.argv", ["collect_round.py", "--state", str(state)])
    rc = cr.main()
    out = capsys.readouterr().out
    assert door.asked == ["025"]
    assert "026-036   LATE 026 027" in out
    assert "hub-ops/from-ludex/026 (late, below the maximum)" in out
    assert cr.hole_ranges(state / "inbox" / "from-ludex") == [(28, 36)]
    assert rc == 0                                                  # 028-036 stays explained


def test_a_probe_that_dies_fails_the_round_and_holes_past_the_budget_are_named(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state"
    for n in (1, 3, 5, 7):
        _env(state / "inbox" / "from-ray", n)

    def dead(since):
        raise OSError("connection reset")
    monkeypatch.setattr(cr, "fetch_channels", lambda *a: {"hub-ops": ["from-ray"]})
    monkeypatch.setattr(cr, "run_pull", lambda *a: ([], None))
    monkeypatch.setattr(cr, "door_fetcher", lambda *a: dead)
    monkeypatch.setattr("sys.argv", ["collect_round.py", "--state", str(state), "--max-probes", "2"])
    assert cr.main() == 1
    out = capsys.readouterr().out
    assert out.count("FAILED: OSError: connection reset") == 2
    assert "006       not asked this round (--max-probes 2)" in out


def test_a_door_whose_pull_failed_is_not_probed(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state"
    for n in (1, 3):
        _env(state / "inbox" / "from-ray", n)
    monkeypatch.setattr(cr, "fetch_channels", lambda *a: {"hub-ops": ["from-ray"]})
    monkeypatch.setattr(cr, "run_pull", lambda *a: ([], "TLS EOF"))
    monkeypatch.setattr(cr, "door_fetcher", lambda *a: pytest.fail("probed a door that did not answer"))
    monkeypatch.setattr("sys.argv", ["collect_round.py", "--state", str(state)])
    assert cr.main() == 1
    assert "probe: 0 hole range(s)" in capsys.readouterr().out


def test_against_a_real_drop_the_late_number_lands_byte_for_byte_as_the_client_writes_it(tmp_path):
    """The format is the client's, so the client is the oracle: a late quad
    fetched by the probe must equal the same quad pulled fresh by organum."""
    hub_drop = pytest.importorskip("organum.hub_drop")
    (tmp_path / "tokens.txt").write_text("probe-test-token\n")
    srv = hub_drop.make_server(tmp_path / "root", tmp_path / "tokens.txt", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/v0/hub-ops/from-ray"

        def post(n, body):
            hub_drop._request(url, "probe-test-token", json.dumps(_quad(n, body)).encode(), timeout=10)

        post(1, b"one\n"); post(4, None)
        ours = tmp_path / "ours"
        assert hub_drop.pull_quads(url, "probe-test-token", ours, warmup=False) == ["001", "004"]
        post(2, b"late, with a body\n"); post(3, None)                # below the maximum, after the pull
        assert hub_drop.pull_quads(url, "probe-test-token", ours, warmup=False) == []   # the cursor never looks back
        assert cr.hole_ranges(ours) == [(2, 3)]

        fetch = cr.door_fetcher(f"http://127.0.0.1:{srv.server_address[1]}", tmp_path / "tokens.txt", 10,
                                Pull("hub-ops", "from-ray", ours, None))
        assert cr.probe_hole(fetch, ours, 2, 3) == ["002", "003"]

        fresh = tmp_path / "fresh"
        hub_drop.pull_quads(url, "probe-test-token", fresh, since="000", warmup=False)
        assert {f.name: f.read_bytes() for f in ours.iterdir()} == {f.name: f.read_bytes() for f in fresh.iterdir()}
    finally:
        srv.shutdown(); srv.server_close()
