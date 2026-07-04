"""Base adapter interface for LxM agent runtimes.

Includes resilience layer: retry with exponential backoff, circuit breaker.
Pattern reference: ludex/blocks/resilience.py
"""

import os
import random
import signal
import subprocess
import time
from abc import ABC, abstractmethod


class BrainCapabilityError(RuntimeError):
    """Raised when an adapter's brain cannot emit the capability a field requires.

    Common case (D-072): gemini-cli backed agent enrolled in a field that needs
    json_emit but the brain only produces narrative output. Caught at match
    setup so the user sees a clear failure before any turn fires.
    """

    def __init__(self, *, adapter: str, agent_id: str, brain_capabilities: list[str],
                 game: str, accepts_capabilities: list[str]):
        self.adapter = adapter
        self.agent_id = agent_id
        self.brain_capabilities = brain_capabilities
        self.game = game
        self.accepts_capabilities = accepts_capabilities
        super().__init__(
            f"Brain capability mismatch: agent '{agent_id}' ({adapter}) "
            f"emits {brain_capabilities}, but game '{game}' accepts "
            f"{accepts_capabilities}. No overlap — match would fail at runtime."
        )


def check_capability_compat(adapter: "AgentAdapter", game) -> None:
    """Raise BrainCapabilityError if adapter's brain can't satisfy game's requirements.

    Called from run_match.py after adapters + game are both constructed.
    """
    accepts = getattr(game, "accepts_capabilities", ["json_emit"])
    brain = adapter.brain_capabilities
    if not (set(brain) & set(accepts)):
        raise BrainCapabilityError(
            adapter=type(adapter).__name__,
            agent_id=adapter.agent_id,
            brain_capabilities=list(brain),
            game=type(game).__name__,
            accepts_capabilities=list(accepts),
        )


