"""The plugin registry tolerates a plugin whose optional dependency is missing
(the hosted server has no treys/chess, or no local ludex engine) — it skips that
plugin with a warning and still loads the rest, so a remote tictactoe match
works on a host that can't import poker or the ludex adapter."""

import importlib

import lxm.adapters.registry as reg


def test_missing_plugin_dep_is_skipped(monkeypatch):
    # Reset registry state so _ensure_defaults runs fresh under the patch.
    monkeypatch.setattr(reg, "_DEFAULTS_LOADED", False)
    monkeypatch.setattr(reg, "_ADAPTERS", {})
    monkeypatch.setattr(reg, "_GAMES", {})

    real_import = importlib.import_module

    def flaky(name, *args, **kwargs):
        if name.endswith("poker.engine") or name.endswith("ludex_creature"):
            raise ImportError("simulated missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", flaky)

    reg._ensure_defaults()  # must not raise despite the two broken imports

    games, adapters = reg.list_games(), reg.list_adapters()
    assert "tictactoe" in games and "chess" in games   # healthy plugins still load
    assert "poker" not in games                          # missing-dep plugin skipped
    assert "rule_bot" in adapters
    assert "ludex" not in adapters                       # missing-dep adapter skipped
