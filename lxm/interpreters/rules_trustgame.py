"""Rule-based interpreter for Trust Game.

Extracts {"type": "choice", "action": "cooperate" | "defect"} from
free-form text by scanning for action-indicating phrases with simple
negation handling. Returns `None` when both actions fire with comparable
strength (caller may then fall through to AI interpretation).
"""

from __future__ import annotations

import re
from typing import Any

from lxm.interpreters.base import Interpretation, Interpreter


# Words that indicate cooperation. Collected empirically from creature
# responses (smoke_002, smoke_003, smoke_005). This is intentionally
# narrow — we want high-precision matches; uncertain text should fall
# through to None.
_COOPERATE_PATTERNS = [
    r"\bcooperate\b",
    r"\bcooperation\b",
    r"\bcooperat(?:ing|ed)\b",
    r"\bchoose\s+(?:to\s+)?cooperate\b",
    r"\bi(?:'ll|\s+will)\s+cooperate\b",
    r"\bgo\s+with\s+cooperation\b",
    r"\bmutual\s+trust\b",
    r"\bbuild\s+trust\b",
    r"\btrust(?:\s+them)?\b",
    r"\bkeep\s+cooperating\b",
]

_DEFECT_PATTERNS = [
    r"\bdefect\b",
    r"\bdefection\b",
    r"\bdefect(?:ing|ed)\b",
    r"\bchoose\s+(?:to\s+)?defect\b",
    r"\bi(?:'ll|\s+will)\s+defect\b",
    r"\bbetray(?:\s+them)?\b",
    r"\bexploit\b",
    r"\btake\s+the\s+5\b",
    r"\bgo\s+with\s+defection\b",
]

# Negation window: if a negator appears within N chars before a keyword,
# flip that keyword's contribution. "won't defect", "not going to
# cooperate", "refuse to betray" etc.
_NEGATORS = [
    r"\bnot\b",
    r"\bno\b",
    r"\bnever\b",
    r"\bwon't\b",
    r"\bwill\s+not\b",
    r"\brefuse(?:d|s)?\s+to\b",
    r"\bavoid\b",
    r"\binstead\s+of\b",
    r"\brather\s+than\b",
    r"\btempted\s+to\b",  # "tempted to defect but..." — usually flipped by the "but"
]

_NEGATION_WINDOW = 30  # chars before the keyword


def _count_matches(text: str, patterns: list[str]) -> list[tuple[int, str]]:
    """Return (position, matched_text) for each pattern hit, in order."""
    hits: list[tuple[int, str]] = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            hits.append((m.start(), m.group(0)))
    hits.sort()
    return hits


def _is_negated(text: str, position: int) -> bool:
    """Check whether any negator falls in [position-window, position)."""
    start = max(0, position - _NEGATION_WINDOW)
    window = text[start:position]
    for neg in _NEGATORS:
        if re.search(neg, window, flags=re.IGNORECASE):
            return True
    return False


def _weighted_score(text: str, hits: list[tuple[int, str]]) -> float:
    """Sum hit weights, flipping negated hits to the opposite side.

    Returns the *net* contribution toward this action's side. Negated
    hits produce a negative contribution (in effect, crediting the
    opposite action).
    """
    score = 0.0
    for pos, _match in hits:
        score += -1.0 if _is_negated(text, pos) else 1.0
    return score


class TrustGameRuleInterpreter(Interpreter):
    """Heuristic Trust Game move extractor. Returns None when ambiguous."""

    game = "trustgame"

    def interpret(self, response: str, context: dict[str, Any]) -> Interpretation | None:
        text = response or ""
        if not text.strip():
            return None

        coop_hits = _count_matches(text, _COOPERATE_PATTERNS)
        defect_hits = _count_matches(text, _DEFECT_PATTERNS)

        coop_score = _weighted_score(text, coop_hits)
        defect_score = _weighted_score(text, defect_hits)

        # No signal at all.
        if not coop_hits and not defect_hits:
            return None

        # Ambiguous: both signals positive and within 1 point of each
        # other. Let the AI fallback decide rather than guess.
        if coop_score > 0 and defect_score > 0 and abs(coop_score - defect_score) < 1.5:
            return None

        # Pick the dominant side.
        if coop_score >= defect_score:
            action = "cooperate"
            score = coop_score
            alt = defect_score
        else:
            action = "defect"
            score = defect_score
            alt = coop_score

        if score <= 0:
            # Dominant side is itself negated overall — nothing reliable.
            return None

        # Confidence: simple margin-based. More hits + wider margin = higher.
        margin = score - max(0.0, alt)
        confidence = min(0.95, 0.55 + 0.15 * margin)

        return Interpretation(
            move={"type": "choice", "action": action},
            confidence=round(confidence, 2),
            path="rule",
            evidence={
                "coop_hits": [m for _, m in coop_hits],
                "defect_hits": [m for _, m in defect_hits],
                "coop_score": coop_score,
                "defect_score": defect_score,
            },
        )
