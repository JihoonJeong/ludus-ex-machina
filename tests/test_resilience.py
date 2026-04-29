"""Tests for adapter resilience: retry, backoff, circuit breaker."""

import unittest
from unittest.mock import patch
from lxm.adapters.base import AgentAdapter


class FakeAdapter(AgentAdapter):
    """Test adapter that returns pre-configured results."""

    def __init__(self, results: list[dict], **kwargs):
        config = {"agent_id": "test", "resilience": kwargs}
        super().__init__(config)
        self._results = list(results)
        self._call_count = 0

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        self._call_count += 1
        if self._results:
            return self._results.pop(0)
        return {"stdout": "ok", "stderr": "", "exit_code": 0, "timed_out": False}


def _ok():
    return {"stdout": "ok", "stderr": "", "exit_code": 0, "timed_out": False}

def _transient_429():
    return {"stdout": "", "stderr": "429 rate limit exceeded", "exit_code": -1, "timed_out": False}

def _transient_timeout():
    return {"stdout": "", "stderr": "timed out", "exit_code": -1, "timed_out": True}

def _transient_connection():
    return {"stdout": "", "stderr": "ECONNREFUSED", "exit_code": -1, "timed_out": False}

def _non_transient_auth():
    return {"stdout": "", "stderr": "401 Unauthorized", "exit_code": -1, "timed_out": False}

def _non_transient_404():
    return {"stdout": "", "stderr": "404 model not found", "exit_code": -1, "timed_out": False}


class TestRetry(unittest.TestCase):

    @patch("time.sleep")
    def test_retry_on_429_then_success(self, mock_sleep):
        adapter = FakeAdapter([_transient_429(), _transient_429(), _ok()], max_retries=2)
        result = adapter.invoke("/tmp", "hello")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "ok")
        self.assertEqual(result["retry_count"], 2)
        self.assertEqual(adapter._call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep")
    def test_retry_on_timeout_then_success(self, mock_sleep):
        adapter = FakeAdapter([_transient_timeout(), _ok()], max_retries=2)
        result = adapter.invoke("/tmp", "hello")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["retry_count"], 1)

    @patch("time.sleep")
    def test_retry_on_connection_error(self, mock_sleep):
        adapter = FakeAdapter([_transient_connection(), _ok()], max_retries=1)
        result = adapter.invoke("/tmp", "hello")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["retry_count"], 1)

    def test_no_retry_on_success(self):
        adapter = FakeAdapter([_ok()], max_retries=2)
        result = adapter.invoke("/tmp", "hello")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["retry_count"], 0)
        self.assertEqual(adapter._call_count, 1)

    def test_no_retry_on_auth_error(self):
        adapter = FakeAdapter([_non_transient_auth()], max_retries=2)
        result = adapter.invoke("/tmp", "hello")
        self.assertEqual(result["exit_code"], -1)
        self.assertIn("401", result["stderr"])
        self.assertEqual(result["retry_count"], 0)
        self.assertEqual(adapter._call_count, 1)

    def test_no_retry_on_404(self):
        adapter = FakeAdapter([_non_transient_404()], max_retries=2)
        result = adapter.invoke("/tmp", "hello")
        self.assertEqual(result["exit_code"], -1)
        self.assertEqual(result["retry_count"], 0)
        self.assertEqual(adapter._call_count, 1)

    @patch("time.sleep")
    def test_all_retries_exhausted(self, mock_sleep):
        adapter = FakeAdapter(
            [_transient_429(), _transient_429(), _transient_429()],
            max_retries=2,
        )
        result = adapter.invoke("/tmp", "hello")
        self.assertEqual(result["exit_code"], -1)
        self.assertEqual(result["retry_count"], 2)
        self.assertEqual(adapter._call_count, 3)


class TestCircuitBreaker(unittest.TestCase):

    @patch("time.sleep")
    def test_circuit_opens_after_threshold(self, mock_sleep):
        adapter = FakeAdapter([], failure_threshold=3, max_retries=0)
        # Override _invoke_once to always fail
        adapter._invoke_once = lambda d, p: _transient_429()

        for _ in range(3):
            adapter.invoke("/tmp", "hello")

        self.assertTrue(adapter._circuit_open)
        self.assertEqual(adapter._consecutive_failures, 3)

        # Next call should be blocked by circuit breaker
        result = adapter.invoke("/tmp", "hello")
        self.assertIn("Circuit breaker open", result["stderr"])
        self.assertEqual(result["exit_code"], -1)

    @patch("time.sleep")
    def test_circuit_resets_on_success(self, mock_sleep):
        adapter = FakeAdapter([], failure_threshold=3, max_retries=0)

        # Fail twice
        adapter._invoke_once = lambda d, p: _transient_429()
        adapter.invoke("/tmp", "hello")
        adapter.invoke("/tmp", "hello")
        self.assertEqual(adapter._consecutive_failures, 2)
        self.assertFalse(adapter._circuit_open)

        # Succeed → counter resets
        adapter._invoke_once = lambda d, p: _ok()
        adapter.invoke("/tmp", "hello")
        self.assertEqual(adapter._consecutive_failures, 0)
        self.assertFalse(adapter._circuit_open)


class TestLatency(unittest.TestCase):

    def test_latency_ms_always_present(self):
        adapter = FakeAdapter([_ok()])
        result = adapter.invoke("/tmp", "hello")
        self.assertIn("latency_ms", result)
        self.assertGreaterEqual(result["latency_ms"], 0)

    def test_latency_on_error(self):
        adapter = FakeAdapter([_non_transient_auth()])
        result = adapter.invoke("/tmp", "hello")
        self.assertIn("latency_ms", result)


class TestBackoff(unittest.TestCase):

    def test_backoff_increases(self):
        adapter = FakeAdapter([], base_delay=1.0, max_delay=100.0)
        d0 = adapter._compute_backoff(0)
        d1 = adapter._compute_backoff(1)
        d2 = adapter._compute_backoff(2)
        self.assertGreater(d1, d0)
        self.assertGreater(d2, d1)

    def test_backoff_capped(self):
        adapter = FakeAdapter([], base_delay=1.0, max_delay=5.0)
        d = adapter._compute_backoff(10)
        self.assertLessEqual(d, 5.0)


class TestTransientClassification(unittest.TestCase):

    def test_success_is_not_transient(self):
        self.assertFalse(AgentAdapter._is_transient_error(_ok()))

    def test_429_is_transient(self):
        self.assertTrue(AgentAdapter._is_transient_error(_transient_429()))

    def test_timeout_is_transient(self):
        self.assertTrue(AgentAdapter._is_transient_error(_transient_timeout()))

    def test_connection_is_transient(self):
        self.assertTrue(AgentAdapter._is_transient_error(_transient_connection()))

    def test_auth_is_not_transient(self):
        self.assertFalse(AgentAdapter._is_transient_error(_non_transient_auth()))

    def test_404_is_not_transient(self):
        self.assertFalse(AgentAdapter._is_transient_error(_non_transient_404()))

    def test_503_is_transient(self):
        r = {"stdout": "", "stderr": "503 Service Unavailable", "exit_code": -1, "timed_out": False}
        self.assertTrue(AgentAdapter._is_transient_error(r))


if __name__ == "__main__":
    unittest.main()
