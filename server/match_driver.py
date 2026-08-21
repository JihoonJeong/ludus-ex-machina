"""Event-driven driver for hosted cross-machine matches (RFP Stage A: A1/A3/A4).

Turns the in-process Orchestrator into a request-driven match plane:

  * `open_match`  — create a match, auto-play any leading LOCAL turns, and halt
                    at the first REMOTE turn (or completion).
  * `submit_move` — apply a remote participant's move, then auto-play LOCAL
                    turns until the next remote turn (or completion).

State lives in Redis (`server.match_store`) between requests, so "await a
remote move" is just the gap between two HTTP calls — no held worker, and a
match survives a server restart. The local in-process path (run_match.py) is
unaffected; this reuses `Orchestrator._process_turn` unchanged.

Persistence model: each call rehydrates an Orchestrator into a throwaway
match_dir (reusing the file-based per-turn logic), drives, then snapshots the
mutable state back into the Redis envelope. The match_dir is scratch.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lxm.adapters.registry import get_adapter_class, get_game_class
from lxm.adapters.remote import RemoteParticipant
from lxm.orchestrator import Orchestrator

from .match_store import load_match, save_match


class MatchError(Exception):
    """A driver-level error with a machine code (routes map it to an HTTP status)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _scratch_dir(base_dir: str | None):
    """Yield a working directory for one driver call. If `base_dir` is given it
    is used as-is (the caller owns cleanup — e.g. tests); otherwise a temp dir
    is created and removed afterwards. The match_dir is scratch: durable state
    lives in the Redis snapshot, not on disk."""
    if base_dir is not None:
        yield base_dir
    else:
        tmp = tempfile.mkdtemp(prefix="lxm_match_")
        try:
            yield tmp
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def make_participant_adapter(p: dict):
    """Build the adapter for one participant: a registry adapter for a local
    participant, a RemoteParticipant placeholder for a remote one."""
    if p.get("kind") == "remote":
        return RemoteParticipant(p["id"], p.get("display"))
    AdapterCls = get_adapter_class(p.get("adapter", "rule_bot"))
    cfg = {"agent_id": p["id"], "model": p.get("model", "medium")}
    cfg.update(p.get("agent_config", {}))
    return AdapterCls(cfg)


def _instantiate_game(game_name: str, match_config: dict):
    """Build the game engine, honoring per-game constructor config carried in
    match_config (e.g. blockworld/deduction `scenario_id`, avalon `role_seed`).

    The hosted path used `get_game_class(game_name)()` with no args, so a game
    whose __init__ takes config (BlockworldGame(scenario_id=...),
    DeductionGame(scenario_id=...)) always fell back to its default scenario —
    a 2-seat blockworld match silently loaded the solo shelter scenario. We pass
    only the constructor params the engine actually declares (inspected), so
    no-arg games (tictactoe/chess/...) are unaffected and a future game's
    constructor params are picked up automatically. Mirrors the local/CLI path
    (`scripts/run_match.py`), which passes scenario_id into the constructor."""
    import inspect
    cls = get_game_class(game_name)
    try:
        params = set(inspect.signature(cls.__init__).parameters) - {"self"}
    except (TypeError, ValueError):
        params = set()
    kwargs = {k: match_config[k] for k in params if k in match_config}
    return cls(**kwargs)


def _build_match_config(match_id: str, game_name: str, participants: list[dict],
                        config: dict) -> dict:
    agents = [{"agent_id": p["id"], "display_name": p.get("display", p["id"]), "seat": i}
              for i, p in enumerate(participants)]
    mc = {
        "protocol_version": "lxm-v0.2",
        "match_id": match_id,
        "game": {"name": game_name, "version": "1.0"},
        "time_model": {
            "type": "turn_based",
            "turn_order": config.get("turn_order", "sequential"),
            "max_turns": config.get("max_turns", 100),
            "timeout_seconds": config.get("timeout_seconds", 180),
            "timeout_action": config.get("timeout_action", "no_op"),
            "max_retries": config.get("max_retries", 2),
        },
        "agents": agents,
        "history": {"recent_moves_count": config.get("recent_moves_count", 20)},
        "invocation": {"mode": "inline", "discovery_turns": 0},
    }
    # Pass through game-specific extras (deduction scenario, codenames teams, ...).
    for k in ("scenario_id", "role_seed", "teams", "role_shells", "role_voice_shells", "deck"):
        if k in config:
            mc[k] = config[k]
    return mc


# Game inline prompts carry a file-mode submission line ("Do NOT read any
# files. Write your move JSON to: moves/turn_N_agent.json"). Locally the move is
# collected from that file OR from stdout, so it's harmless. A remote creature
# has no match_dir, and the "write a file" framing makes some creatures describe/
# "write" a file instead of emitting the move inline — no parseable move (Ludex
# Cody, A5 integration 2026-06-14). Rewrite that line to response mode for the
# cross-machine path only; local matches are untouched (parse_path data intact).
_FILE_FRAMING = re.compile(r"Do NOT read any files\.[^\n]*")


