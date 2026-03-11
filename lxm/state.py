"""State management for the lxm block in state.json."""


class LxMState:
    """Manages the lxm block in state.json and coordinates with the game engine."""

    def __init__(self, match_config: dict):
        self._match_id = match_config["match_id"]
        self._agents = [a["agent_id"] for a in match_config["agents"]]
        self._turn_order = match_config.get("time_model", {}).get("turn_order", "sequential")
        self._recent_moves_count = match_config.get("history", {}).get("recent_moves_count", 5)

        self._turn = 0
        self._phase = "READY"
        self._recent_moves: list[dict] = []

    def start(self, game_state: dict) -> dict:
        """Transition to first turn."""
        self._turn = 1
        self._phase = "TURN"
        return self.to_dict(game_state)

    def get_active_agent(self) -> str:
        """Return the agent_id whose turn it is."""
        idx = (self._turn - 1) % len(self._agents)
        return self._agents[idx]

    @property
    def turn(self) -> int:
        return self._turn

    @property
    def phase(self) -> str:
        return self._phase

    def record_move(self, agent_id: str, move: dict, summary: str) -> None:
        """Record a move in recent_moves (FIFO, capped at recent_moves_count)."""
        entry = {
            "turn": self._turn,
            "agent_id": agent_id,
            "move": move,
            "summary": summary,
        }
        self._recent_moves.append(entry)
        if len(self._recent_moves) > self._recent_moves_count:
            self._recent_moves = self._recent_moves[-self._recent_moves_count:]

    def advance_turn(self, game_state: dict) -> dict:
        """Move to the next turn and return updated state."""
        self._turn += 1
        self._phase = "TURN"
        return self.to_dict(game_state)

    def set_phase(self, phase: str) -> None:
        self._phase = phase

    def to_dict(self, game_state: dict) -> dict:
        """Return the complete state.json structure."""
        return {
            "lxm": {
                "turn": self._turn,
                "phase": self._phase,
                "turn_order": self._turn_order,
                "active_agent": self.get_active_agent() if self._turn > 0 else None,
                "agents": self._agents,
                "recent_moves": list(self._recent_moves),
            },
            "game": game_state,
        }
