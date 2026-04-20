"""CLI-based bare-brain AI interpreter (joint spec §G.3 P5).

Spawns a participating brain *without* its organs, habitat, or memory
to act as a neutral move-extractor when rule-based interpretation is
ambiguous. Aligns with §G.0 ontology — bare brain has no identity, so
it can be used as theatrical infrastructure without contaminating any
creature's narrative.

Per Ludex Cody (r6 reply) the design carries three commitments:

  (a) `meta.interpreter_brain = "<provider>:<model>"` is logged on every
      interpretation event. Lets later analysis audit same-family bias.
  (b) Interpreter is **stateless between turns**. We spin up a fresh
      adapter per call; nothing is carried turn-to-turn. This blocks the
      interpreter from developing its own register.
  (c) **Refusal is data.** When the AI returns text that does not parse
      to one of the legal actions (or its confidence undershoots), we
      do not guess — we return an Interpretation with `path="refusal"`
      so the orchestrator can record `engine_message="refusal"` rather
      than masking the event as a generic timeout.

The interpreter is per-game in the sense that each game registers its
own action space + envelope-move builder. The class itself is generic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable

from lxm.interpreters.base import Interpretation, Interpreter

logger = logging.getLogger(__name__)


# Threshold under which an interpretation is treated as a refusal rather
# than a confident classification. Tuned conservatively — better to log a
# refusal and let the orchestrator record an honest no-op than to fabricate
# a move from a noisy AI response. Configurable per game / per match by
# the registrant if needed.
DEFAULT_REFUSAL_THRESHOLD = 0.5


@dataclass
class BrainSpec:
    """Minimal description of which CLI to spawn for this interpreter call.

    `provider` selects the LxM adapter family (`"claude"`, `"gemini"`,
    `"codex"`); `model` is forwarded verbatim. `timeout_seconds` is the
    subprocess wall-clock cap. We deliberately do *not* expose creature-
    facing knobs (habitat, organs, memory) — bare-brain only.
    """
    provider: str
    model: str
    timeout_seconds: int = 60


class AICLIInterpreter(Interpreter):
    """Generic CLI-based AI interpreter.

    Configure with: a `game` name, an `action_space` (set of legal action
    strings the AI may pick from), a `move_builder` callback that turns
    a chosen action into a game-specific move dict, and a `BrainSpec` for
    which CLI to spawn.

    Attach refusal threshold via `refusal_threshold` (default 0.5).
    """

    def __init__(
        self,
        game: str,
        action_space: list[str],
        move_builder: Callable[[str], dict],
        brain: BrainSpec,
        refusal_threshold: float = DEFAULT_REFUSAL_THRESHOLD,
        prompt_extra: str = "",
    ):
        self.game = game
        if not action_space:
            raise ValueError("action_space must not be empty")
        self._actions = [a.lower() for a in action_space]
        self._move_builder = move_builder
        self._brain = brain
        self._refusal_threshold = refusal_threshold
        # Optional game-specific guidance appended to the standard prompt
        # (e.g. for Avalon vote: "consider the speaker's stated team").
        self._prompt_extra = prompt_extra.strip()

    def interpret(self, response: str, context: dict[str, Any]) -> Interpretation | None:
        text = (response or "").strip()
        if not text:
            return None

        # Stateless spawn — fresh adapter every call. No reuse across turns.
        adapter = self._spawn_bare_brain()
        if adapter is None:
            return None

        prompt = self._build_prompt(text)
        try:
            result = adapter._invoke_once("", prompt)
        except Exception as e:
            logger.warning(f"AICLIInterpreter ({self._brain.provider}) raised: {e}")
            return self._refusal("interpreter_error", evidence={"error": str(e)})

        raw = (result.get("stdout") or "").strip()
        chosen, confidence = self._parse_choice(raw)
        brain_tag = f"{self._brain.provider}:{self._brain.model}"

        if chosen is None:
            return self._refusal(
                "no_action_found",
                evidence={"raw_response": raw[:200], "interpreter_brain": brain_tag},
            )

        if confidence < self._refusal_threshold:
            return self._refusal(
                "low_confidence",
                evidence={
                    "raw_response": raw[:200],
                    "candidate_action": chosen,
                    "confidence": confidence,
                    "interpreter_brain": brain_tag,
                },
            )

        return Interpretation(
            move=self._move_builder(chosen),
            confidence=round(confidence, 2),
            path="ai",
            evidence={
                "interpreter_brain": brain_tag,
                "raw_response": raw[:200],
                "chosen_action": chosen,
            },
        )

    # --- internals ---

    def _spawn_bare_brain(self):
        """Build a fresh adapter instance per call (no shared state).

        We re-use LxM's existing CLI adapters to avoid duplicating subprocess
        plumbing, but only with a minimal config: agent_id, model, timeout.
        No `creature_path`, no `--add-dir`, no MCP wiring.
        """
        from lxm.adapters.registry import get_adapter_class
        try:
            cls = get_adapter_class(self._brain.provider)
        except KeyError:
            logger.warning(f"AICLIInterpreter: unknown provider {self._brain.provider}")
            return None

        cfg = {
            "agent_id": f"interpreter_{self._brain.provider}",
            "display_name": f"interpreter[{self._brain.model}]",
            "model": self._brain.model,
            "timeout_seconds": self._brain.timeout_seconds,
            # Force LxM-side resilience off — interpreter must be one-shot
            "resilience": {
                "max_retries": 0,
                "base_delay": 0.0,
                "max_delay": 0.0,
                "failure_threshold": 10**9,
            },
        }
        try:
            return cls(cfg)
        except Exception as e:
            logger.warning(f"AICLIInterpreter spawn failed for {self._brain.provider}: {e}")
            return None

    def _build_prompt(self, response_text: str) -> str:
        """Narrow prompt — single-word answer expected."""
        actions_csv = " | ".join(self._actions)
        lines = [
            f"You are a neutral move interpreter for the LxM `{self.game}` game.",
            "",
            "A player has just responded. Your job is to read their response and",
            f"identify which of these actions they chose: {actions_csv}.",
            "",
            "Output exactly one word — the chosen action — on a single line. No",
            "punctuation, no JSON, no prose. If the response is too ambiguous to",
            "identify a single action, output the word: refuse.",
        ]
        if self._prompt_extra:
            lines.extend(["", self._prompt_extra])
        lines.extend([
            "",
            "--- BEGIN PLAYER RESPONSE ---",
            response_text,
            "--- END PLAYER RESPONSE ---",
            "",
            f"Your one-word answer (one of: {actions_csv}, or refuse):",
        ])
        return "\n".join(lines)

    def _parse_choice(self, raw: str) -> tuple[str | None, float]:
        """Extract the AI's one-word answer.

        Confidence heuristic (order matters — ambiguity beats first-word):
          - Exact single-token match → 0.95
          - Refusal token → None, 0.0
          - Multiple distinct actions present → None, 0.0 (ambiguous; refusal)
          - First-word match → 0.9
          - Short response, single action token present (≤ 80 chars) → 0.75
          - Long response, single action token → 0.55
          - No match → None, 0.0
        """
        text = raw.strip().lower()
        if not text:
            return None, 0.0
        # Strip code fences / quotes if model wrapped output
        text = text.strip("`\"' ").strip()
        # Explicit refusal
        if text == "refuse" or text.startswith("refuse"):
            return None, 0.0
        # Exact one-token match
        if text in self._actions:
            return text, 0.95
        # Multi-action ambiguity check (must precede first-word path)
        action_hits = [a for a in self._actions if re.search(rf"\b{re.escape(a)}\b", text)]
        if len(action_hits) > 1:
            return None, 0.0
        # First-word match
        first_word = re.split(r"\s+", text, maxsplit=1)[0].strip(".,;:!?\"'`")
        if first_word in self._actions:
            return first_word, 0.9
        # Single-action substring
        if len(action_hits) == 1 and len(text) <= 80:
            return action_hits[0], 0.75
        if len(action_hits) == 1:
            return action_hits[0], 0.55
        return None, 0.0

    def _refusal(self, reason: str, evidence: dict | None = None) -> Interpretation:
        ev = dict(evidence or {})
        ev["refusal_reason"] = reason
        # `path="refusal"` is a sentinel; orchestrator inspects this and
        # records engine_message="refusal" rather than synthesizing a move.
        return Interpretation(
            move={},  # empty — orchestrator must NOT use this as a move
            confidence=0.0,
            path="refusal",
            evidence=ev,
        )
