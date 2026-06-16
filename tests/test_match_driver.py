"""Phase 1 acceptance (RFP A4): a hosted match of 1 local bot + 1 remote
participant completes end-to-end via the event-driven driver, with the remote
driven over the poll path (open_match -> submit_move)."""

import json
from pathlib import Path

from lxm.adapters.registry import register_adapter
from server.match_driver import open_match, submit_move, turn_payload, MatchError
from server.match_store import load_match


class FirstEmptyCellBot:
    """Local test bot: reads state.json, plays the first empty tic-tac-toe cell.

    (Tic-tac-toe has no inline prompt, so the file-based prompt carries no board
    markers — the bot reads the board straight from the match_dir state file.)
    """

    def __init__(self, agent_config):
        self._agent_id = agent_config["agent_id"]
        self.brain_capabilities = ["json_emit"]

    def invoke(self, match_dir, prompt):
        state = json.loads((Path(match_dir) / "state.json").read_text())
        board = state["game"]["current"]["board"]
        pos = next(([r, c] for r in range(3) for c in range(3) if board[r][c] is None), None)
        env = {"protocol": "lxm-v0.2", "agent_id": self._agent_id,
               "turn": 0, "move": {"type": "place", "position": pos}}
        return {"stdout": json.dumps(env), "stderr": "", "exit_code": 0, "timed_out": False}

    def on_match_end(self, *args, **kwargs):
        pass


def _first_empty(env):
    board = env["orchestrator"]["game_state"]["current"]["board"]
    pos = next(([r, c] for r in range(3) for c in range(3) if board[r][c] is None), None)
    return {"type": "place", "position": pos}


class _StubRedis:
    def __init__(self):
        self._d = {}

    def get(self, k):
        return self._d.get(k)

    def set(self, k, v, ex=None):
        self._d[k] = v

    def delete(self, k):
        self._d.pop(k, None)

    def exists(self, k):
        return k in self._d

    def get_json(self, k):
        raw = self._d.get(k)
        return json.loads(raw) if raw is not None else None

    def set_json(self, k, v, ex=None):
        self._d[k] = json.dumps(v)


def _participants():
    return [
        {"id": "bot", "kind": "local", "adapter": "first_empty_bot"},
        {"id": "human", "kind": "remote", "display": "Remote Human"},
    ]


class TestLocalPlusRemote:

    def test_match_completes(self, tmp_path):
        register_adapter("first_empty_bot", FirstEmptyCellBot)
        r = _StubRedis()
        env = open_match(r, match_id="m1", game_name="tictactoe",
                         participants=_participants(), config={"max_turns": 9},
                         base_dir=str(tmp_path))

        # bot (seat 0) auto-played turn 1; the match halted at the remote's turn 2.
        assert env["status"] == "in_progress"
        assert env["to_move"] == "human"
        assert env["to_move_kind"] == "remote"
        assert env["to_move_turn"] == 2
        assert load_match(r, "m1")["to_move"] == "human"  # persisted under lxm:match:m1

        # the turn payload exposes the opponent identity (the bot) + a deadline
        tp = turn_payload(env)
        assert tp["to_move"] == "human"
        assert any(a["id"] == "bot" for a in tp["present_agents"])
        assert tp["deadline"] == 180

        # the remote plays first-empty until the match ends
        remote_moves = 0
        for _ in range(12):
            if env["status"] != "in_progress":
                break
            assert env["to_move_kind"] == "remote"
            env = submit_move(r, "m1", turn=env["to_move_turn"],
                              move=_first_empty(env), base_dir=str(tmp_path))
            remote_moves += 1

        assert env["status"] == "complete"
        assert env["result"] is not None
        assert env["result"]["outcome"] in ("win", "draw")  # a clean finish, not a cliff/timeout
        assert remote_moves >= 1
        assert load_match(r, "m1")["status"] == "complete"
        assert turn_payload(env) is None  # no turn to serve once complete

    def test_rejects_illegal_and_out_of_turn(self, tmp_path):
        register_adapter("first_empty_bot", FirstEmptyCellBot)
        r = _StubRedis()
        env = open_match(r, match_id="m2", game_name="tictactoe",
                         participants=_participants(), config={"max_turns": 9},
                         base_dir=str(tmp_path))
        turn = env["to_move_turn"]

        # [0,0] was taken by the bot on turn 1 -> illegal
        try:
            submit_move(r, "m2", turn=turn, move={"type": "place", "position": [0, 0]},
                        base_dir=str(tmp_path))
            assert False, "expected MatchError(illegal_move)"
        except MatchError as e:
            assert e.code == "illegal_move"

        # wrong turn number -> rejected before the move is even validated
        try:
            submit_move(r, "m2", turn=turn + 5, move=_first_empty(env),
                        base_dir=str(tmp_path))
            assert False, "expected MatchError(wrong_turn)"
        except MatchError as e:
            assert e.code == "wrong_turn"

        # neither rejected attempt advanced the match
        assert load_match(r, "m2")["to_move_turn"] == turn

    def test_unknown_match_raises(self, tmp_path):
        r = _StubRedis()
        try:
            submit_move(r, "nope", turn=1, move={"type": "place", "position": [0, 0]},
                        base_dir=str(tmp_path))
            assert False, "expected MatchError(not_found)"
        except MatchError as e:
            assert e.code == "not_found"


