"""Phase 1 acceptance (RFP A4): a hosted match of 1 local bot + 1 remote
participant completes end-to-end via the event-driven driver, with the remote
driven over the poll path (open_match -> submit_move)."""

import json
from datetime import datetime, timezone
from pathlib import Path

from lxm.adapters.registry import register_adapter
from server.match_driver import (
    open_match, submit_move, turn_payload, reap_if_timed_out, MatchError,
)
from server.match_store import load_match, save_match


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

    def zadd(self, k, score, member):
        self._d.setdefault(k, {})[member] = score


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


class TestHostedLedger:
    """A hosted match that finishes must reach the durable ledger on its own.

    The live envelope expires after 24h, so a `published` match that nobody
    explicitly submits used to leave no lasting record of who played whom.
    """

    def _client(self, monkeypatch):
        from fastapi.testclient import TestClient
        from server.app import app
        register_adapter("first_empty_bot", FirstEmptyCellBot)
        stub = _StubRedis()
        monkeypatch.setattr("server.routes._get_redis", lambda: stub)
        return TestClient(app), stub

    def _play_out(self, client, match_id):
        for _ in range(12):
            st = client.get(f"/api/matches/{match_id}/state").json()
            if st["status"] != "in_progress":
                return st
            t = st["to_move_turn"]
            board = client.get(f"/api/matches/{match_id}/turns/{t}").json()["state"]["board"]
            pos = next([r, c] for r in range(3) for c in range(3) if board[r][c] is None)
            client.post(f"/api/matches/{match_id}/turns/{t}/move",
                        json={"move": {"type": "place", "position": pos}})
        raise AssertionError("match did not finish")

    def _open(self, client, match_id, kind):
        return client.post("/api/matches", json={
            "match_id": match_id, "game": "tictactoe", "kind": kind,
            "participants": [{"id": "bot", "kind": "local", "adapter": "first_empty_bot"},
                             {"id": "human", "kind": "remote"}],
            "config": {"max_turns": 9},
        })

    def test_published_match_reaches_the_ledger(self, monkeypatch):
        client, stub = self._client(monkeypatch)
        self._open(client, "L1", "published")
        final = self._play_out(client, "L1")
        assert final["status"] == "complete"

        record = stub.get_json("lxm:matches:L1")
        assert record is not None, "completed published match left no ledger record"
        assert record["game"] == "tictactoe"
        assert record["result"]["outcome"] == final["result"]["outcome"]
        assert {a["agent_id"] for a in record["agents"]} == {"bot", "human"}
        assert record["duration_seconds"] >= 0

    def test_practice_match_stays_ephemeral(self, monkeypatch):
        client, stub = self._client(monkeypatch)
        self._open(client, "L2", "practice")
        self._play_out(client, "L2")
        assert stub.get_json("lxm:matches:L2") is None

    def test_elo_moves_once_however_often_the_result_is_polled(self, monkeypatch):
        client, stub = self._client(monkeypatch)
        for aid in ("bot", "human"):
            client.post("/api/agents", json={"agent_id": aid, "display_name": aid,
                                             "adapter": "test", "model": "test",
                                             "games": ["tictactoe"]})
        self._open(client, "L3", "published")
        self._play_out(client, "L3")

        after_first = {aid: stub.get_json(f"lxm:agents:{aid}")["elo"]["tictactoe"]
                       for aid in ("bot", "human")}
        assert after_first != {"bot": 1500, "human": 1500}, "ELO never moved"

        for _ in range(3):  # spectators keep polling a finished match
            client.get("/api/matches/L3/state")
        after_polls = {aid: stub.get_json(f"lxm:agents:{aid}")["elo"]["tictactoe"]
                       for aid in ("bot", "human")}
        assert after_polls == after_first

        games = stub.get_json("lxm:agents:bot")["stats"]["tictactoe"]
        assert games["wins"] + games["losses"] + games["draws"] == 1

    def test_reaped_match_is_recorded_too(self, monkeypatch):
        # A seat that walks away is ended by the lazy reaper on someone else's
        # poll — the withdrawal path still owes the ledger a record.
        client, stub = self._client(monkeypatch)
        self._open(client, "L4", "published")

        import server.routes as routes
        env = stub.get_json("lxm:match:L4")
        finished = {**env, "status": "complete", "to_move": None, "to_move_kind": None,
                    "result": {"outcome": "forfeit", "winner": "bot",
                               "scores": {"bot": 1, "human": 0},
                               "summary": "human forfeited"}}
        monkeypatch.setattr(routes, "reap_if_timed_out", lambda *a, **k: finished)

        client.get("/api/matches/L4/state")
        record = stub.get_json("lxm:matches:L4")
        assert record is not None, "a reaper-ended match left no ledger record"
        assert record["result"]["outcome"] == "forfeit"


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


