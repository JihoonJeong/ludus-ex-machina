"""Rule-based NL interpreter for Blockworld.

Blockworld actions are verb + optional direction + optional block/item.
If the creature emits valid JSON that wins via `parse_from_stdout`. This
interpreter catches the natural-language fallback case: prose that
says e.g. "I'll move north" or "break the tree to the west".

Ambiguity returns `None` — the orchestrator then falls through to AI
interpreter (if registered) or records the turn as unparseable.
"""

from __future__ import annotations

import re
from typing import Any

from lxm.interpreters.base import Interpretation, Interpreter

_VERBS = ["move", "break", "place", "craft", "pick", "drop", "look", "say", "wait"]
_DIRS = ["north", "south", "east", "west", "up", "down"]
_BLOCKS = ["stone", "dirt", "grass", "wood", "water", "sand", "iron_ore", "glass"]

# Synonyms that map to canonical verbs. Creatures phrase actions many ways.
_VERB_ALIASES = {
    "move": ["move", "walk", "go", "head", "step", "travel"],
    "break": ["break", "mine", "chop", "destroy", "dig", "harvest"],
    "place": ["place", "put", "set", "build", "position"],
    "craft": ["craft", "make", "create"],
    "pick": ["pick", "pickup", "pick-up", "collect", "grab"],
    "drop": ["drop"],
    "look": ["look", "scan", "survey", "observe"],
    "say": ["say", "speak", "announce", "call out"],
    "wait": ["wait", "skip", "pass", "stay", "hold"],
}


def _find_verb(text: str) -> str | None:
    """Return canonical verb name if exactly one matches; else None."""
    hits: list[str] = []
    for canon, aliases in _VERB_ALIASES.items():
        for a in aliases:
            if re.search(rf"\b{re.escape(a)}\b", text):
                if canon not in hits:
                    hits.append(canon)
                break
    if len(hits) == 1:
        return hits[0]
    return None


def _find_direction(text: str) -> str | None:
    hits = [d for d in _DIRS if re.search(rf"\b{d}\b", text)]
    return hits[0] if len(hits) == 1 else None


def _find_block(text: str) -> str | None:
    hits = [b for b in _BLOCKS if re.search(rf"\b{b}\b", text)]
    return hits[0] if len(hits) == 1 else None


class BlockworldRuleInterpreter(Interpreter):
    game = "blockworld"

    def interpret(self, response: str, context: dict[str, Any]) -> Interpretation | None:
        text = (response or "").lower().strip()
        if not text:
            return None

        verb = _find_verb(text)
        if verb is None:
            return None

        move: dict[str, Any] = {"type": "action", "verb": verb}
        evidence: dict[str, Any] = {"verb_hit": verb}
        confidence = 0.6

        if verb in ("move", "break"):
            d = _find_direction(text)
            if d is None:
                # Required but ambiguous → refuse (caller may route to AI fallback).
                return None
            move["direction"] = d
            evidence["direction"] = d
            confidence = 0.8

        elif verb == "place":
            d = _find_direction(text)
            b = _find_block(text)
            if d is None or b is None or b == "air":
                return None
            move["direction"] = d
            move["block"] = b
            evidence["direction"] = d
            evidence["block"] = b
            confidence = 0.85

        elif verb == "drop":
            b = _find_block(text)
            if b is None:
                return None
            move["item"] = b
            confidence = 0.75

        elif verb == "craft":
            # MVP knows only glass_pane.
            if "glass" in text:
                move["recipe"] = "glass_pane"
                confidence = 0.85
            else:
                return None

        elif verb == "say":
            # Extract anything after "say" up to end of line or quote.
            m = re.search(r"\bsay\b[:,]?\s*[\"']?([^\"'\n]+)[\"']?", text)
            if not m:
                return None
            move["message"] = m.group(1).strip()[:200]
            confidence = 0.65

        # pick / look / wait need nothing more.

        return Interpretation(
            move=move,
            confidence=round(confidence, 2),
            path="rule",
            evidence=evidence,
        )
