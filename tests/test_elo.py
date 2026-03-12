"""Tests for ELO rating system."""

import pytest
from lxm.elo import compute_elo_change, k_factor, DEFAULT_ELO


class TestComputeEloChange:
    def test_equal_players_win(self):
        new_a, new_b = compute_elo_change(1200, 1200, 1.0, k=32)
        assert new_a == 1216
        assert new_b == 1184

    def test_equal_players_draw(self):
        new_a, new_b = compute_elo_change(1200, 1200, 0.5, k=32)
        assert new_a == 1200
        assert new_b == 1200

    def test_equal_players_loss(self):
        new_a, new_b = compute_elo_change(1200, 1200, 0.0, k=32)
        assert new_a == 1184
        assert new_b == 1216

    def test_stronger_beats_weaker(self):
        """Stronger player wins — smaller gain."""
        new_a, new_b = compute_elo_change(1400, 1200, 1.0, k=32)
        assert new_a > 1400
        assert new_b < 1200
        gain = new_a - 1400
        assert gain < 16  # Less than half K because expected

    def test_weaker_beats_stronger(self):
        """Upset — larger gain."""
        new_a, new_b = compute_elo_change(1200, 1400, 1.0, k=32)
        gain = new_a - 1200
        assert gain > 16  # More than half K because unexpected

    def test_symmetry(self):
        """Total ELO is conserved."""
        new_a, new_b = compute_elo_change(1300, 1100, 1.0, k=32)
        assert new_a + new_b == 1300 + 1100

    def test_draw_higher_rated_loses_points(self):
        """Draw: higher-rated player loses a bit, lower gains."""
        new_a, new_b = compute_elo_change(1400, 1200, 0.5, k=32)
        assert new_a < 1400
        assert new_b > 1200


class TestKFactor:
    def test_provisional(self):
        assert k_factor(0) == 32
        assert k_factor(29) == 32

    def test_established(self):
        assert k_factor(30) == 16
        assert k_factor(100) == 16


class TestBuildLeaderboard:
    def test_empty_dir(self, tmp_path):
        from lxm.elo import build_leaderboard
        result = build_leaderboard(str(tmp_path))
        assert result["agents"] == {}
        assert result["matches_processed"] == 0

    def test_single_match(self, tmp_path):
        import json
        from lxm.elo import build_leaderboard

        match_dir = tmp_path / "match_001"
        match_dir.mkdir()

        config = {
            "match_id": "match_001",
            "game": {"name": "chess"},
            "agents": [
                {"agent_id": "alice", "display_name": "Alice"},
                {"agent_id": "bob", "display_name": "Bob"},
            ],
        }
        result = {"outcome": "win", "winner": "alice", "summary": "Alice wins"}

        (match_dir / "match_config.json").write_text(json.dumps(config))
        (match_dir / "result.json").write_text(json.dumps(result))

        lb = build_leaderboard(str(tmp_path))
        assert lb["matches_processed"] == 1
        assert lb["agents"]["alice"]["elo"] > DEFAULT_ELO
        assert lb["agents"]["bob"]["elo"] < DEFAULT_ELO
        assert lb["agents"]["alice"]["wins"] == 1
        assert lb["agents"]["bob"]["losses"] == 1
        assert lb["agents"]["alice"]["by_game"]["chess"]["wins"] == 1

    def test_draw_keeps_equal(self, tmp_path):
        import json
        from lxm.elo import build_leaderboard

        match_dir = tmp_path / "match_001"
        match_dir.mkdir()

        config = {
            "match_id": "match_001",
            "game": {"name": "chess"},
            "agents": [
                {"agent_id": "alice"},
                {"agent_id": "bob"},
            ],
        }
        result = {"outcome": "draw", "winner": None, "summary": "Draw"}

        (match_dir / "match_config.json").write_text(json.dumps(config))
        (match_dir / "result.json").write_text(json.dumps(result))

        lb = build_leaderboard(str(tmp_path))
        assert lb["agents"]["alice"]["elo"] == DEFAULT_ELO
        assert lb["agents"]["bob"]["elo"] == DEFAULT_ELO
        assert lb["agents"]["alice"]["draws"] == 1
