"""Base adapter interface for LxM agent runtimes."""

from abc import ABC, abstractmethod


class AgentAdapter(ABC):
    """Interface for calling AI runtimes as game agents.

    All adapters must implement invoke() which takes a match directory
    and prompt string, and returns a result dict with stdout/stderr/exit_code.

    The orchestrator calls adapters synchronously — one agent at a time,
    turn-based. Async is not needed since we always wait for one agent's
    response before proceeding.
    """

    def __init__(self, agent_config: dict):
        self._agent_id = agent_config["agent_id"]
        self._display_name = agent_config.get("display_name", self._agent_id)
        self._model = agent_config.get("model")
        self._timeout = agent_config.get("timeout_seconds", 120)

    @abstractmethod
    def invoke(self, match_dir: str, prompt: str) -> dict:
        """Send prompt to the agent and return the response.

        Args:
            match_dir: Path to the match directory (agent's working dir).
            prompt: Full prompt including shell tags and game state.

        Returns:
            {
                "stdout": str,      # Agent's text output
                "stderr": str,      # Error output (if any)
                "exit_code": int,   # 0 = success, -1 = error
                "timed_out": bool,  # True if agent exceeded timeout
            }
        """
        pass

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def model(self) -> str | None:
        return self._model
