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


def test_run_match_maps_match_the_registry():
    """`scripts/run_match.py` keeps its own adapter/game maps, so the registry and
    the CLI are two declarations of one fact — and they drifted: `grok` shipped in
    the CLI map on 2026-07-13 but was never added to `_ADAPTER_SPECS`, so for five
    weeks grok was unusable through every registry consumer (hosted match driver,
    LxM client, commentary, the wm-eval harness) while working fine locally.

    Pin them together: whichever list a future adapter lands in, this fails until
    it lands in both. Compare the source-level *declarations* (`_ADAPTER_SPECS`),
    not the live registry — other tests register fakes into that global."""
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "scripts" / "run_match.py"
    text = src.read_text(encoding="utf-8")

    def keys_of(name: str) -> set[str]:
        block = re.search(rf"{name}\s*=\s*\{{(.*?)\n\}}", text, re.S)
        assert block, f"{name} not found in run_match.py"
        return set(re.findall(r'"(\w+)"\s*:', block.group(1)))

    assert keys_of("ADAPTER_CLASSES") == {spec[0] for spec in reg._ADAPTER_SPECS}
    assert keys_of("GAME_ENGINES") == {spec[0] for spec in reg._GAME_SPECS}
