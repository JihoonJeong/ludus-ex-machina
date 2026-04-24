"""D-062 Phase 2b.1 tests for the LxM-side reach orchestrator stub.

Covers the drive loop (pull → pointer check → prompt read → response
write → commit/push) via monkeypatched filesystem and git helpers,
plus two regression gates Ray flagged from the Ludex side:

  (G1) `turn.yaml` uses a *nested* `next:` block — a hand-rolled flat
       parser misses it. These tests exercise PyYAML end-to-end.
  (G2) `meta.yaml.status != "active"` ends the session. Same fragile
       parser category.

Mirror of Ludex's `tests/test_reach_orchestrator.py` (c44117d). The
LxM side keeps a narrower scope: the response function is injected,
so we only test the surrounding loop, not response generation.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
import pytest
import yaml

from lxm.reach_orchestrator import (
    OrchestratorConfig,
    ReachOrchestrator,
)


def _mk_pointer(turn: int, next_creature: str, prompt_available: bool):
    """Test double for ludex.reach.schema_io.TurnPointer.

    The real TurnPointer is a dataclass with these fields (and more);
    SimpleNamespace gives attribute access without the Ludex import.
    """
    return SimpleNamespace(
        turn=turn,
        next_creature=next_creature,
        prompt_available=prompt_available,
    )


# ── fixtures ───────────────────────────────────────────────────────────────


TURN_YAML_NESTED = """\
turn: 3
next:
  creature: Primo
  machine_id: 34d41615-1642-4094-be71-05024185149d
  machine_alias: mac-studio-001
prompt_available: true
"""


META_YAML_ACTIVE = """\
session_id: reach_2026-04-24_hearth_primo_test_001
field: Council
participants:
  - creature: Hearth
    machine_alias: win-nautilus-001
  - creature: Primo
    machine_alias: mac-studio-001
