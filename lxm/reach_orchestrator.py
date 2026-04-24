"""D-062 Phase 2b peer-side polling agent — LxM-side stub.

Mirror of Ludex's `ludex/reach/reach_orchestrator.py` (`258d070`).
Drive-loop shape is the same; response generation is a pluggable
callable because LxM does not have an organism-engine equivalent
yet. Joint session will formalize the LxM-side `response_fn`
contract (LxM adapter wrapper? a reach-specific interpreter?).

Status: skeleton. Git is shelled out via `subprocess`; no retry /
conflict handling yet. `run()` blocks. Tests land alongside the
Phase 2b.1 integration tests on the Ludex side.

The two halves (Ludex `ReachOrchestrator`, LxM `ReachOrchestrator`)
never communicate directly — they only read and write the files
described in `ludex/docs/reach_session_schema.md`. Either side can
be the field host or the peer.
"""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Polling-loop tunables, kept separate from constructor args so a
    future CLI can build one without touching the runtime class."""
    poll_interval_seconds: float = 5.0
    idle_grace_seconds: float = 1800.0
    git_remote: str = "origin"


# Response function: receives the prompt body (no frontmatter) and
# returns the response body text. How the peer generates that text is
# out of scope for this module — an LxM adapter wrapper, a human
# curator, a scripted probe, all valid implementations.
ResponseFn = Callable[[str], str]


class ReachOrchestrator:
    """Peer-side reach session agent.

    Responsibilities mirror the Ludex side:
      1. Poll `sessions/<session_id>/turn.yaml` on a fixed interval.
      2. When `next.creature == local_creature` and the prompt is
         available, read `prompts/NNN.md`, strip frontmatter, and
         invoke the injected `response_fn(prompt_body)` for a string.
      3. Write the response to
         `responses/NNN_<creature>_<machine_slug>.md` with frontmatter,
         commit, and push.
      4. Detect session close (any `close_*.md`, or `meta.yaml.status`
         is not `active`, or idle grace expired) and terminate.

    Not in the skeleton yet:
      - Retry on push contention (Phase 2b.1).
      - Multi-session concurrency (one instance = one session).
      - Consent re-verification per turn (session prep assumed).
      - YAML frontmatter parsing (placeholder; shares helpers with
        `scripts/export_static.py::_parse_frontmatter_md` once the
        joint-session refactor lands).
    """

    def __init__(
        self,
        repo_root: Path,
        session_id: str,
        local_creature: str,
        local_machine_id: str,
        response_fn: ResponseFn,
        config: Optional[OrchestratorConfig] = None,
        machine_alias: str = "",
    ):
        self.repo_root = Path(repo_root)
        self.session_id = session_id
        self.local_creature = local_creature
        self.local_machine_id = local_machine_id
        self.machine_alias = machine_alias
        self.response_fn = response_fn
        self.config = config or OrchestratorConfig()
        self._session_dir = self.repo_root / "sessions" / session_id
        self._answered_turns: set[int] = set()
        self._last_activity_at = time.monotonic()

    # ── public loop ─────────────────────────────────────────────────────

    def run(self) -> int:
        """Block until the session closes or idle grace expires.
        Returns the number of turns this peer answered."""
        logger.info("reach_extended session=%s role=peer creature=%s",
                    self.session_id, self.local_creature)
        turns_answered = 0
        while True:
            if self._is_session_closed():
                break
            if time.monotonic() - self._last_activity_at > self.config.idle_grace_seconds:
                logger.info("idle grace expired; exiting")
                break
            did_work = self._tick()
            if did_work:
                turns_answered += 1
                self._last_activity_at = time.monotonic()
                continue
            time.sleep(self.config.poll_interval_seconds)
        logger.info("reach_retracted session=%s turns=%d",
                    self.session_id, turns_answered)
        return turns_answered

    # ── single iteration (public for testing) ───────────────────────────

    def _tick(self) -> bool:
        """One iteration: pull, check pointer, maybe answer. Returns
        True if a turn was answered (caller should skip the sleep)."""
        self._git_pull()
        pointer = self._read_turn_pointer()
        if pointer is None:
            return False
        if pointer.get("next_creature") != self.local_creature:
            return False
        if not pointer.get("prompt_available"):
            return False
        turn_no = pointer.get("turn")
        if turn_no is None or turn_no in self._answered_turns:
            return False

        prompt_text = self._read_prompt_body(turn_no)
        if prompt_text is None:
            return False

        response_text = self.response_fn(prompt_text)
        self._write_response(turn_no, response_text)
        self._git_commit_push(
            f"reach: {self.local_creature} answers turn {turn_no} "
            f"of {self.session_id}"
        )
        self._answered_turns.add(turn_no)
        return True

    # ── filesystem helpers (stubs; joint-session refactor shares them) ──

    def _read_turn_pointer(self) -> Optional[dict]:
        """Read `turn.yaml` and return {turn, next_creature, prompt_available}.
        NotImplemented at skeleton stage."""
        raise NotImplementedError(
            "turn.yaml parsing pending joint-session refactor; share "
            "_parse_flat_yaml / _parse_turn_envelope with Ludex side."
        )

    def _read_prompt_body(self, turn_no: int) -> Optional[str]:
        """Read `prompts/NNN.md`, strip frontmatter, return body text."""
        raise NotImplementedError(
            "prompts/NNN.md body read pending joint-session refactor."
        )

    def _write_response(self, turn_no: int, body: str) -> None:
        """Write `responses/NNN_<creature>_<machine_slug>.md` with
        frontmatter + body."""
        raise NotImplementedError(
            "responses/ write + frontmatter render pending joint-session refactor."
        )

    def _is_session_closed(self) -> bool:
        """Return True if any `close_*.md` present, or `meta.yaml.status`
        is not 'active'."""
        if not self._session_dir.is_dir():
            return False
        for f in self._session_dir.glob("close_*.md"):
            return True
        meta_path = self._session_dir / "meta.yaml"
        if meta_path.exists():
            # Lightweight scan; full YAML parse is joint-session refactor.
            text = meta_path.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("status:"):
                    value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                    return value != "active"
        return False

    # ── git shell-outs ──────────────────────────────────────────────────

    def _git_pull(self) -> None:
        try:
            subprocess.run(
                ["git", "pull", "--rebase", self.config.git_remote, "main"],
                cwd=str(self.repo_root), check=True, capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning("git pull failed: %s", e.stderr.decode(errors="ignore"))

    def _git_commit_push(self, message: str) -> None:
        subprocess.run(
            ["git", "add", "."], cwd=str(self.repo_root), check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(self.repo_root), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push", self.config.git_remote, "main"],
            cwd=str(self.repo_root), check=True, capture_output=True,
        )
