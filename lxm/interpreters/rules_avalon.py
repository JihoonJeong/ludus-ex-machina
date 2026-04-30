"""Rule-based NL interpreter for Avalon.

Avalon has three turn shapes — `proposal`, `vote`, `quest_action` — and
the prompt tells the brain which one is active. Narrative-only brains
(gemini-cli, future SLMs) often respond in prose: "I propose hearth and
bot_b for the quest", "I'll vote approve", "playing success on this
quest". This interpreter extracts those into the JSON moves Avalon's
engine expects.

Phase is read from the orchestrator-supplied `game_state` in context —
without phase, narrative is too ambiguous (e.g. "I support the team"
could mean approve a vote or include them in a proposal). Returns
None for phase-not-found rather than guessing.
"""

from __future__ import annotations

import re
from typing import Any

from lxm.interpreters.base import Interpretation, Interpreter


_APPROVE_PATTERNS = [
    r"\bapprov(?:e|es|ed|ing)\b",
    r"\baccept(?:s|ed|ing)?\b",
    r"\bsupport(?:s|ed|ing)?\b",
    r"\bvote\s+(?:to\s+)?(?:approve|yes|for|in\s+favor)\b",
    r"\bin\s+favor\b",
    r"\bvote\s+yes\b",
    r"\bvoting\s+yes\b",
    r"\bgreen[\s-]?light\b",
]

_REJECT_PATTERNS = [
    r"\breject(?:s|ed|ing)?\b",
    r"\bden(?:y|ies|ied|ying)\b",
    r"\boppos(?:e|es|ed|ing)\b",
    r"\bvote\s+(?:to\s+)?(?:reject|no|against|down)\b",
    r"\bvote\s+no\b",
    r"\bvoting\s+no\b",
    r"\bblock(?:s|ed|ing)?\b",
    r"\bturn\s+(?:it\s+)?down\b",
]

_SUCCESS_PATTERNS = [
    r"\bplay(?:ing)?\s+success\b",
    r"\bplay(?:ing)?\s+a?\s*success\s+card\b",
    r"\bplay\s+clean\b",
    r"\bsucceed\b",
    r"\bsuccess\s+card\b",
    r"\bcooperat(?:e|ing)\s+on\s+(?:the\s+)?quest\b",
    r"\bcomplete\s+the\s+quest\b",
]

_SABOTAGE_PATTERNS = [
    r"\bsabotag(?:e|ing)\b",
    r"\bplay(?:ing)?\s+(?:a\s+)?fail(?:ure)?\b",
    r"\bfail\s+the\s+quest\b",
    r"\bbetray\s+the\s+quest\b",
    r"\bdrop\s+a\s+fail\b",
]

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
]

_NEGATION_WINDOW = 30


def _hits(text: str, patterns: list[str]) -> list[int]:
    """Return positions of every pattern hit (case-insensitive)."""
    out: list[int] = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            out.append(m.start())
    out.sort()
    return out


def _is_negated(text: str, position: int) -> bool:
    """Check if a negator precedes the keyword within the same sentence.

    Window is bounded by the closer of: 30 chars back, or the most recent
    sentence terminator (. ! ?). Without the sentence bound, "won't approve.
    Rejecting." would propagate "won't" onto "Rejecting" because both fit
    inside a 30-char raw window.
    """
    start = max(0, position - _NEGATION_WINDOW)
    raw_window = text[start:position]
    last_terminator = max(raw_window.rfind("."), raw_window.rfind("!"),
                          raw_window.rfind("?"))
    if last_terminator >= 0:
        raw_window = raw_window[last_terminator + 1:]
    for neg in _NEGATORS:
        if re.search(neg, raw_window, flags=re.IGNORECASE):
            return True
    return False


def _net_score(text: str, hits: list[int]) -> float:
    """Sum hits, flipping each negated one to -1."""
    return sum(-1.0 if _is_negated(text, p) else 1.0 for p in hits)


def _binary_choice(text: str, a_patterns: list[str], b_patterns: list[str],
                   a_label: str, b_label: str) -> tuple[str, dict] | None:
    """Score two competing patterns; pick winner if margin ≥ 1.5; else None."""
    a_hits = _hits(text, a_patterns)
    b_hits = _hits(text, b_patterns)
    if not a_hits and not b_hits:
        return None
    a_score = _net_score(text, a_hits)
    b_score = _net_score(text, b_hits)
    margin = abs(a_score - b_score)
    if a_score > 0 and b_score > 0 and margin < 1.5:
        return None
    if a_score >= b_score and a_score > 0:
        return a_label, {"a_hits": len(a_hits), "b_hits": len(b_hits),
                          "a_score": a_score, "b_score": b_score, "margin": margin}
    if b_score > a_score and b_score > 0:
        return b_label, {"a_hits": len(a_hits), "b_hits": len(b_hits),
                          "a_score": a_score, "b_score": b_score, "margin": margin}
    return None