status: active
"""


META_YAML_CLOSED = META_YAML_ACTIVE.replace("status: active", "status: closed")


@pytest.fixture
def session_dir(tmp_path: Path) -> Path:
    """A bare session directory with meta.yaml (active) and turn.yaml."""
    root = tmp_path
    sdir = root / "sessions" / "reach_2026-04-24_hearth_primo_test_001"
    (sdir / "prompts").mkdir(parents=True)
    (sdir / "responses").mkdir(parents=True)
    (sdir / "meta.yaml").write_text(META_YAML_ACTIVE, encoding="utf-8")
    (sdir / "turn.yaml").write_text(TURN_YAML_NESTED, encoding="utf-8")
    return root


@pytest.fixture
def orch(session_dir: Path) -> ReachOrchestrator:
    return ReachOrchestrator(
        repo_root=session_dir,
        session_id="reach_2026-04-24_hearth_primo_test_001",
        local_creature="Primo",
        local_machine_id="34d41615-1642-4094-be71-05024185149d",
        machine_alias="mac-studio-001",
        response_fn=lambda body: f"response to: {body[:40]}",
        config=OrchestratorConfig(poll_interval_seconds=0.0, idle_grace_seconds=60.0),
    )


# ── regression gate G1: nested `next:` block shape ─────────────────────────


def test_g1_nested_next_block_parses_via_pyyaml():
    """PyYAML loads turn.yaml into the nested shape Ray's TurnPointer
    fix (55c8182) requires. A flat parser would lose the next.creature
    field. Covers the regression Ray flagged in cli_done_20260424.md §1."""
    parsed = yaml.safe_load(TURN_YAML_NESTED)
    assert parsed["turn"] == 3
    assert isinstance(parsed["next"], dict)
    assert parsed["next"]["creature"] == "Primo"
    assert parsed["next"]["machine_alias"] == "mac-studio-001"
    assert parsed["prompt_available"] is True


# ── regression gate G2: meta.yaml.status determines close ──────────────────


def test_g2_is_closed_when_status_is_closed(session_dir: Path, orch: ReachOrchestrator):
    (session_dir / "sessions" / orch.session_id / "meta.yaml").write_text(
        META_YAML_CLOSED, encoding="utf-8"
    )
    assert orch._is_session_closed() is True


def test_g2_not_closed_when_status_is_active(orch: ReachOrchestrator):
    assert orch._is_session_closed() is False


def test_g2_closed_when_any_close_file_present(session_dir: Path, orch: ReachOrchestrator):
    (session_dir / "sessions" / orch.session_id / "close_Primo_mac-studio-001.md").write_text(
        "---\nreason: explicit_retract\n---\n", encoding="utf-8"
    )
    assert orch._is_session_closed() is True


def test_g2_not_closed_when_session_dir_missing(tmp_path: Path):
    orch = ReachOrchestrator(
        repo_root=tmp_path,
        session_id="reach_does_not_exist",
        local_creature="X",
        local_machine_id="xxx",
        response_fn=lambda b: "",
    )
    assert orch._is_session_closed() is False


# ── drive loop: _tick via monkeypatched FS + git helpers ───────────────────


def _install_monkeypatches(monkeypatch, orch: ReachOrchestrator, *,
                           pointer, prompt: str | None,
                           write_sink: list):
    """Swap the thin schema_io wrappers + git shell-outs for test
    doubles so the drive loop is exercised in isolation (no Ludex
    import at test time, no filesystem writes, no git calls).

    `pointer` is either None or anything with `.turn`, `.next_creature`,
    `.prompt_available` attributes — SimpleNamespace works (`_mk_pointer`)
    and the real `TurnPointer` dataclass does too."""
    record = {"pulled": 0, "committed": [], "wrote": []}

    def fake_pull():
        record["pulled"] += 1

    def fake_read_pointer():
        return pointer

    def fake_read_prompt(turn_no: int):
        return prompt

    def fake_write(turn_no: int, body: str, prompt_body_for_digest=None):
        record["wrote"].append({
            "turn": turn_no,
            "body": body,
            "prompt_digest_src": prompt_body_for_digest,
        })
        write_sink.append(body)

    def fake_commit_push(message: str):
        record["committed"].append(message)

    monkeypatch.setattr(orch, "_git_pull", fake_pull)
    monkeypatch.setattr(orch, "_read_turn_pointer", fake_read_pointer)
    monkeypatch.setattr(orch, "_read_prompt_body", fake_read_prompt)
    monkeypatch.setattr(orch, "_write_response", fake_write)
    monkeypatch.setattr(orch, "_git_commit_push", fake_commit_push)
    return record


def test_tick_answers_when_pointer_matches_local_creature(
    monkeypatch, orch: ReachOrchestrator
):
    sink: list[str] = []
    record = _install_monkeypatches(
        monkeypatch, orch,
        pointer=_mk_pointer(turn=3, next_creature="Primo", prompt_available=True),
        prompt="What brings you here?",
        write_sink=sink,
    )

    assert orch._tick() is True
    assert record["pulled"] == 1
    assert len(record["wrote"]) == 1
    assert record["wrote"][0]["turn"] == 3
    assert "What brings you here" in record["wrote"][0]["body"]
    assert len(record["committed"]) == 1
    assert "turn 3" in record["committed"][0]
    assert 3 in orch._answered_turns


def test_tick_skips_when_not_my_turn(monkeypatch, orch: ReachOrchestrator):
    sink: list[str] = []
    record = _install_monkeypatches(
        monkeypatch, orch,
        pointer=_mk_pointer(turn=3, next_creature="Hearth", prompt_available=True),
        prompt="ignored",
        write_sink=sink,
    )

    assert orch._tick() is False
    assert record["wrote"] == []
    assert record["committed"] == []
    assert 3 not in orch._answered_turns


def test_tick_skips_when_prompt_unavailable(monkeypatch, orch: ReachOrchestrator):
    sink: list[str] = []
    record = _install_monkeypatches(
        monkeypatch, orch,
        pointer=_mk_pointer(turn=3, next_creature="Primo", prompt_available=False),
        prompt=None,
        write_sink=sink,
    )

    assert orch._tick() is False
    assert record["wrote"] == []


def test_tick_skips_when_pointer_missing(monkeypatch, orch: ReachOrchestrator):
    sink: list[str] = []
    record = _install_monkeypatches(
        monkeypatch, orch,
        pointer=None,
        prompt=None,
        write_sink=sink,
    )

    assert orch._tick() is False
    assert record["wrote"] == []


def test_tick_does_not_double_answer_same_turn(monkeypatch, orch: ReachOrchestrator):
    sink: list[str] = []
    record = _install_monkeypatches(
        monkeypatch, orch,
        pointer=_mk_pointer(turn=3, next_creature="Primo", prompt_available=True),
        prompt="one",
        write_sink=sink,
    )

    assert orch._tick() is True
    assert orch._tick() is False  # same turn, already answered
    assert len(record["wrote"]) == 1
    assert len(record["committed"]) == 1


def test_tick_skips_when_prompt_body_is_none(monkeypatch, orch: ReachOrchestrator):
    sink: list[str] = []
    record = _install_monkeypatches(
        monkeypatch, orch,
        pointer=_mk_pointer(turn=3, next_creature="Primo", prompt_available=True),
        prompt=None,
        write_sink=sink,
    )

    assert orch._tick() is False
    assert record["wrote"] == []


# ── response_fn contract ───────────────────────────────────────────────────


def test_response_fn_receives_prompt_body(monkeypatch, session_dir: Path):
    seen: list[str] = []
    orch = ReachOrchestrator(
        repo_root=session_dir,
        session_id="reach_2026-04-24_hearth_primo_test_001",
        local_creature="Primo",
        local_machine_id="34d41615-1642-4094-be71-05024185149d",
        response_fn=lambda body: (seen.append(body), f"echo:{body}")[1],
    )
    _install_monkeypatches(
        monkeypatch, orch,
        pointer=_mk_pointer(turn=1, next_creature="Primo", prompt_available=True),
        prompt="hello there",
        write_sink=[],
    )
    orch._tick()
    assert seen == ["hello there"]


def test_write_response_receives_prompt_body_for_digest(
    monkeypatch, orch: ReachOrchestrator
):
    """The answered prompt body flows through to write_response's
    prompt_body_for_digest so schema_io can compute prompt_digest
    provenance (schema §2.3). Confirmed via the thin wrapper."""
    sink: list[str] = []
    record = _install_monkeypatches(
        monkeypatch, orch,
        pointer=_mk_pointer(turn=4, next_creature="Primo", prompt_available=True),
        prompt="original prompt text",
        write_sink=sink,
    )
    assert orch._tick() is True
    assert record["wrote"][0]["prompt_digest_src"] == "original prompt text"
