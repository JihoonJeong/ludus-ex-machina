"""Tests for lxm/orchestrator.py using MockAdapter."""

import json
from pathlib import Path

from games.tictactoe.engine import TicTacToe
from lxm.orchestrator import Orchestrator


MATCH_CONFIG = {
    "protocol_version": "lxm-v0.2",
    "match_id": "test_match",
    "game": {"name": "tictactoe", "version": "1.0"},
    "time_model": {
        "type": "turn_based",
        "turn_order": "sequential",
        "max_turns": 9,
        "timeout_seconds": 120,
        "timeout_action": "no_op",
        "max_retries": 2,
    },
    "agents": [
        {"agent_id": "alpha", "display_name": "Alpha", "seat": 0},
        {"agent_id": "beta", "display_name": "Beta", "seat": 1},
    ],
    "history": {"recent_moves_count": 5},
}


class MockAdapter:
    """Returns predetermined moves for testing."""

    def __init__(self, moves: list[dict], fail_first_n: int = 0):
        self._moves = list(moves)
        self._call_idx = 0
        self._fail_first_n = fail_first_n
        self._match_id = MATCH_CONFIG["match_id"]

    def set_context(self, agent_id: str):
        self._agent_id = agent_id

    def invoke(self, match_dir: str, prompt: str) -> dict:
        self._call_idx += 1

        # Parse turn and agent_id from prompt
        agent_id = self._agent_id
        turn = self._parse_turn(prompt)

        if self._call_idx <= self._fail_first_n:
            return {
                "stdout": "I don't know what to do",
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            }

        if not self._moves:
            return {"stdout": "", "stderr": "", "exit_code": 0, "timed_out": True}

        move = self._moves.pop(0)
        envelope = {
            "protocol": "lxm-v0.2",
            "match_id": self._match_id,
            "agent_id": agent_id,
            "turn": turn,
            "move": move,
        }
        return {
            "stdout": json.dumps(envelope),
            "stderr": "",
            "exit_code": 0,
            "timed_out": False,
        }

    @staticmethod
    def _parse_turn(prompt: str) -> int:
        import re
        m = re.search(r"Turn:\s*(\d+)", prompt)
        return int(m.group(1)) if m else 1


class WritingMockAdapter:
    """Writes move to file instead of stdout."""

    def __init__(self, moves: list[dict]):
        self._moves = list(moves)
        self._agent_id = None

    def set_context(self, agent_id: str):
        self._agent_id = agent_id

    def invoke(self, match_dir: str, prompt: str) -> dict:
        agent_id = self._agent_id
        turn = MockAdapter._parse_turn(prompt)
        move = self._moves.pop(0)
        envelope = {
            "protocol": "lxm-v0.2",
            "match_id": MATCH_CONFIG["match_id"],
            "agent_id": agent_id,
            "turn": turn,
            "move": move,
        }
        move_path = Path(match_dir) / "moves" / f"turn_{turn}_{agent_id}.json"
        move_path.write_text(json.dumps(envelope))
        return {"stdout": "", "stderr": "", "exit_code": 0, "timed_out": False}