def test_blockworld_scenario_discovery():
    """GET /api/games/blockworld/scenarios lists selectable scenarios with seat
    counts + a multiplayer/solo category, so a client can pick a scenario_id."""
    from fastapi.testclient import TestClient
    from server.app import app
    client = TestClient(app)

    alls = client.get("/api/games/blockworld/scenarios").json()
    by_id = {s["scenario_id"]: s for s in alls}
    assert len(alls) >= 20  # the full family

    # social-dilemma scenarios are 2-seat multiplayer
    pd = by_id["prisoners_dilemma_01"]
    assert pd["players"] == 2 and pd["category"] == "multiplayer"
    assert pd["mode"] == "prisoners_dilemma"
    assert by_id["commons_harvest_01"]["category"] == "multiplayer"

    # shelter (single agent_start) is solo
    assert by_id["shelter_01"]["players"] == 1
    assert by_id["shelter_01"]["category"] == "solo"

    # every entry has a derivable seat count + valid category
    for s in alls:
        assert isinstance(s["players"], int) and s["players"] >= 1
        assert s["category"] in ("multiplayer", "solo")

    # ?category=multiplayer filters to creatures-meet scenarios
    mp = client.get("/api/games/blockworld/scenarios?category=multiplayer").json()
    assert mp and all(s["category"] == "multiplayer" for s in mp)
    assert {s["scenario_id"] for s in mp} >= {"prisoners_dilemma_01", "commons_harvest_01",
                                              "stag_hunt_repeated_01", "pure_coord_01"}
    assert "shelter_01" not in {s["scenario_id"] for s in mp}


class AlwaysFailBot:
    """Local bot that never emits a parseable move — exhausts retries to force
    the timeout/forfeit path."""

    def __init__(self, agent_config):
        self._agent_id = agent_config["agent_id"]
        self.brain_capabilities = ["json_emit"]

    def invoke(self, match_dir, prompt):
        return {"stdout": "not a move", "stderr": "", "exit_code": 0, "timed_out": False}

    def on_match_end(self, *args, **kwargs):
        pass


