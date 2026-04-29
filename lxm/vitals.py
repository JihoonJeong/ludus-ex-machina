"""Vital signs collection for LxM matches.

Per-turn telemetry (latency, tokens, errors) and match-level aggregation.
Pattern reference: ludex/blocks/tracking.py
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TurnVitals:
    """Per-turn telemetry."""
    turn: int
    agent_id: str
    latency_ms: float
    error_type: Optional[str] = None
    retry_count: int = 0
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None


class MatchVitals:
    """Aggregated vitals for one match."""

    def __init__(self):
        self._turns: list[TurnVitals] = []

    def record(self, vitals: TurnVitals):
        self._turns.append(vitals)

    def to_dict(self) -> dict:
        """Produce summary for result.json."""
        if not self._turns:
            return {"turns": 0}

        latencies = [t.latency_ms for t in self._turns]
        errors = [t for t in self._turns if t.error_type]
        total_retries = sum(t.retry_count for t in self._turns)
        tokens_in = sum(t.tokens_in for t in self._turns if t.tokens_in)
        tokens_out = sum(t.tokens_out for t in self._turns if t.tokens_out)

        # Per-agent breakdown
        agents: dict[str, dict] = {}
        for t in self._turns:
            if t.agent_id not in agents:
                agents[t.agent_id] = {
                    "latency_ms": [], "errors": 0, "retries": 0,
                    "tokens_in": 0, "tokens_out": 0,
                }
            a = agents[t.agent_id]
            a["latency_ms"].append(t.latency_ms)
            if t.error_type:
                a["errors"] += 1
            a["retries"] += t.retry_count
            if t.tokens_in:
                a["tokens_in"] += t.tokens_in
            if t.tokens_out:
                a["tokens_out"] += t.tokens_out

        per_agent = {}
        for aid, a in agents.items():
            lats = a["latency_ms"]
            sorted_lats = sorted(lats)
            per_agent[aid] = {
                "turns": len(lats),
                "latency_ms_mean": round(sum(lats) / len(lats), 1),
                "latency_ms_p50": round(sorted_lats[len(lats) // 2], 1),
                "latency_ms_max": round(max(lats), 1),
                "errors": a["errors"],
                "retries": a["retries"],
                "tokens_in": a["tokens_in"] or None,
                "tokens_out": a["tokens_out"] or None,
            }

        return {
            "turns": len(self._turns),
            "total_latency_ms": round(sum(latencies), 1),
            "mean_latency_ms": round(sum(latencies) / len(latencies), 1),
            "errors": len(errors),
            "retries": total_retries,
            "tokens_in": tokens_in or None,
            "tokens_out": tokens_out or None,
            "per_agent": per_agent,
        }

    @property
    def turn_list(self) -> list[TurnVitals]:
        return list(self._turns)
