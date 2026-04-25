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

    def fake_advance(prev_pointer, body):
        record.setdefault("advanced", []).append(prev_pointer.turn)

    monkeypatch.setattr(orch, "_git_pull", fake_pull)
    monkeypatch.setattr(orch, "_read_turn_pointer", fake_read_pointer)
    monkeypatch.setattr(orch, "_read_prompt_body", fake_read_prompt)
    monkeypatch.setattr(orch, "_write_response", fake_write)
    monkeypatch.setattr(orch, "_git_commit_push", fake_commit_push)
    monkeypatch.setattr(orch, "_advance_after_response", fake_advance)
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


# ── Phase 2b.1.1 regression gates G3/G4/G5 ─────────────────────────────────


def test_g3_compose_next_prompt_avoids_v1_fail_format():
    """G3: `compose_next_prompt_body` (Phase 2b.1.1 §2.4.1) must never
    emit the R4.P v1 header-style framing that Hearth's haiku read as
    metadata-only. The peer body must arrive blockquoted, and the
    "<creature> (turn N, alias):" header from v1 must be absent."""
    from lxm.reach_orchestrator import _ensure_ludex_on_path
    _ensure_ludex_on_path()
    from ludex.reach.schema_io import compose_next_prompt_body
    body = compose_next_prompt_body(
        field_name="Council",
        peer_creature="Primo",
        peer_machine_alias="mac-studio-001",
        peer_response_body="*Primo speaks first*\n\nThe silence is the texture.",
        peer_turn_n=1,
        addressee_creature="Hearth",
        sentences=4,
    )
    assert "Primo (turn 1, mac-studio-001):" not in body
    assert "Primo (turn 1," not in body
    # Peer utterance must be blockquoted
    assert "> *Primo speaks first*" in body
    assert "> The silence is the texture." in body
    # Plain-prose framing wraps it
    assert "Council session with Primo" in body
    assert "Hearth — your turn." in body


def test_g4_lock_blocks_other_live_pid(tmp_path: Path):
    """G4: a lock file naming a different *live* PID blocks acquire
    with RuntimeError; same-PID re-acquire is idempotent."""
    from lxm.reach_orchestrator import _ensure_ludex_on_path
    _ensure_ludex_on_path()
    from ludex.reach.schema_io import (
        acquire_session_lock, release_session_lock, machine_slug,
    )
    sdir = tmp_path / "sessions" / "reach_test"
    sdir.mkdir(parents=True)
    import os
    my_pid = os.getpid()

    # Same-pid re-acquire is a no-op (idempotent).
    acquire_session_lock(sdir, creature="P", machine_id="m1", pid=my_pid)
    acquire_session_lock(sdir, creature="P", machine_id="m1", pid=my_pid)

    # Hand-write the lock to claim a different live PID (use parent
    # PID of the test process — guaranteed alive, guaranteed != ours).
    other_live_pid = os.getppid()
    assert other_live_pid != my_pid
    slug = machine_slug("", "m1")
    lock_file = sdir / f".orchestrator_P_{slug}.lock"
    lock_file.write_text(
        f"{other_live_pid} 2026-01-01T00:00:00Z P\n", encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="already running"):
        acquire_session_lock(sdir, creature="P", machine_id="m1", pid=my_pid)

    release_session_lock(sdir, creature="P", machine_id="m1")


def test_g4_lock_overwritten_when_held_pid_is_dead(tmp_path: Path):
    """A lock left behind by a hard-killed orchestrator (PID no longer
    running) does not block the next acquire. The schema_io helper
    uses os.kill(pid, 0) as the liveness probe; we synthesize a dead
    PID by using a clearly impossible value."""
    from lxm.reach_orchestrator import _ensure_ludex_on_path
    _ensure_ludex_on_path()
    from ludex.reach.schema_io import (
        acquire_session_lock, machine_slug,
    )
    sdir = tmp_path / "sessions" / "reach_test"
    sdir.mkdir(parents=True)
    slug = machine_slug("", "m1")
    lock = sdir / f".orchestrator_P_{slug}.lock"
    # Synthesize stale lock with PID 1 — wait, PID 1 is always alive.
    # Use a very large PID that's almost certainly free:
    lock.write_text("9999999 2026-01-01T00:00:00Z P\n", encoding="utf-8")
    # Should succeed (stale lock overwritten):
    import os
    acquire_session_lock(sdir, creature="P", machine_id="m1", pid=os.getpid())
    assert lock.exists()