class TestNCreatureAllRemote:
    """N>2 all-external (RFP generalization): a 5-creature all-remote avalon
    match runs to completion over the poll path, per-seat private info stays
    masked in the structured `state` field (H1), a no-show seat is reaped (H2),
    and an N>2 forfeit yields no arbitrary winner (H3)."""

    def _avalon5(self, r, tmp_path, match_id="av5", **cfg):
        parts = [{"id": f"p{i}", "kind": "remote", "display": f"P{i}"} for i in range(5)]
        config = {"max_turns": 120}
        config.update(cfg)
        return open_match(r, match_id=match_id, game_name="avalon",
                          participants=parts, config=config, base_dir=str(tmp_path))

    @staticmethod
    def _legal_move(cur):
        """A legal move for whatever phase the (single) active seat is in. All
        seats approve + all quests succeed -> Good wins in 3 quests (terminates
        regardless of the random role assignment)."""
        phase = cur.get("phase")
        if phase == "propose":
            qn = cur.get("quest_number", 1)
            sizes = cur.get("quest_sizes", [2, 3, 2, 3, 3])
            size = sizes[qn - 1] if 0 <= qn - 1 < len(sizes) else 2
            return {"type": "proposal", "team": cur.get("seat_order", [])[:size]}
        if phase == "vote":
            return {"type": "vote", "choice": "approve"}
        if phase == "quest":
            return {"type": "quest_action", "choice": "success"}
        return {"type": "pass"}

    def test_five_remote_completes_and_no_state_leak(self, tmp_path):
        r = _StubRedis()
        env = self._avalon5(r, tmp_path)
        assert env["status"] == "in_progress" and env["to_move_kind"] == "remote"
        assert len(env["participants"]) == 5

        seen = set()
        for _ in range(400):
            if env["status"] != "in_progress":
                break
            seat = env["to_move"]
            seen.add(seat)
            tp = turn_payload(env)
            cur = tp["state"] or {}
            players = cur.get("players", {})
            # H1: the structured `state` field is per-seat filtered — a Good seat
            # must not see any other seat's role or the evil roster.
            if players.get(seat, {}).get("role") == "good":
                leaked = {pid: p.get("role") for pid, p in players.items()
                          if pid != seat and p.get("role") != "unknown"}
                assert not leaked, f"role leak to Good seat {seat}: {leaked}"
                assert not cur.get("evil_players"), f"evil roster leak to {seat}"
            env = submit_move(r, "av5", turn=env["to_move_turn"],
                              move=self._legal_move(cur), base_dir=str(tmp_path))

        assert env["status"] == "complete", f"stuck at {env.get('to_move')}"
        assert env["result"] is not None
        assert len(seen) == 5  # every seat acted -> N>2 seat cycling works

    def test_reaper_advances_no_show_seat(self, tmp_path):
        r = _StubRedis()
        env = self._avalon5(r, tmp_path, match_id="av5r")
        seat0, turn0 = env["to_move"], env["to_move_turn"]
        assert env["to_move_kind"] == "remote"

        # fresh -> within deadline -> no reaping (unchanged)
        same = reap_if_timed_out(r, "av5r", envelope=load_match(r, "av5r"),
                                 base_dir=str(tmp_path))
        assert same["to_move"] == seat0 and same["to_move_turn"] == turn0

        # backdate the clock past the deadline -> reaper injects the fallback move
        stale = load_match(r, "av5r")
        stale["updated_at"] = "2000-01-01T00:00:00+00:00"
        advanced = reap_if_timed_out(r, "av5r", envelope=stale, base_dir=str(tmp_path))
        assert advanced["status"] == "complete" or advanced["to_move_turn"] > turn0
        assert load_match(r, "av5r")["to_move_turn"] == advanced["to_move_turn"]  # persisted

    def test_late_fetch_delivers_instead_of_reaping_itself(self, monkeypatch):
        """The route ordering, not just the pieces: a seat fetching its own turn
        after the deadline must receive the turn, not a 409 for a turn the same
        request took from it.

        The first version of this fix stamped delivery *after* the reaper ran, so
        a first fetch still had no delivered_at, fell back to updated_at, and the
        seat was reaped by its own request — the exact bug, still present. Unit
        tests on reap_if_timed_out and _stamp_delivery both passed; only the path
        showed it."""
        from fastapi.testclient import TestClient

        from server.app import app
        register_adapter("first_empty_bot", FirstEmptyCellBot)
        stub = _StubRedis()
        monkeypatch.setattr("server.routes._get_redis", lambda: stub)
        client = TestClient(app)
        client.post("/api/matches", json={
            "match_id": "lf1", "game": "tictactoe",
            "participants": [{"id": "bot", "kind": "local", "adapter": "first_empty_bot"},
                             {"id": "human", "kind": "remote"}],
            "config": {"max_turns": 9},
        })
        env = stub.get_json("lxm:match:lf1")
        turn = env["to_move_turn"]

        # Nobody touched the match for far longer than the deadline.
        env["updated_at"] = "2000-01-01T00:00:00+00:00"
        stub.set_json("lxm:match:lf1", env)

        resp = client.get(f"/api/matches/lf1/turns/{turn}")
        assert resp.status_code == 200, f"own late fetch was reaped: {resp.text}"
        assert resp.json()["turn"] == turn
        assert stub.get_json("lxm:match:lf1")["delivered_turn"] == turn

        # A seat that never fetches is still reapable from updated_at — the
        # /state path the reaper docstring describes stays intact.
        stale = stub.get_json("lxm:match:lf1")
        stale.pop("delivered_at", None)
        stale.pop("delivered_turn", None)
        stale["updated_at"] = "2000-01-01T00:00:00+00:00"
        stub.set_json("lxm:match:lf1", stale)
        client.get("/api/matches/lf1/state")
        after = stub.get_json("lxm:match:lf1")
        assert after["status"] == "complete" or after["to_move_turn"] > turn

    def test_stale_turn_409_says_whose_problem_it_is(self, monkeypatch):
        """A 409 that only reports a mismatch reads as "you asked wrong" — that is
        exactly how the self-reap bug was first misread, costing the caller time
        on a healthy client. A past turn must say it was already played and name
        the deadline; a finished match must say it is finished."""
        from fastapi.testclient import TestClient

        from server.app import app
        register_adapter("first_empty_bot", FirstEmptyCellBot)
        stub = _StubRedis()
        monkeypatch.setattr("server.routes._get_redis", lambda: stub)
        client = TestClient(app)
        client.post("/api/matches", json={
            "match_id": "d409", "game": "tictactoe",
            "participants": [{"id": "bot", "kind": "local", "adapter": "first_empty_bot"},
                             {"id": "human", "kind": "remote"}],
            "config": {"max_turns": 9},
        })
        turn = stub.get_json("lxm:match:d409")["to_move_turn"]

        # Asking for a turn that has moved on: the fallback is named, not implied.
        client.post(f"/api/matches/d409/turns/{turn}/move",
                    json={"move": {"type": "place", "position": [1, 1]}})
        past = client.get(f"/api/matches/d409/turns/{turn}")
        assert past.status_code == 409
        detail = past.json()["detail"]
        assert "already been played" in detail and "deadline" in detail

        # And a finished match says so rather than "no remote turn is pending".
        env = stub.get_json("lxm:match:d409")
        env["status"] = "complete"
        env["to_move"] = env["to_move_kind"] = env["to_move_turn"] = None
        stub.set_json("lxm:match:d409", env)
        done = client.get("/api/matches/d409/turns/1")
        assert done.status_code == 409
        assert "already complete" in done.json()["detail"]

    def test_delivery_starts_the_move_clock(self, tmp_path):
        """Envelope 015: the deadline runs from when the seat was handed the board.

        Before this, `elapsed` was measured from turn assignment and GET
        /turns/{n} ran the reaper first — so a participant fetching its own turn
        late was reaped by that very request, spending network time out of the
        mover's budget. Delivery is stamped once per turn; a seat that never
        fetched still falls back to updated_at and stays reapable."""
        r = _StubRedis()
        env = self._avalon5(r, tmp_path, match_id="av5d")
        seat0, turn0 = env["to_move"], env["to_move_turn"]

        # Assignment is old, but the board was just handed over -> not reaped.
        stale = load_match(r, "av5d")
        stale["updated_at"] = "2000-01-01T00:00:00+00:00"
        stale["delivered_turn"] = turn0
        stale["delivered_at"] = datetime.now(timezone.utc).isoformat()
        same = reap_if_timed_out(r, "av5d", envelope=stale, base_dir=str(tmp_path))
        assert same["to_move"] == seat0 and same["to_move_turn"] == turn0

        # Delivered long ago -> the seat really did sit on it -> reaped.
        expired = load_match(r, "av5d")
        expired["updated_at"] = "2000-01-01T00:00:00+00:00"
        expired["delivered_turn"] = turn0
        expired["delivered_at"] = "2000-01-01T00:00:00+00:00"
        advanced = reap_if_timed_out(r, "av5d", envelope=expired, base_dir=str(tmp_path))
        assert advanced["status"] == "complete" or advanced["to_move_turn"] > turn0

    def test_delivery_stamp_is_once_per_turn(self, tmp_path):
        """A reconnecting participant re-fetching the same turn must not push its
        own deadline out (Ludex refinement 1), and a stamp left over from an
        earlier turn must not shield the current one."""
        from server import routes

        r = _StubRedis()
        env = self._avalon5(r, tmp_path, match_id="av5s")
        turn0 = env["to_move_turn"]

        live = load_match(r, "av5s")
        routes._stamp_delivery(r, "av5s", live, turn0)
        first = load_match(r, "av5s")["delivered_at"]

        live2 = load_match(r, "av5s")
        live2["delivered_at"] = "2000-01-01T00:00:00+00:00"
        save_match(r, "av5s", live2)
        routes._stamp_delivery(r, "av5s", live2, turn0)          # same turn again
        assert load_match(r, "av5s")["delivered_at"] == "2000-01-01T00:00:00+00:00"
        assert first  # the first delivery was recorded

        # A stamp for a different turn does not count for the current one.
        old = load_match(r, "av5s")
        old["updated_at"] = "2000-01-01T00:00:00+00:00"
        old["delivered_turn"] = turn0 - 1
        old["delivered_at"] = datetime.now(timezone.utc).isoformat()
        advanced = reap_if_timed_out(r, "av5s", envelope=old, base_dir=str(tmp_path))
        assert advanced["status"] == "complete" or advanced["to_move_turn"] > turn0

    def test_n_player_forfeit_has_no_arbitrary_winner(self, tmp_path):
        # H3: a seat exhausting retries under timeout_action="forfeit" must not
        # crown an arbitrary other seat in an N>2 game; scores cover all seats.
        register_adapter("always_fail_bot", AlwaysFailBot)
        r = _StubRedis()
        parts = [{"id": "p0", "kind": "local", "adapter": "always_fail_bot"}] + \
                [{"id": f"p{i}", "kind": "remote"} for i in range(1, 5)]
        env = open_match(r, match_id="avf", game_name="avalon", participants=parts,
                         config={"timeout_action": "forfeit", "max_retries": 1,
                                 "max_turns": 120}, base_dir=str(tmp_path))
        assert env["status"] == "complete"
        assert env["result"]["outcome"] == "forfeit"
        assert env["result"]["winner"] is None       # not other_agents[0]
        assert set(env["result"]["scores"]) == {"p0", "p1", "p2", "p3", "p4"}  # all ids, not `marks`

    def test_codenames_four_remote_inline_path(self, tmp_path):
        # codenames had no auto team/role assignment -> an all-remote match left
        # teams empty -> build_inline_prompt returned None (file-mode fallback +
        # empty state_readable) and every move was rejected ('Expected None').
        # _build_teams now default-assigns the four seats.
        r = _StubRedis()
        parts = [{"id": f"p{i}", "kind": "remote", "display": f"P{i}"} for i in range(4)]
        env = open_match(r, match_id="cn4", game_name="codenames",
                         participants=parts, base_dir=str(tmp_path))
        cur = env["orchestrator"]["game_state"]["current"]
        assert cur["teams"] == {"red": {"spymaster": "p0", "guesser": "p1"},
                                "blue": {"spymaster": "p2", "guesser": "p3"}}
        assert env["to_move"] == "p0"  # red spymaster acts first

        tp = turn_payload(env)
        assert "moves/turn_" not in tp["prompt"]      # inline, not the file-mode stub
        assert "SPYMASTER" in tp["prompt"]
        assert (tp["state_readable"] or "").strip()   # not empty

        # spymaster clue accepted -> advances to the red guesser
        env = submit_move(r, "cn4", turn=env["to_move_turn"],
                          move={"type": "clue", "word": "ocean", "number": 2},
                          base_dir=str(tmp_path))
        assert env["to_move"] == "p1" and env["to_move_turn"] == 2

        # guesser guess accepted (any unrevealed board word)
        board = turn_payload(env)["state"]["board"]
        word = next(board[i][j]["word"] for i in range(5) for j in range(5)
                    if not board[i][j]["revealed"])
        env = submit_move(r, "cn4", turn=env["to_move_turn"],
                          move={"type": "guess", "word": word}, base_dir=str(tmp_path))
        assert env["status"] in ("in_progress", "complete")

    def test_blockworld_social_scenario_all_remote(self, tmp_path):
        # Phase 2: a blockworld social-dilemma scenario runs all-remote — inline
        # prompt (not file stub), real moves accepted, seats cycle p0<->p1. The
        # driver passes scenario_id through; the engine self-seeds 2 agents from
        # the scenario's agent_starts.
        r = _StubRedis()
        parts = [{"id": "p0", "kind": "remote"}, {"id": "p1", "kind": "remote"}]
        env = open_match(r, match_id="bwpd", game_name="blockworld", participants=parts,
                         config={"scenario_id": "prisoners_dilemma_01"},
                         base_dir=str(tmp_path))
        assert env["status"] == "in_progress" and env["to_move"] == "p0"

        tp = turn_payload(env)
        assert "moves/turn_" not in tp["prompt"]          # inline, not file stub
        assert (tp["state_readable"] or "").strip()
        # the REQUESTED scenario actually loaded (not the default solo shelter) —
        # the bug Ludex caught: scenario_id was dropped, every match got shelter
        assert "dilemma" in tp["prompt"].lower() or "prisoner" in tp["prompt"].lower()
        assert "shelter" not in tp["prompt"].lower()
        # arbitrary seat ids (p0/p1, not the scenario's hardcoded "a"/"b") land on
        # the two DISTINCT declared start positions
        agents = env["orchestrator"]["game_state"]["current"]["agents"]
        xs = {aid: agents[aid]["x"] for aid in agents}
        assert len(set(xs.values())) == 2, f"seats overlap: {xs}"

        wait = {"type": "action", "verb": "wait"}
        seats = []
        for _ in range(4):
            if env["status"] != "in_progress":
                break
            seats.append(env["to_move"])
            env = submit_move(r, "bwpd", turn=env["to_move_turn"], move=wait,
                              base_dir=str(tmp_path))
        assert seats == ["p0", "p1", "p0", "p1"]          # real moves accepted + cycling

    def test_blockworld_default_scenario_when_unspecified(self, tmp_path):
        # No scenario_id -> the engine's default (solo shelter) still loads.
        r = _StubRedis()
        env = open_match(r, match_id="bwdef", game_name="blockworld",
                         participants=[{"id": "solo", "kind": "remote"}],
                         config={}, base_dir=str(tmp_path))
        assert "shelter" in turn_payload(env)["prompt"].lower()

    def test_deduction_scenario_id_honored(self, tmp_path):
        # Same constructor-config bug class: DeductionGame(scenario_id=...).
        r = _StubRedis()
        env = open_match(r, match_id="ded2", game_name="deduction",
                         participants=[{"id": "solo", "kind": "remote"}],
                         config={"scenario_id": "mystery_002"}, base_dir=str(tmp_path))
        cur = env["orchestrator"]["game_state"]["current"]
        assert cur.get("scenario_id") == "mystery_002"
