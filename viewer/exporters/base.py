"""Abstract frame renderer for LxM replay export."""

from abc import ABC, abstractmethod
from PIL import Image


class FrameRenderer(ABC):
    @abstractmethod
    def initial_state(self, match_config: dict) -> dict:
        """Return the initial game state before any moves."""
        pass

    @abstractmethod
    def apply_move(self, state: dict, log_entry: dict) -> dict:
        """Apply a move to a state and return the new state."""
        pass

    @abstractmethod
    def render_frame(self, state: dict, turn: int, total_turns: int,
                     agents: list[dict], last_move: dict | None) -> Image.Image:
        """Render a single frame for this turn."""
        pass

    @abstractmethod
    def render_result_frame(self, state: dict, result: dict,
                            agents: list[dict], total_turns: int) -> Image.Image:
        """Render the final result frame."""
        pass