def _to_response_mode(prompt: str) -> str:
    """Rewrite a local inline prompt's file-mode submission line into response
    mode for a remote creature. The 'Copy this exactly: {json}' line that
    follows already shows the envelope to emit."""
    return _FILE_FRAMING.sub(
        "Reply with ONLY your move JSON in your response — do not read or write any files.",
        prompt,
    )


def _drive(orch: Orchestrator, game_state: dict, match_dir: Path) -> dict:
    """Auto-play LOCAL turns until the active participant is REMOTE (halt) or
    the match completes. Returns a drive-outcome dict."""
    while orch._state.turn <= orch._max_turns:
        agent_id = orch._state.get_active_agent(game_state)
        adapter = orch._adapters[agent_id]
        turn = orch._state.turn
        if isinstance(adapter, RemoteParticipant):
            # Build the same prompt a local adapter would receive (rules + state
            # + lxm-v0.2 move format) so the remote creature plays byte-identical
            # to local — the game owner owns the prompt, the client never rebuilds
            # it. Inline-capable games (avalon, poker, ...) yield a self-contained
            # prompt; file-mode-only games (tictactoe) yield the file prompt.
            prompt = _to_response_mode(orch._build_turn_prompt(agent_id, turn, game_state))
            return {"status": "in_progress", "to_move": agent_id,
                    "to_move_kind": "remote", "to_move_turn": turn,
                    "to_move_prompt": prompt,
                    "game_state": game_state, "result": None}
        prompt = orch._build_turn_prompt(agent_id, turn, game_state)
        inv = adapter.invoke(orch._match_dir, prompt)
        outcome = orch._process_turn(game_state, agent_id, turn, inv, match_dir)
        if outcome.terminal:
            return {"status": "complete", "to_move": None, "to_move_kind": None,
                    "to_move_turn": None, "game_state": game_state,
                    "result": outcome.result}
        game_state = outcome.game_state
    result = orch._finalize_max_turns(game_state, match_dir)
    return {"status": "complete", "to_move": None, "to_move_kind": None,
            "to_move_turn": None, "game_state": game_state, "result": result}


def _participants_public(participants: list[dict]) -> list[dict]:
    return [{"id": p["id"], "kind": p.get("kind", "local"),
             "display": p.get("display", p["id"]),
             "creature_id": p.get("creature_id"),  # B1 stable identity (or None)
             "adapter": p.get("adapter"), "model": p.get("model")}
            for p in participants]


def _assemble_envelope(match_id, game_name, match_config, participants, orch,
                       drive, created_at, kind="practice") -> dict:
    return {
        "match_id": match_id,
        "game": game_name,
        "kind": kind,
        "config": match_config,
        "participants": _participants_public(participants),
        "status": drive["status"],
        "to_move": drive["to_move"],
        "to_move_kind": drive["to_move_kind"],
        "to_move_turn": drive["to_move_turn"],
        "to_move_prompt": drive.get("to_move_prompt"),
        "orchestrator": orch.to_snapshot(drive["game_state"]),
        "result": drive["result"],
        "created_at": created_at,
        "updated_at": _now(),
    }


def open_match(redis, *, match_id, game_name, participants, config=None,
               kind="practice", base_dir=None) -> dict:
    """Create a hosted match, auto-play leading local turns, persist, and return
    the envelope (halted at the first remote turn, or completed)."""
    config = config or {}
    match_config = _build_match_config(match_id, game_name, participants, config)
    game = _instantiate_game(game_name, match_config)
    adapters = {p["id"]: make_participant_adapter(p) for p in participants}
    orch = Orchestrator(game, match_config, adapters)
    with _scratch_dir(base_dir) as work:
        orch.setup_match(base_dir=work)
        full = json.loads((Path(orch._match_dir) / "state.json").read_text(encoding="utf-8"))
        drive = _drive(orch, full["game"], Path(orch._match_dir))
        env = _assemble_envelope(match_id, game_name, match_config, participants, orch,
                                 drive, created_at=_now(), kind=kind)
    if redis is not None:
        save_match(redis, match_id, env)
    return env


def _rehydrate(envelope: dict, work_dir: str):
    game = _instantiate_game(envelope["game"], envelope["config"])
    adapters = {p["id"]: make_participant_adapter(p) for p in envelope["participants"]}
    orch = Orchestrator(game, envelope["config"], adapters)
    md = Path(work_dir) / envelope["match_id"]
    md.mkdir(parents=True, exist_ok=True)
    orch._match_dir = str(md.resolve())
    game_state = orch.load_snapshot(envelope["orchestrator"])
    return orch, game_state


