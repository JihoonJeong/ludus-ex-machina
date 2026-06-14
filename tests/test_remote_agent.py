"""Unit tests for the generic remote-agent reference client (policies + move
extraction). No network — proves the contract-facing logic without a server."""

import importlib.util
import pathlib


def _load():
    p = pathlib.Path(__file__).resolve().parents[1] / "examples" / "remote_agent.py"
    spec = importlib.util.spec_from_file_location("remote_agent", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ra = _load()


def test_first_empty_policy():
    board = [["X", None, None], [None, "O", None], [None, None, None]]
    assert ra.first_empty_policy({"state": {"board": board}}) == {"type": "place", "position": [0, 1]}
    assert ra.first_empty_policy({"state": {"board": [["X"] * 3] * 3}}) is None  # full
    assert ra.first_empty_policy({"state": {}}) is None  # no board


def test_extract_move_from_envelope_and_bare():
    # from an LxM envelope embedded in CLI-LLM chatter
    txt = ('let me think...\n'
           '{"protocol":"lxm-v0.2","agent_id":"aria","turn":1,'
           '"move":{"type":"place","position":[1,1]}}\n done.')
    assert ra._extract_move(txt) == {"type": "place", "position": [1, 1]}
    # a bare move object
    assert ra._extract_move('move: {"type":"place","position":[2,0]}') == {
        "type": "place", "position": [2, 0]}
    # nothing parseable
    assert ra._extract_move("I'm not sure what to do") is None
