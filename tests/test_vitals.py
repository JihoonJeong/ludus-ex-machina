"""Tests for lxm.vitals — TurnVitals and MatchVitals."""

import unittest
from lxm.vitals import TurnVitals, MatchVitals


class TestTurnVitals(unittest.TestCase):

    def test_basic_creation(self):
        tv = TurnVitals(turn=1, agent_id="a", latency_ms=150.0)
        self.assertEqual(tv.turn, 1)
        self.assertEqual(tv.agent_id, "a")
        self.assertEqual(tv.latency_ms, 150.0)
        self.assertIsNone(tv.error_type)
        self.assertEqual(tv.retry_count, 0)
        self.assertIsNone(tv.tokens_in)
        self.assertIsNone(tv.tokens_out)

    def test_with_all_fields(self):
        tv = TurnVitals(
            turn=3, agent_id="b", latency_ms=5000.0,
            error_type="timeout", retry_count=2,
            tokens_in=100, tokens_out=50,
        )
        self.assertEqual(tv.error_type, "timeout")
        self.assertEqual(tv.retry_count, 2)
        self.assertEqual(tv.tokens_in, 100)
        self.assertEqual(tv.tokens_out, 50)


class TestMatchVitals(unittest.TestCase):

    def test_empty(self):
        mv = MatchVitals()
        d = mv.to_dict()
        self.assertEqual(d, {"turns": 0})

    def test_single_turn(self):
        mv = MatchVitals()
        mv.record(TurnVitals(turn=1, agent_id="a", latency_ms=200.0))
        d = mv.to_dict()
        self.assertEqual(d["turns"], 1)
        self.assertEqual(d["mean_latency_ms"], 200.0)
        self.assertEqual(d["errors"], 0)
        self.assertEqual(d["retries"], 0)
        self.assertIsNone(d["tokens_in"])
        self.assertIn("a", d["per_agent"])

    def test_multi_agent(self):
        mv = MatchVitals()
        mv.record(TurnVitals(turn=1, agent_id="a", latency_ms=100.0))
        mv.record(TurnVitals(turn=2, agent_id="b", latency_ms=300.0))
        mv.record(TurnVitals(turn=3, agent_id="a", latency_ms=200.0))
        mv.record(TurnVitals(turn=4, agent_id="b", latency_ms=400.0, error_type="timeout", retry_count=1))

        d = mv.to_dict()
        self.assertEqual(d["turns"], 4)
        self.assertEqual(d["errors"], 1)
        self.assertEqual(d["retries"], 1)
        self.assertEqual(d["total_latency_ms"], 1000.0)

        # Per-agent
        self.assertEqual(d["per_agent"]["a"]["turns"], 2)
        self.assertEqual(d["per_agent"]["a"]["latency_ms_mean"], 150.0)
        self.assertEqual(d["per_agent"]["a"]["errors"], 0)
        self.assertEqual(d["per_agent"]["b"]["turns"], 2)
        self.assertEqual(d["per_agent"]["b"]["errors"], 1)
        self.assertEqual(d["per_agent"]["b"]["retries"], 1)

    def test_tokens_aggregation(self):
        mv = MatchVitals()
        mv.record(TurnVitals(turn=1, agent_id="a", latency_ms=100.0, tokens_in=50, tokens_out=20))
        mv.record(TurnVitals(turn=2, agent_id="a", latency_ms=100.0, tokens_in=60, tokens_out=30))
        mv.record(TurnVitals(turn=3, agent_id="b", latency_ms=100.0))  # no tokens

        d = mv.to_dict()
        self.assertEqual(d["tokens_in"], 110)
        self.assertEqual(d["tokens_out"], 50)
        self.assertEqual(d["per_agent"]["a"]["tokens_in"], 110)
        self.assertIsNone(d["per_agent"]["b"]["tokens_in"])

    def test_turn_list(self):
        mv = MatchVitals()
        mv.record(TurnVitals(turn=1, agent_id="a", latency_ms=100.0))
        mv.record(TurnVitals(turn=2, agent_id="b", latency_ms=200.0))
        self.assertEqual(len(mv.turn_list), 2)


if __name__ == "__main__":
    unittest.main()
