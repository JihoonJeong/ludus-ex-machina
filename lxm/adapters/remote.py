"""RemoteParticipant — a participant whose moves arrive over the network.

In a hosted cross-machine match (RFP Stage A) the creature stays on its
owner's machine; only the move crosses the wire. The match driver detects a
RemoteParticipant, emits the turn (your_turn / GET /turns/{n}), and halts until
the move arrives via POST — so invoke() is never called on the happy path. The
no-op methods exist only so a RemoteParticipant can sit in the orchestrator's
adapters dict; invoke() degrades to a timeout if ever reached (a stray retry or
post-game eval), which the orchestrator treats as a no-op.
"""

from __future__ import annotations


class RemoteParticipant:
    """Adapter-shaped placeholder for a network-reached participant."""

    def __init__(self, agent_id: str, display: str | None = None):
        self.agent_id = agent_id
        self.display = display or agent_id
        # Declared so the capability gate (if ever run) doesn't reject it; the
        # wire move is pre-validated by the driver regardless.
        self.brain_capabilities = ["json_emit", "narrative"]

    def invoke(self, match_dir: str, prompt: str) -> dict:
        return {"stdout": "", "stderr": "", "exit_code": 0, "timed_out": True}

    def on_match_end(self, *args, **kwargs) -> None:
        return None