class TestFullGameMock:
    """Simulate a complete X wins game."""

    def test_x_wins(self, tmp_path):
        game = TicTacToe()
        # X plays: (0,0), (0,1), (0,2) -> row 0 win
        # O plays: (1,0), (1,1)
        alpha_moves = [
            {"type": "place", "position": [0, 0]},
            {"type": "place", "position": [0, 1]},
            {"type": "place", "position": [0, 2]},
        ]
        beta_moves = [
            {"type": "place", "position": [1, 0]},
            {"type": "place", "position": [1, 1]},
        ]

        alpha_adapter = MockAdapter(alpha_moves)
        alpha_adapter.set_context("alpha")
        beta_adapter = MockAdapter(beta_moves)
        beta_adapter.set_context("beta")

        adapters = {"alpha": alpha_adapter, "beta": beta_adapter}
        orch = Orchestrator(game, MATCH_CONFIG, adapters)
        orch.setup_match(base_dir=str(tmp_path))

        # Override adapter context per turn
        class TurnAwareMock:
            def __init__(self, alpha, beta):
                self.alpha = alpha
                self.beta = beta

        result = orch.run()

        assert result["outcome"] == "win"
        assert result["winner"] == "alpha"
        assert result["scores"]["alpha"] == 1

        # Verify files exist
        match_dir = tmp_path / "test_match"
        assert (match_dir / "result.json").exists()
        assert (match_dir / "state.json").exists()

        log = json.loads((match_dir / "log.json").read_text())
        assert len(log) == 5  # 3 X moves + 2 O moves

    def test_draw(self, tmp_path):
        game = TicTacToe()
        # Board ends as:  X O X
        #                 X X O
        #                 O X O  -> draw
        alpha_moves = [
            {"type": "place", "position": [0, 0]},  # X
            {"type": "place", "position": [0, 2]},  # X
            {"type": "place", "position": [1, 0]},  # X
            {"type": "place", "position": [1, 1]},  # X
            {"type": "place", "position": [2, 1]},  # X
        ]
        beta_moves = [
            {"type": "place", "position": [0, 1]},  # O
            {"type": "place", "position": [1, 2]},  # O
            {"type": "place", "position": [2, 0]},  # O
            {"type": "place", "position": [2, 2]},  # O
        ]

        alpha_adapter = MockAdapter(alpha_moves)
        alpha_adapter.set_context("alpha")
        beta_adapter = MockAdapter(beta_moves)
        beta_adapter.set_context("beta")

        config = {**MATCH_CONFIG, "match_id": "draw_match"}
        alpha_adapter._match_id = "draw_match"
        beta_adapter._match_id = "draw_match"

        orch = Orchestrator(game, config, {"alpha": alpha_adapter, "beta": beta_adapter})
        orch.setup_match(base_dir=str(tmp_path))
        result = orch.run()

        assert result["outcome"] == "draw"
        assert result["winner"] is None

    def test_file_based_moves(self, tmp_path):
        """Test that agents can submit moves via file."""
        game = TicTacToe()
        alpha_moves = [
            {"type": "place", "position": [0, 0]},
            {"type": "place", "position": [0, 1]},
            {"type": "place", "position": [0, 2]},
        ]
        beta_moves = [
            {"type": "place", "position": [1, 0]},
            {"type": "place", "position": [1, 1]},
        ]

        alpha_adapter = WritingMockAdapter(alpha_moves)
        alpha_adapter.set_context("alpha")
        beta_adapter = WritingMockAdapter(beta_moves)
        beta_adapter.set_context("beta")

        orch = Orchestrator(game, MATCH_CONFIG, {"alpha": alpha_adapter, "beta": beta_adapter})
        orch.setup_match(base_dir=str(tmp_path))
        result = orch.run()

        assert result["outcome"] == "win"
        assert result["winner"] == "alpha"


class TestRetryOnInvalid:
    def test_retry_succeeds(self, tmp_path):
        """First attempt fails (no JSON), second succeeds."""
        game = TicTacToe()

        # Alpha: fail first call, then succeed
        alpha_adapter = MockAdapter(
            [{"type": "place", "position": [1, 1]},
             {"type": "place", "position": [0, 0]},
             {"type": "place", "position": [0, 1]}],
            fail_first_n=1,
        )
        alpha_adapter.set_context("alpha")

        beta_adapter = MockAdapter([
            {"type": "place", "position": [2, 0]},
            {"type": "place", "position": [2, 1]},
        ])
        beta_adapter.set_context("beta")

        orch = Orchestrator(game, MATCH_CONFIG, {"alpha": alpha_adapter, "beta": beta_adapter})
        orch.setup_match(base_dir=str(tmp_path))
        result = orch.run()

        # Game should still complete
        assert result["outcome"] in ("win", "draw")


class TestTimeout:
    def test_timeout_noop(self, tmp_path):
        """Agent times out, gets no_op, game continues."""
        game = TicTacToe()

        class TimeoutOnceAdapter:
            def __init__(self, moves, agent_id):
                self._moves = list(moves)
                self._agent_id = agent_id
                self._first = True
                self._match_id = "test_match"

            def set_context(self, agent_id):
                self._agent_id = agent_id

            def invoke(self, match_dir, prompt):
                turn = MockAdapter._parse_turn(prompt)
                if self._first and "RETRY" not in prompt:
                    self._first = False
                    return {"stdout": "", "stderr": "", "exit_code": 1, "timed_out": True}
                if not self._moves:
                    return {"stdout": "", "stderr": "", "exit_code": 1, "timed_out": True}
                move = self._moves.pop(0)
                env = {
                    "protocol": "lxm-v0.2",
                    "match_id": self._match_id,
                    "agent_id": self._agent_id,
                    "turn": turn,
                    "move": move,
                }
                return {"stdout": json.dumps(env), "stderr": "", "exit_code": 0, "timed_out": False}

        alpha_adapter = TimeoutOnceAdapter([
            {"type": "place", "position": [0, 0]},
            {"type": "place", "position": [0, 1]},
            {"type": "place", "position": [0, 2]},
        ], "alpha")

        beta_adapter = MockAdapter([
            {"type": "place", "position": [1, 0]},
            {"type": "place", "position": [1, 1]},
        ])
        beta_adapter.set_context("beta")

        orch = Orchestrator(game, MATCH_CONFIG, {"alpha": alpha_adapter, "beta": beta_adapter})
        orch.setup_match(base_dir=str(tmp_path))
        result = orch.run()

        # Game should complete (alpha had a timeout on turn 1, then played normally)
        assert result["outcome"] in ("win", "draw")