class AgentAdapter(ABC):
    """Interface for calling AI runtimes as game agents.

    Subclasses implement _invoke_once(). The base invoke() wraps it with:
    - Latency measurement (latency_ms added to every result)
    - Retry with exponential backoff + jitter for transient errors
    - Circuit breaker after consecutive failures

    Resilience config via agent_config["resilience"]:
        max_retries: int (default 2)
        base_delay: float seconds (default 2.0)
        max_delay: float seconds (default 30.0)
        failure_threshold: int (default 5) — circuit breaker opens after this many
    """

    def __init__(self, agent_config: dict):
        self._agent_id = agent_config["agent_id"]
        self._display_name = agent_config.get("display_name", self._agent_id)
        self._model = agent_config.get("model")
        self._timeout = agent_config.get("timeout_seconds", 120)

        # Resilience config
        resilience = agent_config.get("resilience", {})
        self._max_retries = resilience.get("max_retries", 2)
        self._base_delay = resilience.get("base_delay", 2.0)
        self._max_delay = resilience.get("max_delay", 30.0)
        self._failure_threshold = resilience.get("failure_threshold", 5)

        # Circuit breaker state
        self._consecutive_failures: int = 0
        self._circuit_open: bool = False

        # D-072: brain capability declaration. Subclasses populate via
        # _populate_capabilities() (called below). Default is conservative
        # ["json_emit"] for any subclass that doesn't declare otherwise.
        self.brain_capabilities: list[str] = ["json_emit"]
        self._populate_capabilities(agent_config)

    def _populate_capabilities(self, agent_config: dict) -> None:
        """Hook for subclasses to set self.brain_capabilities based on
        the runtime they wrap and (where relevant) the model in use.
        Default: leave the conservative ["json_emit"] from __init__.
        """
        return None

    def _run_cli(self, cmd: list, *, cwd: str | None = None,
                 input_text: str | None = None,
                 env: dict | None = None) -> dict:
        """Run a CLI command; on timeout, SIGKILL the whole process group.

        nvm/npm-installed launchers (codex, claude) are wrapper scripts:
        killing only the direct child on timeout leaves the real binary
        running as an orphan that keeps burning account quota (observed
        with `codex exec` zombies at 12+ min, 2026-07-04).
        start_new_session=True puts the tree in its own group (pgid ==
        child pid) so the timeout path can reap all of it.
        """
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(input=input_text, timeout=self._timeout)
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            if os.name == "nt":  # no process groups on Windows (Ray's setup)
                proc.kill()
            else:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    proc.kill()
            proc.wait()
            return {
                "stdout": "",
                "stderr": "Process timed out",
                "exit_code": -1,
                "timed_out": True,
            }

    def invoke(self, match_dir: str, prompt: str) -> dict:
        """Resilient invoke: timing + retry + circuit breaker around _invoke_once()."""
        # Circuit breaker check
        if self._circuit_open:
            return {
                "stdout": "",
                "stderr": f"Circuit breaker open: {self._consecutive_failures} consecutive failures for {self._agent_id}",
                "exit_code": -1,
                "timed_out": False,
                "latency_ms": 0,
                "retry_count": 0,
            }

        last_result = None
        attempts = 0

        for attempt in range(1 + self._max_retries):
            attempts = attempt + 1
            start = time.monotonic()
            result = self._invoke_once(match_dir, prompt)
            elapsed_ms = (time.monotonic() - start) * 1000
            result["latency_ms"] = round(elapsed_ms, 1)

            if not self._is_transient_error(result):
                # Success or non-transient error — done
                self._consecutive_failures = 0
                self._circuit_open = False
                result["retry_count"] = attempt
                return result

            last_result = result

            # Transient error — retry if attempts remain
            if attempt < self._max_retries:
                delay = self._compute_backoff(attempt)
                print(f"[Retry] {self._agent_id} attempt {attempt + 2}/{1 + self._max_retries} "
                      f"after {delay:.1f}s ({self._error_label(result)})")
                time.sleep(delay)

        # All attempts exhausted
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._circuit_open = True
            print(f"[Circuit Breaker] {self._agent_id}: OPEN after {self._consecutive_failures} consecutive failures")

        if last_result is not None:
            last_result["retry_count"] = attempts - 1
            return last_result

        # Should not reach here, but safety fallback
        return {
            "stdout": "",
            "stderr": "All retry attempts exhausted",
            "exit_code": -1,
            "timed_out": False,
            "latency_ms": 0,
            "retry_count": self._max_retries,
        }

    @abstractmethod
    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
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

    def _compute_backoff(self, attempt: int) -> float:
        """Exponential backoff with jitter. Ludex _compute_backoff pattern."""
        base = self._base_delay * (2 ** attempt)
        jitter = random.uniform(0, base * 0.1)
        return min(base + jitter, self._max_delay)

    @staticmethod
    def _is_transient_error(result: dict) -> bool:
        """Check if the error is transient and worth retrying."""
        if result.get("exit_code", 0) == 0:
            return False

        if result.get("timed_out"):
            return True

        stderr = (result.get("stderr") or "").lower()

        # Transient: rate limit, server errors, connection issues
        transient_patterns = [
            "429", "rate limit", "quota", "resource exhausted",
            "500", "502", "503", "service unavailable",
            "connection", "econnrefused", "network", "timed out",
        ]
        for pattern in transient_patterns:
            if pattern in stderr:
                return True

        return False

    @staticmethod
    def _error_label(result: dict) -> str:
        """Short label for logging."""
        if result.get("timed_out"):
            return "timeout"
        stderr = (result.get("stderr") or "")[:80]
        return stderr or f"exit {result.get('exit_code')}"

    def on_match_end(self, match_result: dict, match_id: str, match_dir: str) -> None:
        """Hook called by Orchestrator after match completion.

        Default: no-op. Adapters that wrap stateful backends (e.g. a Ludex
        creature whose memory should record the match outcome) can override
        this to emit a distilled summary entry.
        """
        return None

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def model(self) -> str | None:
        return self._model
