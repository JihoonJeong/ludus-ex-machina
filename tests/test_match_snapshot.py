"""Round-trip tests for Orchestrator snapshot/rehydrate (RFP A1 restart-safety)
plus the Redis match-store CRUD."""

import json
from pathlib import Path

from games.tictactoe.engine import TicTacToe
from lxm.orchestrator import Orchestrator


MATCH_CONFIG = {
    "protocol_version": "lxm-v0.2",
    "match_id": "snap_match",
    "game": {"name": "tictactoe", "version": "1.0"},
    "time_model": {
        "type": "turn_based", "turn_order": "sequential", "max_turns": 9,
        "timeout_seconds": 120, "timeout_action": "no_op", "max_retries": 2,
    },
    "agents": [
        {"agent_id": "alpha", "display_name": "Alpha", "seat": 0},
        {"agent_id": "beta", "display_name": "Beta", "seat": 1},
    ],
    "history": {"recent_moves_count": 5},
}

# alpha completes row 0 on turn 5 -> alpha wins (5 logged moves), same scenario
# as test_orchestrator.test_x_wins.
ALPHA_MOVES = [
    {"type": "place", "position": [0, 0]},
    {"type": "place", "position": [0, 1]},
    {"type": "place", "position": [0, 2]},
]
BETA_MOVES = [
    {"type": "place", "position": [1, 0]},
    {"type": "place", "position": [1, 1]},
]


class MockAdapter:
    """Pops predetermined moves; emits each as a JSON envelope on stdout."""

    def __init__(self, moves, agent_id):
        self._moves = list(moves)
        self._agent_id = agent_id

    def invoke(self, match_dir, prompt):
        import re
        m = re.search(r"Turn:\s*(\d+)", prompt)
        turn = int(m.group(1)) if m else 1
        if not self._moves:
            return {"stdout": "", "stderr": "", "exit_code": 0, "timed_out": True}
        move = self._moves.pop(0)
        env = {"protocol": "lxm-v0.2", "match_id": MATCH_CONFIG["match_id"],
               "agent_id": self._agent_id, "turn": turn, "move": move}
        return {"stdout": json.dumps(env), "stderr": "", "exit_code": 0, "timed_out": False}

    def on_match_end(self, *args, **kwargs):
        pass


def _adapters():
    return {"alpha": MockAdapter(ALPHA_MOVES, "alpha"),
            "beta": MockAdapter(BETA_MOVES, "beta")}


def _read_log(orch):
    return json.loads((Path(orch._match_dir) / "log.json").read_text())


class TestSnapshotResume:

    def test_resume_matches_uninterrupted_run(self, tmp_path):
        # Baseline: an uninterrupted match.
        full = Orchestrator(TicTacToe(), MATCH_CONFIG, _adapters())
        full.setup_match(base_dir=str(tmp_path / "full"))
        full_result = full.run()
        full_log = _read_log(full)
        assert full_result["winner"] == "alpha"

        # Interrupted: drive 3 turns, snapshot, rehydrate into a fresh
        # orchestrator (reusing the partially-consumed adapters), run() to end.
        adapters = _adapters()
        orch_a = Orchestrator(TicTacToe(), MATCH_CONFIG, adapters)
        orch_a.setup_match(base_dir=str(tmp_path / "a"))
        md_a = Path(orch_a._match_dir)
        gs = json.loads((md_a / "state.json").read_text())["game"]
        for _ in range(3):
            aid = orch_a._state.get_active_agent(gs)
            turn = orch_a._state.turn
            prompt = orch_a._build_turn_prompt(aid, turn, gs)
            inv = adapters[aid].invoke(orch_a._match_dir, prompt)
            outcome = orch_a._process_turn(gs, aid, turn, inv, md_a)
            assert not outcome.terminal
            gs = outcome.game_state

        snap = orch_a.to_snapshot(gs)
        assert snap["lxm"]["turn"] == 4
        assert len(snap["log"]) == 3

        # Restart: fresh orchestrator + same (partially-consumed) adapters.
        orch_b = Orchestrator(TicTacToe(), MATCH_CONFIG, adapters)
        orch_b.setup_match(base_dir=str(tmp_path / "b"))
        orch_b.load_snapshot(snap)
        result_b = orch_b.run()

        assert result_b["outcome"] == full_result["outcome"]
        assert result_b["winner"] == "alpha"
        assert len(_read_log(orch_b)) == len(full_log)  # 5 — log carried across the restart

    def test_snapshot_roundtrip_preserves_fields(self, tmp_path):
        orch = Orchestrator(TicTacToe(), MATCH_CONFIG, _adapters())
        orch.setup_match(base_dir=str(tmp_path / "rt"))
        orch.run()
        gs = json.loads((Path(orch._match_dir) / "state.json").read_text())["game"]
        snap = orch.to_snapshot(gs)

        orch2 = Orchestrator(TicTacToe(), MATCH_CONFIG, _adapters())
        orch2.setup_match(base_dir=str(tmp_path / "rt2"))
        gs2 = orch2.load_snapshot(snap)

        assert gs2 == gs
        assert orch2._state.turn == orch._state.turn
        assert (orch2._state.to_dict(gs2)["lxm"]["recent_moves"]
                == orch._state.to_dict(gs)["lxm"]["recent_moves"])
        assert len(orch2._vitals.turn_list) == len(orch._vitals.turn_list)
        assert orch2._agent_turn_counts == orch._agent_turn_counts


class _StubRedis:
    """Minimal in-memory stand-in for UpstashRedis (get/set/del JSON)."""

    def __init__(self):
        self._d = {}

    def set(self, k, v, ex=None):
        self._d[k] = v

    def get(self, k):
        return self._d.get(k)

    def delete(self, k):
        self._d.pop(k, None)

    def exists(self, k):
        return k in self._d

    def get_json(self, k):
        raw = self._d.get(k)
        return json.loads(raw) if raw is not None else None

    def set_json(self, k, v, ex=None):
        self._d[k] = json.dumps(v)


class TestMatchStore:

    def test_crud_roundtrip(self):
        from server.match_store import (save_match, load_match, delete_match,
                                        match_exists, match_key)
        r = _StubRedis()
        assert match_key("m1") == "lxm:match:m1"
        assert not match_exists(r, "m1")
        assert load_match(r, "m1") is None

        env = {"match_id": "m1", "status": "in_progress",
               "orchestrator": {"lxm": {"turn": 4}}}
        save_match(r, "m1", env)
        assert match_exists(r, "m1")
        assert load_match(r, "m1") == env

        delete_match(r, "m1")
        assert not match_exists(r, "m1")
        assert load_match(r, "m1") is None