def _extract_phase(context: dict[str, Any]) -> str | None:
    """Pull current phase from orchestrator-supplied game_state."""
    gs = context.get("game_state") or {}
    current = gs.get("current") if isinstance(gs, dict) else None
    if isinstance(current, dict):
        phase = current.get("phase")
        if isinstance(phase, str):
            return phase
    return None


def _extract_team_size(context: dict[str, Any]) -> int | None:
    gs = context.get("game_state") or {}
    current = gs.get("current") if isinstance(gs, dict) else None
    if not isinstance(current, dict):
        return None
    qnum = current.get("quest_number")
    sizes = current.get("quest_sizes")
    if isinstance(qnum, int) and isinstance(sizes, list) and 0 < qnum <= len(sizes):
        return sizes[qnum - 1]
    return None


def _extract_seat_order(context: dict[str, Any]) -> list[str]:
    gs = context.get("game_state") or {}
    current = gs.get("current") if isinstance(gs, dict) else None
    if isinstance(current, dict):
        seats = current.get("seat_order")
        if isinstance(seats, list):
            return [s for s in seats if isinstance(s, str)]
    return []


def _find_team(text: str, seat_order: list[str], team_size: int,
               leader: str | None) -> list[str] | None:
    """Find ordered, deduplicated agent names mentioned in text.

    Returns the first `team_size` mentions in text-order, restricted to
    seat_order. If the leader proposes themselves implicitly ("propose
    self plus ..."), include leader at front when they're not already
    mentioned by name. Returns None when fewer than `team_size` distinct
    seats are referenced.
    """
    if team_size <= 0 or not seat_order:
        return None
    lower = text.lower()
    # Order-preserving dedup: walk text, capture each seat the first
    # time it appears. Use word-boundary regex so "bot_b" doesn't match
    # inside "bot_bot" (defensive).
    found: list[tuple[int, str]] = []
    for seat in seat_order:
        seat_lc = seat.lower()
        for m in re.finditer(rf"\b{re.escape(seat_lc)}\b", lower):
            found.append((m.start(), seat))
            break  # first hit per seat is enough for ordering
    found.sort()
    team = [seat for _, seat in found]

    # "self" / "myself" / "me" → leader implicit inclusion.
    if leader and leader not in team:
        if re.search(r"\b(?:self|myself|i\s+include\s+me)\b", lower):
            team = [leader] + team

    if len(team) < team_size:
        return None
    return team[:team_size]


class AvalonRuleInterpreter(Interpreter):
    """Phase-aware Avalon move extractor.

    Uses orchestrator-supplied `game_state` in `context` to determine
    which move shape to emit. Returns None when prose is too ambiguous
    or when phase is unknown — caller falls through to AI fallback or
    records a no-op.
    """

    game = "avalon"

    def interpret(self, response: str, context: dict[str, Any]) -> Interpretation | None:
        text = (response or "").strip()
        if not text:
            return None

        phase = _extract_phase(context)
        if phase is None:
            return None

        if phase == "vote":
            return self._interpret_vote(text)
        if phase == "quest":
            return self._interpret_quest(text)
        if phase == "propose":
            return self._interpret_proposal(text, context)
        return None

    def _interpret_vote(self, text: str) -> Interpretation | None:
        choice = _binary_choice(text, _APPROVE_PATTERNS, _REJECT_PATTERNS,
                                "approve", "reject")
        if choice is None:
            return None
        label, evidence = choice
        return Interpretation(
            move={"type": "vote", "choice": label},
            confidence=0.8,
            path="rule",
            evidence={"vote": label, **evidence},
        )

    def _interpret_quest(self, text: str) -> Interpretation | None:
        choice = _binary_choice(text, _SUCCESS_PATTERNS, _SABOTAGE_PATTERNS,
                                "success", "sabotage")
        if choice is None:
            return None
        label, evidence = choice
        return Interpretation(
            move={"type": "quest_action", "choice": label},
            confidence=0.8,
            path="rule",
            evidence={"quest_action": label, **evidence},
        )

    def _interpret_proposal(self, text: str, context: dict[str, Any]) -> Interpretation | None:
        team_size = _extract_team_size(context)
        seat_order = _extract_seat_order(context)
        if team_size is None or not seat_order:
            return None
        leader = context.get("agent_id")
        team = _find_team(text, seat_order, team_size, leader)
        if team is None:
            return None
        return Interpretation(
            move={"type": "proposal", "team": team},
            confidence=0.75,
            path="rule",
            evidence={"team": team, "team_size": team_size,
                      "from_seats": seat_order},
        )
