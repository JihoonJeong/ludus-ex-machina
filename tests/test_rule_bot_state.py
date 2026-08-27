"""The default hosted opponent must play the board it is actually on.

rule_bot is what a participant gets when no adapter is named, so it is the
out-of-the-box path for anyone opening a hosted match — including a village
building its first candidate. It was broken in a way that produced no error
line at all: the game was recovered by keyword-scanning the prompt, and the
board by a regex that could not match a nested board and returned an empty one
instead. So every turn proposed the centre, which is legal exactly once, and
the match died six rejected moves later at the timeout cliff.

Both halves of that were recoveries of facts the caller already had. These
tests pin the structural path and, deliberately, also pin that a parse failure
must not masquerade as an empty board.
"""

from __future__ import annotations

import json

from lxm.adapters.rule_bot import RuleBotAdapter, TicTacToeStrategy
from server.match_driver import make_participant_adapter, open_match


def _state(board):
    return {"current": {"board": board, "marks": {"a": "X", "b": "O"}}}


def test_the_board_comes_from_state_not_from_prose():
    s = TicTacToeStrategy("medium")
    board = [["X", None, None], [None, "O", None], [None, None, None]]
    move = s.decide("prompt text with no board in it", "a", _state(board))
    assert move["type"] == "place"
    r, c = move["position"]
    assert board[r][c] is None, "the bot proposed an occupied cell"


def test_an_occupied_centre_is_not_proposed_again():
    """The exact failure: centre taken, and the bot must move somewhere else."""
    s = TicTacToeStrategy("medium")
    board = [[None, None, None], [None, "X", None], [None, None, None]]
    assert s.decide("", "b", _state(board))["position"] != [1, 1]


def test_a_malformed_state_falls_back_instead_of_flattening_garbage():
    s = TicTacToeStrategy("medium")
    for bad in (None, {}, {"current": {}}, {"current": {"board": "nope"}},
                {"current": {"board": [[None, None]]}}):
        assert s._board_from_state(bad) is None


def test_the_flatten_preserves_cell_order_and_empties():
    s = TicTacToeStrategy("medium")
    flat = s._board_from_state(_state([["X", None, "O"], [None, "X", None], ["O", None, None]]))
    assert flat == ["X", "", "O", "", "X", "", "O", "", ""]


def test_the_adapter_reads_the_state_file_the_orchestrator_writes(tmp_path):
    (tmp_path / "state.json").write_text(json.dumps(
        {"lxm": {"turn": 2}, "game": _state([[None] * 3] * 3)}), encoding="utf-8")
    bot = RuleBotAdapter({"agent_id": "a", "game": "tictactoe"})
    assert bot._read_state(str(tmp_path)) == _state([[None] * 3] * 3)


def test_a_missing_state_file_is_not_an_error(tmp_path):
    """Absence must degrade to the prompt path, not raise into a failed turn."""
    assert RuleBotAdapter({"agent_id": "a", "game": "tictactoe"})._read_state(str(tmp_path)) is None


def test_the_driver_tells_the_adapter_which_game_it_is():
    """The caller knows; the adapter should not have to guess from prose."""
    bot = make_participant_adapter({"id": "a", "adapter": "rule_bot"}, "tictactoe")
    assert bot._game == "tictactoe"


def test_an_unnamed_game_still_leaves_the_prompt_fallback():
    bot = make_participant_adapter({"id": "a", "adapter": "rule_bot"})
    assert bot._game is None


def test_a_default_hosted_match_plays_to_a_real_ending(tmp_path):
    """The end-to-end claim: no adapter named, so rule_bot on both seats, and
    the match must reach a genuine tictactoe result rather than the cliff."""
    env = open_match(None, match_id="_t", game_name="tictactoe",
                     participants=[{"id": "a", "kind": "local"},
                                   {"id": "b", "kind": "local"}],
                     config={}, kind="practice", base_dir=str(tmp_path))
    assert env["status"] == "complete"
    assert env["result"]["outcome"] in ("win", "draw"), env["result"]["outcome"]
    assert env["result"]["vitals"]["errors"] == 0
