"""Abstract game engine interface for LxM."""

from abc import ABC, abstractmethod


class LxMGame(ABC):
    """
    Abstract base class for all LxM games.
    The orchestrator calls ONLY these methods.
    """

    @abstractmethod
    def get_rules(self) -> str:
        """Return the contents of rules.md for this game."""
        pass

    @abstractmethod
    def initial_state(self, agents: list[dict]) -> dict:
        """
        Generate the initial game state.

        Args:
            agents: List of agent configs. Each has: agent_id, display_name, seat

        Returns:
            The initial `game` block: {"current": {...}, "context": {...}}
        """
        pass

    @abstractmethod
    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        """
        Validate a move payload.

        Returns:
            {"valid": bool, "message": str or None}
        """
        pass

    @abstractmethod
    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        """
        Apply a validated move and return the updated game block.

        Returns:
            Updated {"current": {...}, "context": {...}}
        """
        pass

    @abstractmethod
    def is_over(self, state: dict) -> bool:
        """Check if the game has ended."""
        pass

    @abstractmethod
    def get_result(self, state: dict) -> dict:
        """
        Get the final result.

        Returns:
            {"outcome": str, "winner": str|None, "scores": dict, "summary": str}
        """
        pass

    @abstractmethod
    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        """Create a short text summary of a move for recent_moves."""
        pass

    @abstractmethod
    def get_evaluation_schema(self) -> dict:
        """Return the evaluation schema for post-game assessment."""
        pass

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        """Build inline turn prompt. Return None to fall back to file mode."""
        return None

    def get_active_agent_id(self, state: dict) -> str | None:
        """Override orchestrator's default turn rotation.

        Return the agent_id who should move next, or None to use default rotation.
        Games with custom turn logic (e.g. Codenames: spymaster→guesser within
        a team turn) implement this. Games with simple rotation don't need to.
        """
        return None
