"""The server-side GCS auto-export is best-effort and safe: a no-op when
unconfigured, never raises."""

from server.gcs_export import export_replay_to_gcs


def test_noop_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GCS_SA_KEY_JSON", raising=False)
    # no key -> returns False, does not raise, does not import/contact GCS
    assert export_replay_to_gcs({"config": {}, "log": [], "result": {}}, "m1") is False


def test_bad_key_does_not_raise(monkeypatch):
    monkeypatch.setenv("GCS_SA_KEY_JSON", "{not valid json")
    assert export_replay_to_gcs({"config": {}, "log": [], "result": {}}, "m1") is False