class TestHTTPEndpoints:
    """The A1/A3 endpoints over the driver, via FastAPI TestClient."""

    def _client(self, monkeypatch):
        from fastapi.testclient import TestClient
        from server.app import app
        register_adapter("first_empty_bot", FirstEmptyCellBot)
        stub = _StubRedis()
        monkeypatch.setattr("server.routes._get_redis", lambda: stub)
        return TestClient(app)

    def test_create_play_complete(self, monkeypatch):
        client = self._client(monkeypatch)
        resp = client.post("/api/matches", json={
            "match_id": "e1", "game": "tictactoe",
            "participants": [
                {"id": "bot", "kind": "local", "adapter": "first_empty_bot"},
                {"id": "human", "kind": "remote"},
            ],
            "config": {"max_turns": 9},
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "in_progress"
        assert body["to_move"] == "human"

        # play to completion over the poll path (GET turn -> POST move)
        for _ in range(12):
            st = client.get("/api/matches/e1/state").json()
            if st["status"] != "in_progress":
                break
            t = st["to_move_turn"]
            tp = client.get(f"/api/matches/e1/turns/{t}").json()
            board = tp["state"]["board"]
            pos = next([r, c] for r in range(3) for c in range(3) if board[r][c] is None)
            resp = client.post(f"/api/matches/e1/turns/{t}/move",
                               json={"move": {"type": "place", "position": pos}})
            assert resp.status_code == 200, resp.text

        final = client.get("/api/matches/e1/state").json()
        assert final["status"] == "complete"
        assert final["result"]["outcome"] in ("win", "draw")

    def test_error_status_mapping(self, monkeypatch):
        client = self._client(monkeypatch)
        # unknown match -> 404
        assert client.get("/api/matches/ghost/state").status_code == 404
        assert client.post(
            "/api/matches/ghost/turns/1/move",
            json={"move": {"type": "place", "position": [0, 0]}},
        ).status_code == 404

        # create, then an illegal move -> 400
        client.post("/api/matches", json={
            "match_id": "e2", "game": "tictactoe",
            "participants": [
                {"id": "bot", "kind": "local", "adapter": "first_empty_bot"},
                {"id": "human", "kind": "remote"},
            ],
            "config": {"max_turns": 9},
        })
        st = client.get("/api/matches/e2/state").json()
        bad = client.post(f"/api/matches/e2/turns/{st['to_move_turn']}/move",
                          json={"move": {"type": "place", "position": [0, 0]}})  # bot took [0,0]
        assert bad.status_code == 400
        assert bad.json()["detail"]["code"] == "illegal_move"

    def test_viewer_endpoints(self, monkeypatch):
        # A6: config/log/result in the viewer's shape, fed from the envelope.
        client = self._client(monkeypatch)
        client.post("/api/matches", json={
            "match_id": "v1", "game": "tictactoe",
            "participants": [{"id": "bot", "kind": "local", "adapter": "first_empty_bot"},
                             {"id": "human", "kind": "remote"}],
            "config": {"max_turns": 9},
        })
        for _ in range(12):  # play to completion
            st = client.get("/api/matches/v1/state").json()
            if st["status"] != "in_progress":
                break
            t = st["to_move_turn"]
            board = client.get(f"/api/matches/v1/turns/{t}").json()["state"]["board"]
            pos = next([r, c] for r in range(3) for c in range(3) if board[r][c] is None)
            client.post(f"/api/matches/v1/turns/{t}/move", json={"move": {"type": "place", "position": pos}})

        cfg = client.get("/api/matches/v1/config").json()
        assert cfg["game"]["name"] == "tictactoe"
        assert any(a["agent_id"] == "bot" for a in cfg["agents"])
        log = client.get("/api/matches/v1/log").json()
        assert isinstance(log, list) and len(log) >= 1 and all("turn" in e for e in log)
        result = client.get("/api/matches/v1/result").json()
        assert result["outcome"] in ("win", "draw")
        assert client.get("/api/matches/ghost/config").status_code == 404

    def test_kind_field(self, monkeypatch):
        client = self._client(monkeypatch)
        parts = [{"id": "a", "kind": "remote"}, {"id": "b", "kind": "remote"}]
        # default = practice
        r = client.post("/api/matches", json={"match_id": "k1", "game": "tictactoe",
                                              "participants": parts})
        assert r.json()["kind"] == "practice"
        # explicit published round-trips through /state
        client.post("/api/matches", json={"match_id": "k2", "game": "tictactoe",
                                          "kind": "published", "participants": parts})
        assert client.get("/api/matches/k2/state").json()["kind"] == "published"
        # invalid -> 400
        bad = client.post("/api/matches", json={"match_id": "k3", "game": "tictactoe",
                                               "kind": "bogus", "participants": parts})
        assert bad.status_code == 400


class TestA5Payload:
    """A5: the turn payload carries the full local-parity prompt + the D-089
    four-field contract (present_agents / incoming_messages / opponent_actions /
    state). Exercised with two remote creatures — the product shape."""

    def test_two_remote_creatures_payload(self, tmp_path):
        r = _StubRedis()
        participants = [
            {"id": "aria", "kind": "remote", "display": "Aria"},
            {"id": "kestrel", "kind": "remote", "display": "Kestrel"},
        ]
        env = open_match(r, match_id="m3", game_name="tictactoe",
                         participants=participants, config={"max_turns": 9},
                         base_dir=str(tmp_path))
        # no local turns -> halt immediately at aria's turn 1
        assert env["to_move"] == "aria" and env["to_move_turn"] == 1
        tp1 = turn_payload(env)
        assert isinstance(tp1["prompt"], str) and "aria" in tp1["prompt"]  # agent-specific prompt
        # response-mode framing — no file-write line that confuses a remote creature
        assert "moves/turn" not in tp1["prompt"]
        assert "Write your move JSON to" not in tp1["prompt"]
        assert "Reply with ONLY" in tp1["prompt"]
        assert tp1["opponent_actions"] == [] and tp1["incoming_messages"] == []  # nothing yet

        # aria plays with dialogue
        env = submit_move(r, "m3", turn=1, move={"type": "place", "position": [0, 0]},
                          dialogue="Taking the corner.", base_dir=str(tmp_path))
        assert env["to_move"] == "kestrel" and env["to_move_turn"] == 2

        tp2 = turn_payload(env)
        # kestrel receives aria's action (humoral immune) + dialogue (immune) + identity (bonds)
        assert any(a["agent_id"] == "aria" and a["move"]["position"] == [0, 0]
                   for a in tp2["opponent_actions"])
        assert any(m["agent_id"] == "aria" and "corner" in m["message"]
                   for m in tp2["incoming_messages"])
        assert any(p["id"] == "aria" for p in tp2["present_agents"])
        assert isinstance(tp2["prompt"], str) and "kestrel" in tp2["prompt"]


class TestSSE:
    """A2: the SSE your_turn stream over the driver (poll remains the fallback)."""

    def _client(self, monkeypatch):
        from fastapi.testclient import TestClient
        from server.app import app
        register_adapter("first_empty_bot", FirstEmptyCellBot)
        # Cap the stream short: TestClient doesn't cancel the server generator on
        # client disconnect the way a real uvicorn worker does, so the stream
        # would otherwise run to SSE_MAX_SECONDS before teardown completes.
        monkeypatch.setattr("server.routes.SSE_MAX_SECONDS", 2)
        monkeypatch.setattr("server.routes.SSE_POLL_SECONDS", 0.05)
        stub = _StubRedis()
        monkeypatch.setattr("server.routes._get_redis", lambda: stub)
        return TestClient(app)

    def test_your_turn_emitted_to_active_remote(self, monkeypatch):
        import json as _j
        client = self._client(monkeypatch)
        client.post("/api/matches", json={
            "match_id": "sse1", "game": "tictactoe",
            "participants": [{"id": "aria", "kind": "remote"}, {"id": "kestrel", "kind": "remote"}],
            "config": {"max_turns": 9},
        })
        # aria is to_move on turn 1 -> first event is an immediate your_turn
        with client.stream("GET", "/api/matches/sse1/events?as=aria") as r:
            assert r.status_code == 200
            evt = None
            for line in r.iter_lines():
                if line.startswith("data:"):
                    evt = _j.loads(line[len("data:"):].strip())
                    break
            assert evt is not None and evt["type"] == "your_turn"
            assert evt["turn"] == 1 and evt["deadline"] == 180

    def test_events_unknown_match_404(self, monkeypatch):
        client = self._client(monkeypatch)
        assert client.get("/api/matches/ghost/events?as=x").status_code == 404


class TestB1Identity:
    """B1: a registered creature gets a stable opaque creature_id, surfaced in
    present_agents + the match record (the re-recognition key)."""

    def _client(self, monkeypatch):
        from fastapi.testclient import TestClient
        from server.app import app
        stub = _StubRedis()  # one shared store across requests
        monkeypatch.setattr("server.routes._get_redis", lambda: stub)
        return TestClient(app)

    def test_register_and_surface(self, monkeypatch):
        client = self._client(monkeypatch)
        a = client.post("/api/creatures", json={"display_name": "Aria"}).json()
        b = client.post("/api/creatures", json={"display_name": "Kestrel"}).json()
        assert a["creature_id"].startswith("cr_") and a["creature_id"] != b["creature_id"]
        assert client.get(f"/api/creatures/{a['creature_id']}").json()["display_name"] == "Aria"
        assert client.get("/api/creatures/cr_nope").status_code == 404

        env = client.post("/api/matches", json={
            "match_id": "b1", "game": "tictactoe",
            "participants": [
                {"id": "aria", "kind": "remote", "creature_id": a["creature_id"]},
                {"id": "kestrel", "kind": "remote", "creature_id": b["creature_id"]},
            ]}).json()
        # the match record carries the stable id
        parts = client.get("/api/matches/b1/state").json()["participants"]
        assert {p["id"]: p["creature_id"] for p in parts} == {
            "aria": a["creature_id"], "kestrel": b["creature_id"]}
        # the turn payload surfaces the OPPONENT's stable id (B2 re-recognition key)
        tp = client.get(f"/api/matches/b1/turns/{env['to_move_turn']}").json()
        opp = tp["present_agents"][0]
        assert opp["id"] != env["to_move"]
        assert opp["creature_id"] in (a["creature_id"], b["creature_id"])

    def test_unknown_creature_id_rejected(self, monkeypatch):
        client = self._client(monkeypatch)
        r = client.post("/api/matches", json={
            "match_id": "b2", "game": "tictactoe",
            "participants": [{"id": "x", "kind": "remote", "creature_id": "cr_ghost"},
                             {"id": "y", "kind": "remote"}]})
        assert r.status_code == 400


def test_games_roster():
    """GET /api/games surfaces player-count bounds for client-side filtering."""
    from fastapi.testclient import TestClient
    from server.app import app
    games = {g["id"]: (g["min_players"], g["max_players"])
             for g in TestClient(app).get("/api/games").json()}
    assert games["tictactoe"] == (2, 2)
    assert games["chess"] == (2, 2)
    assert games["trustgame"] == (2, 2)   # iterated PD
    assert games["poker"] == (2, 6)
    assert games["codenames"] == (4, 4)
    assert games["avalon"] == (5, 10)
    assert games["deduction"] == (1, 1)
    two_player = {gid for gid, (mn, mx) in games.items() if mn <= 2 <= mx}
    assert {"tictactoe", "chess", "trustgame", "poker"} <= two_player
    assert "codenames" not in two_player and "avalon" not in two_player
