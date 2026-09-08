"""The round must not depend on the operator's memory of which trees exist.

Twice in one week a hand-typed round pulled hub-ops and forgot the plaza.
These tests pin the property that replaced the memory: the facility's own
channel list is the plan, every door in it is pulled, a door never seen
starts from zero, and a tree the operator has no directory for yet is in the
plan rather than silently absent. A pull that fails must say so — an empty
"pulled" list from a dead connection would look exactly like a quiet day.
"""

from __future__ import annotations

import json
from pathlib import Path

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