def _synthesize_invoke(match_id, agent_id, turn, move, dialogue, thoughts) -> dict:
    env = {"protocol": "lxm-v0.2", "match_id": match_id, "agent_id": agent_id,
           "turn": turn, "move": move}
    if dialogue:
        env["message"] = dialogue
    if thoughts:
        env["reasoning"] = thoughts
    return {"stdout": json.dumps(env), "stderr": "", "exit_code": 0, "timed_out": False}


def submit_move(redis, match_id, *, turn, move, dialogue=None, thoughts=None,
                base_dir=None) -> dict:
    """Apply a remote participant's move, auto-play subsequent local turns,
    persist, and return the updated envelope. Raises MatchError on a bad request
    (unknown match, not the remote's turn, out-of-turn, illegal move)."""
    envelope = load_match(redis, match_id) if redis is not None else None
    if envelope is None:
        raise MatchError("not_found", f"match '{match_id}' not found")
    if envelope["status"] != "in_progress":
        raise MatchError("not_active", f"match '{match_id}' is {envelope['status']}")
    if envelope["to_move_kind"] != "remote":
        raise MatchError("not_remote_turn", "the current turn is not a remote participant")
    if int(turn) != envelope["to_move_turn"]:
        raise MatchError("wrong_turn",
                         f"expected turn {envelope['to_move_turn']}, got {turn}")
    to_move = envelope["to_move"]

    with _scratch_dir(base_dir) as work:
        orch, game_state = _rehydrate(envelope, work)

        # Pre-validate so an illegal move is rejected without advancing the
        # match; the client resubmits. (_process_turn re-validates on the happy
        # path.)
        vr = orch._game.validate_move(move, to_move, orch._state.to_dict(game_state))
        if not vr.get("valid"):
            raise MatchError("illegal_move", vr.get("message", "illegal move"))

        inv = _synthesize_invoke(match_id, to_move, turn, move, dialogue, thoughts)
        outcome = orch._process_turn(game_state, to_move, turn, inv, Path(orch._match_dir))
        if outcome.terminal:
            drive = {"status": "complete", "to_move": None, "to_move_kind": None,
                     "to_move_turn": None, "game_state": game_state,
                     "result": outcome.result}
        else:
            drive = _drive(orch, outcome.game_state, Path(orch._match_dir))

        env = _assemble_envelope(match_id, envelope["game"], envelope["config"],
                                 envelope["participants"], orch, drive,
                                 created_at=envelope.get("created_at"),
                                 kind=envelope.get("kind", "practice"))
    if redis is not None:
        save_match(redis, match_id, env)
    return env


def _elapsed_seconds(since_iso: str | None) -> float | None:
    """Seconds since an ISO-8601 timestamp (UTC-aware), or None if unparseable."""
    if not since_iso:
        return None
    try:
        then = datetime.fromisoformat(since_iso)
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds()


def reap_if_timed_out(redis, match_id, *, envelope=None, base_dir=None) -> dict | None:
    """Lazy timeout reaper (H2): if the current REMOTE seat has blown its move
    deadline, inject the game's timeout-fallback move (e.g. avalon
    get_timeout_move: propose first-N / vote reject / quest success) and drive on.

    Request-driven — no background worker. Progress is made whenever any client
    touches the match, so in an all-external match the *other* seats polling
    /state reap a no-show seat rather than letting it stall to the 24h TTL.
    Returns the (possibly advanced) envelope, or None if the match is absent. A
    no-show with zero observers simply waits until someone polls (benign).
    """
    if envelope is None:
        envelope = load_match(redis, match_id) if redis is not None else None
    if envelope is None:
        return None
    if envelope.get("status") != "in_progress" or envelope.get("to_move_kind") != "remote":
        return envelope
    deadline = ((envelope.get("config") or {}).get("time_model") or {}).get("timeout_seconds", 180)
    # The clock starts when the seat was handed the board, not when the turn was
    # assigned (envelope 015, Ludex ACK on measured latency): GET /turns/{n}
    # stamps delivered_at once per turn. Before this, the gap between assignment
    # and delivery came out of the mover's budget — so a participant fetching its
    # own turn could be reaped by that very request. Falling back to updated_at
    # keeps a seat that never fetched reapable exactly as before, which is the
    # path the docstring above describes.
    delivered = (envelope.get("delivered_at")
                 if envelope.get("delivered_turn") == envelope.get("to_move_turn")
                 else None)
    elapsed = _elapsed_seconds(delivered or envelope.get("updated_at"))
    if elapsed is None or elapsed <= deadline:
        return envelope

    # The remote seat exceeded its deadline — apply its fallback move as if it
    # had submitted, then auto-play onward (same path as submit_move).
    to_move = envelope["to_move"]
    turn = envelope["to_move_turn"]
    with _scratch_dir(base_dir) as work:
        orch, game_state = _rehydrate(envelope, work)
        fallback = orch._get_timeout_move(to_move, game_state) or {"type": "pass"}
        inv = _synthesize_invoke(match_id, to_move, turn, fallback, None, None)
        outcome = orch._process_turn(game_state, to_move, turn, inv, Path(orch._match_dir))
        if outcome.terminal:
            drive = {"status": "complete", "to_move": None, "to_move_kind": None,
                     "to_move_turn": None, "game_state": game_state,
                     "result": outcome.result}
        else:
            drive = _drive(orch, outcome.game_state, Path(orch._match_dir))
        env = _assemble_envelope(match_id, envelope["game"], envelope["config"],
                                 envelope["participants"], orch, drive,
                                 created_at=envelope.get("created_at"),
                                 kind=envelope.get("kind", "practice"))
    if redis is not None:
        save_match(redis, match_id, env)
    return env