def test_g5_retry_returns_terminal_error_after_exhaustion(
    monkeypatch, orch: ReachOrchestrator
):
    """G5: when every attempt yields a transient error, `_submit_with_retry`
    returns the last error string after `engine_max_retries + 1` calls
    rather than spinning forever."""
    calls = {"n": 0}

    def always_fail(prompt: str) -> str:
        calls["n"] += 1
        return "[Error: Anthropic 529 Overloaded]"

    orch.response_fn = always_fail
    orch.config.engine_max_retries = 3
    orch.config.engine_initial_backoff_s = 0.0  # don't actually sleep
    orch.config.engine_backoff_factor = 1.0
    monkeypatch.setattr("time.sleep", lambda *a, **kw: None)

    out = orch._submit_with_retry("ignored")
    assert out.startswith("[Error:")
    # max_retries=3 means 1 initial + 3 retries = 4 attempts total
    assert calls["n"] == 4


def test_g5_retry_succeeds_when_transient_clears(
    monkeypatch, orch: ReachOrchestrator
):
    """Transient errors clear after a few attempts → real response wins."""
    seq = iter([
        "[Error: Anthropic 529 Overloaded]",
        "[Error: 503 Service Unavailable]",
        "actual response body",
    ])

    def flaky(prompt: str) -> str:
        return next(seq)

    orch.response_fn = flaky
    orch.config.engine_max_retries = 3
    orch.config.engine_initial_backoff_s = 0.0
    monkeypatch.setattr("time.sleep", lambda *a, **kw: None)

    assert orch._submit_with_retry("p") == "actual response body"


def test_g5_retry_skips_for_non_transient_config_error(
    monkeypatch, orch: ReachOrchestrator
):
    """Config errors (non-transient) surface immediately — no retries.
    Distinguishes "fix this and rerun" from "wait it out"."""
    calls = {"n": 0}

    def config_error(prompt: str) -> str:
        calls["n"] += 1
        return "[Error: CLAUDE_CODE_GIT_BASH_PATH not set]"

    orch.response_fn = config_error
    orch.config.engine_max_retries = 5
    monkeypatch.setattr("time.sleep", lambda *a, **kw: None)

    out = orch._submit_with_retry("p")
    assert out.startswith("[Error:")
    assert calls["n"] == 1  # no retry


def test_tick_skips_publish_on_terminal_engine_error(
    monkeypatch, orch: ReachOrchestrator
):
    """Phase 2b.1.1 (3): when `_submit_with_retry` returns an error
    after exhaustion, the orchestrator does NOT commit it as a
    creature response — it leaves turn.yaml as-is so the next poll
    cycle picks the same turn back up."""
    sink: list[str] = []
    record = _install_monkeypatches(
        monkeypatch, orch,
        pointer=_mk_pointer(turn=3, next_creature="Primo", prompt_available=True),
        prompt="what brings you here?",
        write_sink=sink,
    )
    orch.config.engine_max_retries = 1
    orch.config.engine_initial_backoff_s = 0.0
    monkeypatch.setattr("time.sleep", lambda *a, **kw: None)
    orch.response_fn = lambda p: "[Error: Anthropic 529 Overloaded]"

    assert orch._tick() is False
    assert record["wrote"] == []
    assert record["committed"] == []
    assert 3 not in orch._answered_turns


def test_tick_calls_advance_after_successful_publish(
    monkeypatch, orch: ReachOrchestrator
):
    """Phase 2b.1.1 (4): on a successful publish, `_tick` calls
    `_advance_after_response` so neither side needs a manual host
    nudge to advance turn.yaml + write the next prompt."""
    sink: list[str] = []
    record = _install_monkeypatches(
        monkeypatch, orch,
        pointer=_mk_pointer(turn=5, next_creature="Primo", prompt_available=True),
        prompt="prompt body",
        write_sink=sink,
    )
    assert orch._tick() is True
    assert record.get("advanced") == [5]
