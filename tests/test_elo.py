"""Tests for ELO rating system."""

import pytest
from lxm.elo import compute_elo_change, k_factor, weighted_overall_elo, DEFAULT_ELO


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


class TestWeightedOverallElo:
    def test_single_game(self):
        by_game = {"chess": {"elo": 1300, "games": 10}}
        assert weighted_overall_elo(by_game, {"chess": 1.0}) == 1300

    def test_equal_weights(self):
        by_game = {
            "chess": {"elo": 1400, "games": 5},
            "trustgame": {"elo": 1200, "games": 5},
        }
        assert weighted_overall_elo(by_game, {"chess": 1.0, "trustgame": 1.0}) == 1300

    def test_unequal_weights(self):
        by_game = {
            "chess": {"elo": 1400, "games": 5},
            "tictactoe": {"elo": 1000, "games": 5},
        }
        # chess weight 1.0, tictactoe weight 0.5 → (1400*1 + 1000*0.5) / 1.5 = 1267
        result = weighted_overall_elo(by_game, {"chess": 1.0, "tictactoe": 0.5})
        assert result == 1267

    def test_skips_unplayed_games(self):
        by_game = {
            "chess": {"elo": 1400, "games": 5},
            "trustgame": {"elo": 1200, "games": 0},
        }
        assert weighted_overall_elo(by_game, {"chess": 1.0, "trustgame": 1.0}) == 1400

    def test_no_games_returns_default(self):
        assert weighted_overall_elo({}, {}) == DEFAULT_ELO

    def test_unknown_game_defaults_weight_1(self):
        by_game = {"newgame": {"elo": 1350, "games": 3}}
        assert weighted_overall_elo(by_game, {}) == 1350


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

    def test_overall_elo_is_weighted_average(self, tmp_path):
        """Overall ELO should be weighted average of per-game ELOs, not independent."""
        import json
        from lxm.elo import build_leaderboard

        # Alice wins chess, loses trustgame
        for i, (game, winner) in enumerate([("chess", "alice"), ("trustgame", "bob")]):
            d = tmp_path / f"match_{i:03d}"
            d.mkdir()
            config = {
                "match_id": f"match_{i:03d}",
                "game": {"name": game},
                "agents": [{"agent_id": "alice"}, {"agent_id": "bob"}],
            }
            result = {"outcome": "win", "winner": winner}
            (d / "match_config.json").write_text(json.dumps(config))
            (d / "result.json").write_text(json.dumps(result))

        lb = build_leaderboard(str(tmp_path), game_weights={"chess": 2.0, "trustgame": 1.0})

        alice = lb["agents"]["alice"]
        # Alice: chess ELO > 1200, trustgame ELO < 1200
        assert alice["by_game"]["chess"]["elo"] > DEFAULT_ELO
        assert alice["by_game"]["trustgame"]["elo"] < DEFAULT_ELO
        # Overall should be weighted: chess counts double
        chess_elo = alice["by_game"]["chess"]["elo"]
        trust_elo = alice["by_game"]["trustgame"]["elo"]
        expected = round((chess_elo * 2.0 + trust_elo * 1.0) / 3.0)
        assert alice["elo"] == expected
        assert "games" in lb
        assert "game_weights" in lb

    def test_response_includes_games_list(self, tmp_path):
        import json
        from lxm.elo import build_leaderboard

        d = tmp_path / "m1"
        d.mkdir()
        config = {
            "match_id": "m1", "game": {"name": "chess"},
            "agents": [{"agent_id": "a"}, {"agent_id": "b"}],
        }
        (d / "match_config.json").write_text(json.dumps(config))
        (d / "result.json").write_text(json.dumps({"outcome": "draw", "winner": None}))

        lb = build_leaderboard(str(tmp_path))
        assert "chess" in lb["games"]