def _history_since(snap: dict, to_move: str, current_turn: int):
    """Opponent moves + dialogue since the requester's previous accepted turn.

    D-089 channels: `opponent_actions` -> humoral immune (a defect/betray/
    fail-quest is an *action*), `incoming_messages` -> immune (what was *said*).
    The window is (my_last, current_turn): for an alternating game that's the one
    intervening opponent move; before the requester's first move it's every
    opponent move so far. Both are read from the per-turn log; summaries are
    cross-referenced from recent_moves when present.
    """
    log = snap.get("log", [])
    recent = snap.get("lxm", {}).get("recent_moves", [])
    summaries = {(m.get("turn"), m.get("agent_id")): m.get("summary") for m in recent}
    my_last = 0
    for e in log:
        if (e.get("agent_id") == to_move and e.get("result") == "accepted"
                and e.get("turn", 0) < current_turn):
            my_last = max(my_last, e.get("turn", 0))
    actions, messages = [], []
    for e in log:
        t = e.get("turn", 0)
        if not (my_last < t < current_turn) or e.get("agent_id") == to_move:
            continue
        if e.get("result") != "accepted":
            continue
        env = e.get("envelope") or {}
        move = env.get("move")
        if isinstance(move, dict):
            actions.append({"agent_id": e["agent_id"], "turn": t, "move": move,
                            "summary": summaries.get((t, e["agent_id"]))})
        msg = env.get("message")
        if isinstance(msg, str) and msg.strip():
            messages.append({"agent_id": e["agent_id"], "turn": t, "message": msg.strip()})
    return actions, messages


def turn_payload(envelope: dict) -> dict | None:
    """Build the turn payload a remote participant acts on (A3 GET /turns/{n};
    poll path). Carries the frozen D-089 four-field contract: opponent identity
    (present_agents), the readable state (state_readable/state -> physis), the
    opponent's dialogue (incoming_messages -> immune) and actions
    (opponent_actions -> humoral immune) since the requester's last turn."""
    if envelope.get("status") != "in_progress" or envelope.get("to_move_kind") != "remote":
        return None
    snap = envelope["orchestrator"]
    to_move = envelope["to_move"]
    current_turn = envelope["to_move_turn"]
    game = _instantiate_game(envelope["game"], envelope["config"])
    full_state = {"lxm": snap["lxm"], "game": snap["game_state"]}
    if hasattr(game, "filter_state_for_agent"):
        try:
            full_state = game.filter_state_for_agent(full_state, to_move)
        except Exception:
            pass
    try:
        state_readable = game.build_inline_prompt(to_move, full_state, current_turn)
    except Exception:
        state_readable = None
    present = [{"id": p["id"], "display_name": p.get("display", p["id"]),
                "creature_id": p.get("creature_id")}  # B1: re-recognition key
               for p in envelope["participants"] if p["id"] != to_move]
    opponent_actions, incoming_messages = _history_since(snap, to_move, current_turn)
    return {
        "match_id": envelope["match_id"],
        "turn": current_turn,
        "to_move": to_move,
        "prompt": envelope.get("to_move_prompt"),  # full local-parity turn prompt
        "state_readable": state_readable,
        # H1: per-seat filtered current — full_state was masked via
        # filter_state_for_agent above. NOT the raw snapshot, which would leak
        # hidden roles/hands/keys in social-deduction games to a parsing client.
        "state": (full_state.get("game") or {}).get("current"),
        "present_agents": present,           # -> bonds/ToM
        "incoming_messages": incoming_messages,  # -> immune
        "opponent_actions": opponent_actions,    # -> humoral immune
        "deadline": envelope["config"]["time_model"]["timeout_seconds"],
    }
