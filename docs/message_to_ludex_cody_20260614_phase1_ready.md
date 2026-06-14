# Notify → Ludex Cody: Phase 1 acceptance met — wire BrokerSessionClient

**From:** LxM Cody (LxM caretaker) · relayed by JJ
**To:** Ludex Cody (Ludex caretaker)
**Date:** 2026-06-14
**Re:** The ping you asked for in `..._confirm.md` §3 — **Phase 1 (A1/A3/A4) is built, tested, and green (468 passing).** The live cross-machine match plane exists. Here's the contract to build §5 against.

---

## 0. Status

Phase 1 acceptance — **1 local bot + 1 remote completes end-to-end** — passes at both the driver and the HTTP level (`tests/test_match_driver.py`). The event-driven decomposition landed as designed: `Orchestrator.run()` split into `_process_turn`, match state in Redis `lxm:match:{id}`, "await = the gap between two HTTP requests". Local `run_match.py` untouched.

**Not deployed yet** (JJ's push call). Commits are local on `main`; on deploy the Docker/render image now carries `lxm/`+`games/` and you must set `LXM_CORS_ORIGINS` to include the Ludex app origin. Base URL stays `https://lxm-api.onrender.com`.

## 1. Live contract (build BrokerSessionClient against this)

**Create** — `POST /api/matches`
```json
{ "game": "tictactoe",
  "match_id": "optional-else-server-generates",
  "participants": [
    {"id": "aria", "kind": "remote", "display": "Aria"},
    {"id": "kestrel", "kind": "remote", "display": "Kestrel"}
  ],
  "config": {"max_turns": 100, "timeout_seconds": 180} }
```
→ match view: `{match_id, game, status, to_move, to_move_kind, to_move_turn, participants, result, updated_at}`.
Auto-plays any leading LOCAL turns; returns halted at the first REMOTE turn (or `status:"complete"`). **Two remotes is the product shape** — the driver halts at whichever creature is next; no local needed.

**State** — `GET /api/matches/{id}/state` → same match view (poll this to learn when `to_move == you`).

**Turn payload** — `GET /api/matches/{id}/turns/{n}`
```json
{ "match_id", "turn", "to_move",
  "state_readable", "state",
  "present_agents": [{"id","display_name"}],
  "incoming_messages": [],
  "deadline": 180 }
```
409 if no remote turn pending or `n` ≠ current turn.

**Submit** — `POST /api/matches/{id}/turns/{n}/move`
```json
{ "move": { ...game move... }, "dialogue": "optional", "thoughts": "optional" }
```
→ updated match view. Errors carry a machine code in `detail.code`: `404 not_found` · `409 not_active|not_remote_turn|wrong_turn` · `400 illegal_move`. An illegal/out-of-turn move does **not** advance the match — resubmit.

**Reference flow:** `tests/test_match_driver.py::TestHTTPEndpoints::test_create_play_complete` is the exact create → GET turn → POST move → complete loop, runnable with a stub Redis (no server needed).

## 2. The poll loop (your client, Phase 1)

```
POST /matches  -> {to_move, to_move_turn, to_move_kind, status}
loop:
  GET /state
  if status == complete: break
  if to_move == ME and to_move_kind == remote:
      GET /turns/{to_move_turn}        # run creature locally on the payload
      POST /turns/{to_move_turn}/move  # {move, dialogue?}
  else: sleep + poll        # opponent's turn; (SSE replaces this poll in Phase 2)
```
This is the durable path. SSE (`your_turn`) in Phase 2 is a latency optimization on top — the poll remains the fallback we agreed on (Q1).

## 3. What's stubbed until Phase 2 (so you don't build against air)

The turn payload currently carries `present_agents` (opponent identity) + `state`/`state_readable`, but **`incoming_messages` and `opponent_actions` are empty** — the D-089 immune/humoral channels aren't fed yet. So you can build + test the **plumbing** (subscribe/poll, GET turn, POST move, advance) against the live contract now; the **organ-feeding** (A5 four-field payload incl. `opponent_actions`) lights up when Phase 2 lands. I'm starting Phase 2 next:
- **A2 SSE** `GET /api/matches/{id}/events` → `your_turn` (drops the §2 poll).
- **A5 full payload** — fill `incoming_messages` (immune) + `opponent_actions` (humoral immune) + freeze the 4-field D-089 mapping on the wire.

## 4. Integration point

When you have BrokerSessionClient plumbing against §1 and I have A5 fields populated, we wire + test a real 2-creature cross-machine match together. Ping me when your client can drive the §2 loop against a stub/local server; I'll have A5 by then.

## Net

1. **Phase 1 A1/A3/A4 done, 468 green.** Live contract in §1; reference flow in `test_match_driver.py`.
2. Build BrokerSessionClient against the §2 poll loop now — durable, SSE-optional.
3. `incoming_messages`/`opponent_actions` are empty stubs until Phase 2 (next on my side).
4. Not deployed — local commits; on deploy set `LXM_CORS_ORIGINS` for the Ludex origin.

— LxM Cody (2026-06-14, Phase 1 ready)
