"""Match orchestrator for LxM."""

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on Windows (prevents cp949 encoding crashes)
if os.name == "nt" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dataclasses import dataclass

from lxm.engine import LxMGame
from lxm.envelope import parse_from_file, parse_from_stdout, validate_envelope
from lxm.state import LxMState
from lxm.vitals import TurnVitals, MatchVitals


@dataclass
class _TurnOutcome:
    """Result of processing one turn.

    Either terminal (the match ended — `result` carries the final result
    dict) or non-terminal (the turn advanced — `game_state` carries the
    possibly-mutated game state for the next turn).
    """
    terminal: bool
    result: dict | None = None
    game_state: dict | None = None


class Orchestrator:
    """Manages a complete match from setup to evaluation."""

    # Consecutive quota errors before early abort
    QUOTA_ABORT_THRESHOLD = 3

    def __init__(self, game: LxMGame, match_config: dict, adapters: dict):
        self._game = game
        self._config = match_config
        self._adapters = adapters
        self._state = LxMState(match_config, game=game)
        self._match_dir: str | None = None
        self._max_retries = match_config.get("time_model", {}).get("max_retries", 2)
        self._timeout_action = match_config.get("time_model", {}).get("timeout_action", "no_op")
        # Error tracking
        self._error_counts: dict[str, dict[str, int]] = {}  # agent_id → {error_type: count}
        self._consecutive_quota_errors: int = 0
        # Cliff guard: end match if too many consecutive turns are invalid
        # (timeout or refusal). Threshold scales with no_op_limit; setting
        # to 0 disables the guard. Default tuned for 2-agent matches —
        # 3 rounds of mutual failure is enough signal that the match has
        # collapsed and isn't producing data.
        self._max_consecutive_invalid = match_config.get("time_model", {}).get(
            "max_consecutive_invalid", 6
        )
        self._consecutive_invalid: int = 0
        # Vital signs collector
        self._vitals = MatchVitals()
        # Agent memory (envelope-based, per-agent)
        self._agent_memory: dict[str, str] = {}  # agent_id → memory text
        self._max_turns = match_config.get("time_model", {}).get("max_turns", 100)
        invocation = match_config.get("invocation", {})
        self._invocation_mode = invocation.get("mode", "inline")
        self._discovery_turns = invocation.get("discovery_turns", 1)
        self._agent_turn_counts: dict[str, int] = {}  # Turns each agent has had

        # Shell system: per-agent hard_shell + soft_shell
        self._agent_shells: dict[str, dict] = {}  # agent_id -> {"hard": str, "soft": str}
        for agent_cfg in match_config.get("agents", []):
            aid = agent_cfg.get("agent_id")
            shells = {}
            hs = agent_cfg.get("hard_shell")
            if hs:
                try:
                    shells["hard"] = Path(hs).read_text(encoding="utf-8") if Path(hs).exists() else hs
                except (OSError, TypeError):
                    shells["hard"] = str(hs)
            ss = agent_cfg.get("soft_shell")
            if ss:
                shells["soft"] = str(ss)
            if shells:
                self._agent_shells[aid] = shells

        # Role-based shells (Avalon etc.): resolved at prompt time
        self._role_shells: dict[str, str] = {}
        for role, path in match_config.get("role_shells", {}).items():
            try:
                self._role_shells[role] = Path(path).read_text(encoding="utf-8")
            except (OSError, FileNotFoundError):
                pass

        # Role-based voice shells (M3-full E condition, §B.7 falsifier).
        # Voice shell is a *soft* shell — register/voice guidance, not
        # strategy prescription. Injected alongside per-agent soft shell
        # but under a distinct `[Voice Shell — role:<r>]` fence so
        # analysis can attribute register drift to the injection.
        self._role_voice_shells: dict[str, str] = {}
        for role, path in match_config.get("role_voice_shells", {}).items():
            try:
                self._role_voice_shells[role] = Path(path).read_text(encoding="utf-8")
            except (OSError, FileNotFoundError):
                pass

    def setup_match(self, base_dir: str = "matches") -> str:
        """Create the match folder and initialize all files."""
        match_id = self._config["match_id"]
        match_dir = Path(base_dir) / match_id
        match_dir.mkdir(parents=True, exist_ok=True)
        (match_dir / "moves").mkdir(exist_ok=True)
        (match_dir / "evals").mkdir(exist_ok=True)

        self._match_dir = str(match_dir.resolve())

        # Check if this is an existing match to resume
        state_file = match_dir / "state.json"
        result_file = match_dir / "result.json"
        is_resume = state_file.exists() and not result_file.exists()

        # Copy PROTOCOL.md (only if not resuming)
        if not is_resume:
            protocol_src = Path("PROTOCOL_v0.2.md")
            if protocol_src.exists():
                shutil.copy2(protocol_src, match_dir / "PROTOCOL.md")
            else:
                protocol_src = Path("PROTOCOL.md")
                if protocol_src.exists():
                    shutil.copy2(protocol_src, match_dir / "PROTOCOL.md")

        # Write rules.md (only if not resuming)
        if not is_resume:
            (match_dir / "rules.md").write_text(encoding="utf-8", data=self._game.get_rules())

        # Write match_config.json (always update)
        (match_dir / "match_config.json").write_text(encoding="utf-8", data=json.dumps(self._config, indent=2))

        # Initialize state only if this is a new match
        if not is_resume:
            game_state = self._game.initial_state(self._config["agents"])
            full_state = self._state.start(game_state)
            state_file.write_text(encoding="utf-8", data=json.dumps(full_state, indent=2))

            # Write empty log
            (match_dir / "log.json").write_text(encoding="utf-8", data="[]")
        else:
            # Load existing state for resume
            full_state = json.loads(state_file.read_text(encoding="utf-8"))
            # Restore the LxMState from the saved state
            self._state.load_from_state(full_state["lxm"])

        return self._match_dir

    def run(self) -> dict:
        """Run the complete match (local, in-process). Returns the final result.

        Thin driver: pick the active agent, build the prompt, invoke the local
        adapter, then hand the response to `_process_turn`. All per-turn
        processing lives in `_process_turn` so the hosted/event-driven path can
        reuse it for remote participants (emit turn -> await a network move ->
        `_process_turn`) in place of the in-process `adapter.invoke`.
        """
        assert self._match_dir, "Call setup_match() first"
        match_dir = Path(self._match_dir)

        # Load current game state from state.json
        full_state = json.loads((match_dir / "state.json").read_text(encoding="utf-8"))
        game_state = full_state["game"]

        while self._state.turn <= self._max_turns:
            agent_id = self._state.get_active_agent(game_state)
            adapter = self._adapters[agent_id]
            turn = self._state.turn

            # Build and invoke (the seam: for a remote participant the hosted
            # driver emits the turn and awaits a network move instead).
            prompt = self._build_turn_prompt(agent_id, turn, game_state)
            invoke_result = adapter.invoke(self._match_dir, prompt)

            outcome = self._process_turn(game_state, agent_id, turn, invoke_result, match_dir)
            if outcome.terminal:
                return outcome.result
            game_state = outcome.game_state

        # Max turns reached
        return self._finalize_max_turns(game_state, match_dir)

    def _process_turn(self, game_state: dict, agent_id: str, turn: int,
                      invoke_result: dict, match_dir: Path) -> _TurnOutcome:
        """Process one participant's response for `turn` and advance the match.

        Covers error classification + vitals + quota abort, move collection
        (+ refusal short-circuit), validation/retry, timeout handling, move
        application, logging, game-over detection, and the turn advance.

        Returns a `_TurnOutcome`: terminal (match ended — carries `result`) or
        non-terminal (carries the possibly-mutated `game_state` for the next
        turn). Reused by both the local `run()` loop and the hosted move
        handler; `invoke_result` is the adapter result locally, or a
        synthesized result wrapping a remote participant's submitted move.
        """
        # Classify and log errors
        error_type = self._classify_error(invoke_result)

        # Record vital signs
        self._vitals.record(TurnVitals(
            turn=turn,
            agent_id=agent_id,
            latency_ms=invoke_result.get("latency_ms", 0),
            error_type=error_type,
            retry_count=invoke_result.get("retry_count", 0),
            tokens_in=invoke_result.get("tokens_in"),
            tokens_out=invoke_result.get("tokens_out"),
        ))
        if error_type:
            self._record_error(agent_id, error_type, invoke_result, turn, match_dir)
            if error_type == "quota" and self._check_quota_abort():
                return _TurnOutcome(terminal=True, result=self._abort_quota(agent_id, game_state, match_dir))

        # Handle timeout
        if invoke_result.get("timed_out"):
            envelope = None
        else:
            envelope = self.collect_move(self._match_dir, agent_id, turn, invoke_result, game_state)
            # Refusal short-circuit (joint spec §G.3 P5 corollary c):
            # AI interpreter explicitly refused to fabricate a move.
            # Skip retry loop, record refusal, treat as no-op.
            if (
                envelope is not None
                and envelope.get("meta", {}).get("parse_path") == "refusal"
            ):
                self._append_log(match_dir, {
                    "turn": turn, "agent_id": agent_id, "envelope": envelope,
                    "validation": {
                        "envelope_valid": False, "payload_valid": False,
                        "engine_message": "refusal",
                    },
                    "result": "refusal", "attempt": 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                print(f"[Turn {turn}] {agent_id} refusal "
                      f"(confidence={envelope.get('meta', {}).get('interpreter_confidence', 0)})")
                self._state.record_move(agent_id, {"type": "pass"}, f"{agent_id} refused interpretation")
                cliff = self._bump_and_check_cliff(match_dir, turn, "refusal")
                if cliff:
                    return _TurnOutcome(terminal=True, result=cliff)
                full_state = self._state.advance_turn(game_state)
                next_agent_id = self._state.get_active_agent(game_state)
                write_state = self._filter_state(full_state, next_agent_id)
                (match_dir / "state.json").write_text(encoding="utf-8", data=json.dumps(write_state, indent=2))
                return _TurnOutcome(terminal=False, game_state=game_state)

        # Retry loop
        attempt = 1
        max_attempts = 1 + self._max_retries
        valid_envelope = None

        while attempt <= max_attempts:
            if envelope is None:
                reason = "No valid envelope found in output"
            else:
                # Validate envelope fields
                env_result = validate_envelope(envelope, self._config, agent_id, turn)
                if not env_result["valid"]:
                    reason = env_result["message"]
                    self._append_log(match_dir, {
                        "turn": turn, "agent_id": agent_id, "envelope": envelope,
                        "validation": {"envelope_valid": False, "payload_valid": False, "engine_message": reason},
                        "result": "rejected", "attempt": attempt,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    # Validate game payload
                    payload_result = self._game.validate_move(
                        envelope["move"], agent_id, self._state.to_dict(game_state)
                    )
                    if not payload_result["valid"]:
                        reason = payload_result["message"]
                        self._append_log(match_dir, {
                            "turn": turn, "agent_id": agent_id, "envelope": envelope,
                            "validation": {"envelope_valid": True, "payload_valid": False, "engine_message": reason},
                            "result": "rejected", "attempt": attempt,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    else:
                        valid_envelope = envelope
                        break

            # Need retry
            attempt += 1
            if attempt <= max_attempts:
                retry_result = self._retry(agent_id, turn, reason, attempt, max_attempts)
                envelope = self.collect_move(self._match_dir, agent_id, turn, retry_result, game_state) if retry_result else None

        if valid_envelope is None:
            # All attempts exhausted — apply timeout action
            timeout_result = self.handle_timeout(agent_id, self._state.to_dict(game_state))
            if timeout_result.get("forfeit"):
                # Game over by forfeit
                other_agents = [a for a in self._config["agents"] if a["agent_id"] != agent_id]
                winner = other_agents[0]["agent_id"] if other_agents else None
                marks = game_state["current"].get("marks", {})
                scores = {aid: (1 if aid == winner else 0) for aid in marks}
                result = {
                    "outcome": "forfeit",
                    "winner": winner,
                    "scores": scores,
                    "summary": f"{agent_id} forfeited (exhausted retries)",
                }
                (match_dir / "result.json").write_text(encoding="utf-8", data=json.dumps(result, indent=2))
                self._state.set_phase("END")
                print(f"[Result] {result['summary']}")
                return _TurnOutcome(terminal=True, result=result)
            # no_op: skip turn (auto-fold for poker)
            timeout_move = self._get_timeout_move(agent_id, game_state)
            if timeout_move:
                # Apply auto-move (e.g. auto-fold in poker)
                current_full_state = self._state.to_dict(game_state)
                summary = self._game.summarize_move(timeout_move, agent_id, current_full_state)
                game_state = self._game.apply_move(timeout_move, agent_id, current_full_state)
                self._state.record_move(agent_id, timeout_move, f"{summary} (timeout)")
                self._append_log(match_dir, {
                    "turn": turn, "agent_id": agent_id, "envelope": None,
                    "validation": {"envelope_valid": False, "payload_valid": False, "engine_message": "timeout auto-move"},
                    "result": "timeout", "attempt": attempt - 1,
                    "post_move_state": game_state.get("current"),
                    "post_move_context": game_state.get("context"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                print(f"[Turn {turn}] {agent_id}: {summary} (timeout)")
            else:
                self._append_log(match_dir, {
                    "turn": turn, "agent_id": agent_id, "envelope": None,
                    "validation": {"envelope_valid": False, "payload_valid": False, "engine_message": "timeout"},
                    "result": "timeout", "attempt": attempt - 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                summary = f"{agent_id} timed out (no_op)"
                self._state.record_move(agent_id, {"type": "pass"}, summary)
                print(f"[Turn {turn}] {summary}")
            cliff = self._bump_and_check_cliff(match_dir, turn, "timeout")
            if cliff:
                return _TurnOutcome(terminal=True, result=cliff)
        else:
            # Apply valid move — resets cliff counter.
            self._consecutive_invalid = 0
            move = valid_envelope["move"]
            current_full_state = self._state.to_dict(game_state)
            summary = self._game.summarize_move(move, agent_id, current_full_state)
            game_state = self._game.apply_move(move, agent_id, current_full_state)

            self._state.record_move(agent_id, move, summary)

            # Save agent memory from envelope (if provided)
            self._save_agent_memory(agent_id, valid_envelope, match_dir)

            self._append_log(match_dir, {
                "turn": turn, "agent_id": agent_id, "envelope": valid_envelope,
                "validation": {"envelope_valid": True, "payload_valid": True, "engine_message": None},
                "result": "accepted", "attempt": attempt,
                "post_move_state": game_state.get("current"),
                "post_move_context": game_state.get("context"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            print(f"[Turn {turn}] {agent_id}: {summary}")

        # Update state.json
        full_state = self._state.to_dict(game_state)
        (match_dir / "state.json").write_text(encoding="utf-8", data=json.dumps(full_state, indent=2))

        # Check game over
        if self._game.is_over(full_state):
            result = self._game.get_result(full_state)
            result["vitals"] = self._vitals.to_dict()
            (match_dir / "result.json").write_text(encoding="utf-8", data=json.dumps(result, indent=2))
            self._state.set_phase("END")
            print(f"[Result] {result['summary']}")
            self._notify_adapters_match_end(result, match_dir)
            # Run evaluation
            self.run_evaluation(self._match_dir)
            return _TurnOutcome(terminal=True, result=result)

        # Advance turn
        full_state = self._state.advance_turn(game_state)
        # Filter state for next agent if the game supports it
        next_agent_id = self._state.get_active_agent(game_state)
        write_state = self._filter_state(full_state, next_agent_id)
        (match_dir / "state.json").write_text(encoding="utf-8", data=json.dumps(write_state, indent=2))
        return _TurnOutcome(terminal=False, game_state=game_state)

    def _finalize_max_turns(self, game_state: dict, match_dir: Path) -> dict:
        """Finalize a match that reached max_turns without a terminal state."""
        result = self._game.get_result(self._state.to_dict(game_state))
        result["vitals"] = self._vitals.to_dict()
        (match_dir / "result.json").write_text(encoding="utf-8", data=json.dumps(result, indent=2))
        self._state.set_phase("END")
        print(f"[Result] {result['summary']}")
        self._notify_adapters_match_end(result, match_dir)
        return result

    def _notify_adapters_match_end(self, result: dict, match_dir: Path) -> None:
        """Call `on_match_end` on each adapter. Errors are logged but not raised.

        Stateful adapters (e.g. LudexCreatureAdapter) use this to commit a
        distilled summary to the creature's long-term memory. Stateless
        adapters inherit the base no-op.
        """
        match_id = self._config.get("match_id", "")
        for aid, adapter in self._adapters.items():
            try:
                adapter.on_match_end(result, match_id, str(match_dir))
            except Exception as e:
                print(f"[on_match_end] {aid} adapter raised: {e}")

    def collect_move(self, match_dir: str, agent_id: str, turn: int, invoke_result: dict,
                     game_state: dict | None = None) -> dict | None:
        """Collect move from file first, then stdout, then NL interpretation.

        Fallback order (spec v0.1 §A.2 + r6 interpreter extension):
        1. Written move file (file-mode agents).
        2. Parsed JSON envelope from stdout (standard path).
        3. Per-game rule-based interpreter on raw stdout (this round).
        4. AI-based CLI interpreter (planned — §G.3 pending thread).

        `game_state` is forwarded to phase-aware interpreters (e.g. Avalon
        needs to know whether the active turn is propose/vote/quest).

        Each step carries a `meta.parse_path` tag (`file` | `json` | `rule`
        | `ai`) so downstream analysis can see which creatures relied on
        which path — this becomes a direct observation channel for the
        B.1 voice-vs-task-shell hypothesis.
        """
        move_file = Path(match_dir) / "moves" / f"turn_{turn}_{agent_id}.json"
        envelope = parse_from_file(
            str(move_file),
            protocol=self._config.get("protocol_version", "lxm-v0.2"),
            match_id=self._config.get("match_id", ""),
            agent_id=agent_id,
            turn=turn,
        )
        if envelope is not None:
            move_file.unlink(missing_ok=True)
            envelope.setdefault("meta", {}).setdefault("parse_path", "file")
            return self._fill_envelope(envelope, agent_id, turn)

        # Try stdout
        stdout = invoke_result.get("stdout", "")
        # Handle Claude Code --output-format json
        if stdout.strip().startswith("{"):
            try:
                cc_output = json.loads(stdout)
                if "result" in cc_output:
                    stdout = cc_output["result"]
            except json.JSONDecodeError:
                pass
        envelope = parse_from_stdout(stdout)
        if envelope is not None:
            envelope.setdefault("meta", {}).setdefault("parse_path", "json")
            return self._fill_envelope(envelope, agent_id, turn)

        # Rule-based interpreter fallback.
        interpreted = self._interpret_response(stdout, agent_id, game_state)
        if interpreted is not None:
            return self._fill_envelope(interpreted, agent_id, turn)
        return None

    def _interpret_response(self, response: str, agent_id: str,
                            game_state: dict | None = None) -> dict | None:
        """Attempt to extract a move from free-form response.

        Chain (per joint spec §A.2): rule-based interpreter first, then
        AI CLI interpreter on rule-ambiguity. Returns a partially-filled
        envelope dict, or a sentinel envelope with `meta.parse_path =
        "refusal"` when the AI explicitly refuses (orchestrator surfaces
        this via `engine_message="refusal"` per §G.3 P5).
        """
        if not response or not response.strip():
            return None
        try:
            from lxm.interpreters import get_interpreter, get_ai_interpreter
        except Exception:
            return None
        game_name = self._config.get("game", {}).get("name", "")

        # Rule first.
        interpreter = get_interpreter(game_name)
        if interpreter is not None:
            try:
                result = interpreter.interpret(response, {"agent_id": agent_id, "game_state": game_state})
            except Exception as e:
                print(f"[interpreter rule:{game_name}] raised: {e}")
                result = None
            if result is not None and result.path != "refusal":
                return self._envelope_from_interpretation(response, agent_id, result)

        # Rule failed or returned None → AI fallback (if registered).
        ai = get_ai_interpreter(game_name)
        if ai is not None:
            try:
                result = ai.interpret(response, {"agent_id": agent_id, "game_state": game_state})
            except Exception as e:
                print(f"[interpreter ai:{game_name}] raised: {e}")
                result = None
            if result is not None:
                return self._envelope_from_interpretation(response, agent_id, result)
        return None

    def _envelope_from_interpretation(self, response: str, agent_id: str, result) -> dict:
        """Wrap an `Interpretation` (rule or AI) into a partial envelope.

        Refusal is encoded by `move == {}` and `meta.parse_path == "refusal"` —
        the orchestrator's caller checks for this and records the turn as
        a refusal rather than a synthesized move (§G.3 P5 corollary c).
        """
        return {
            "protocol": self._config.get("protocol_version", "lxm-v0.2"),
            "match_id": self._config.get("match_id", ""),
            "agent_id": agent_id,
            "turn": 0,  # _fill_envelope overrides
            "move": result.move,
            "meta": {
                "parse_path": result.path,
                "interpreter_confidence": result.confidence,
                "interpreter_evidence": result.evidence,
                "reasoning": response[:800],
            },
        }

    def _fill_envelope(self, envelope: dict, agent_id: str, turn: int) -> dict:
        """Auto-fill missing/wrong envelope metadata fields.

        The orchestrator knows match_id, agent_id, and turn — if the agent
        got the move payload right but missed metadata, fix it silently.
        """
        envelope.setdefault("protocol", self._config.get("protocol_version", "lxm-v0.2"))
        envelope.setdefault("match_id", self._config.get("match_id", ""))
        envelope.setdefault("agent_id", agent_id)
        envelope.setdefault("turn", turn)

        # Fix empty/wrong values (common with inline prompts)
        if not envelope["match_id"]:
            envelope["match_id"] = self._config.get("match_id", "")
        if not envelope["agent_id"]:
            envelope["agent_id"] = agent_id
        if envelope["turn"] != turn:
            envelope["turn"] = turn
        return envelope

    def _get_timeout_move(self, agent_id: str, game_state: dict) -> dict | None:
        """Return an auto-move for timeout, or None for no_op.

        Poker: auto-fold. Other games: None (no_op).
        """
        if hasattr(self._game, 'get_timeout_move'):
            return self._game.get_timeout_move(agent_id, game_state)
        return None

    def handle_timeout(self, agent_id: str, state: dict) -> dict:
        """Apply timeout_action from match_config."""
        if self._timeout_action == "forfeit":
            return {"forfeit": True}
        # no_op or random (treated as no_op for v0.1)
        return {"forfeit": False}

    def run_evaluation(self, match_dir: str) -> None:
        """Invoke each agent for post-game evaluation (best-effort)."""
        for agent_config in self._config["agents"]:
            agent_id = agent_config["agent_id"]
            adapter = self._adapters.get(agent_id)
            if adapter is None:
                continue

            prompt = self._build_eval_prompt(agent_id)
            try:
                adapter.invoke(match_dir, prompt)
            except Exception as e:
                print(f"[Eval] {agent_id} evaluation failed: {e}")

    def _build_turn_prompt(self, agent_id: str, turn: int, game_state: dict = None) -> str:
        match_id = self._config["match_id"]
        agent_turns = self._agent_turn_counts.get(agent_id, 0)
        self._agent_turn_counts[agent_id] = agent_turns + 1

        # Discovery phase: file-mode "Read PROTOCOL.md..." prompts. Skip
        # under inline mode — discovery's file-based prompt has no game
        # markers, so rule_bot._detect_game returns "unknown" and ludex
        # creatures emit cross-game actions (no state.json visible yet).
        if self._invocation_mode != "inline" and agent_turns < self._discovery_turns:
            if agent_turns == 0:
                # Very first turn: full exploration prompt (read rules + protocol)
                return (
                    f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}\n"
                    f"It is your turn.\n"
                    f"1. Read PROTOCOL.md for universal rules.\n"
                    f"2. Read rules.md for game-specific rules.\n"
                    f"3. Read state.json for current situation.\n"
                    f"4. Submit your move by writing to: moves/turn_{turn}_{agent_id}.json"
                )
            else:
                # Subsequent discovery turns: file-based but no protocol read
                return (
                    f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}\n"
                    f"It is your turn.\n"
                    f"1. Read state.json for current situation.\n"
                    f"2. Submit your move by writing to: moves/turn_{turn}_{agent_id}.json"
                )

        # Past discovery phase: use inline mode if configured and game supports it
        if self._invocation_mode == "inline" and game_state is not None:
            full_state = self._state.to_dict(game_state)
            # Apply per-agent filtering before building prompt
            if hasattr(self._game, 'filter_state_for_agent'):
                full_state = self._game.filter_state_for_agent(full_state, agent_id)
            inline = self._game.build_inline_prompt(agent_id, full_state, turn)
            if inline is not None:
                return self._prepend_shells(agent_id, inline, full_state)

        # Fallback: standard file-based prompt
        prompt = (
            f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}\n"
            f"It is your turn.\n"
            f"1. Read state.json for current situation.\n"
            f"2. Submit your move by writing to: moves/turn_{turn}_{agent_id}.json"
        )
        return self._prepend_shells(agent_id, prompt)

    # Hard limit for agent memory files (platform stability)
    MEMORY_MAX_CHARS = 2000

    def _prepend_shells(self, agent_id: str, prompt: str, full_state: dict = None) -> str:
        """Prepend [STRATEGY], [COACHING], and [MEMORY] to prompt.

        Shell resolution order for hard shell:
        1. Per-agent hard_shell from match_config agents
        2. Role-based shell from role_shells (Avalon etc.)

        Memory: reads match_dir/memory_{agent_id}.md if it exists (agent-managed).
        """
        prefix = ""

        # Hard shell: per-agent first, then role-based fallback
        agent_shells = self._agent_shells.get(agent_id, {})
        hard = agent_shells.get("hard")

        if not hard and self._role_shells and full_state:
            agent_role = (
                full_state.get("game", {})
                .get("current", {})
                .get("players", {})
                .get(agent_id, {})
                .get("role")
            )
            hard = self._role_shells.get(agent_role)

        if hard:
            prefix += f"[STRATEGY]\n{hard.strip()}\n[/STRATEGY]\n\n"

        # Soft shell: per-agent only
        soft = agent_shells.get("soft")
        if soft:
            prefix += f"[COACHING]\n{soft.strip()}\n[/COACHING]\n\n"

        # Role-based voice shell (M3-full E condition, joint spec §B.7
        # falsifier). Distinct fence so register-drift analysis can
        # attribute changes to this injection. Composes on top of any
        # per-agent soft shell.
        if self._role_voice_shells and full_state:
            agent_role = (
                full_state.get("game", {})
                .get("current", {})
                .get("players", {})
                .get(agent_id, {})
                .get("role")
            )
            voice = self._role_voice_shells.get(agent_role)
            if voice:
                prefix += f"[Voice Shell — role:{agent_role}]\n{voice.strip()}\n[/Voice Shell]\n\n"

        # Agent memory: from envelope or file
        memory = self._read_agent_memory(agent_id)
        if memory:
            prefix += f"[YOUR MEMORY]\n{memory}\n[/YOUR MEMORY]\n\n"

        return prefix + prompt if prefix else prompt

    def _read_agent_memory(self, agent_id: str) -> str | None:
        """Read agent's memory. Checks in-memory store first, then file fallback."""
        # Primary: envelope-based memory (stored in-memory by orchestrator)
        memory = self._agent_memory.get(agent_id)
        if memory:
            if len(memory) > self.MEMORY_MAX_CHARS:
                memory = memory[:self.MEMORY_MAX_CHARS] + "\n[...truncated]"
            return memory

        # Fallback: file-based memory (for file-mode agents)
        if not self._match_dir:
            return None
        memory_path = Path(self._match_dir) / f"memory_{agent_id}.md"
        if not memory_path.exists():
            return None
        try:
            content = memory_path.read_text(encoding="utf-8").strip()
            if not content:
                return None
            if len(content) > self.MEMORY_MAX_CHARS:
                content = content[:self.MEMORY_MAX_CHARS] + "\n[...truncated]"
            return content
        except OSError:
            return None

    def _save_agent_memory(self, agent_id: str, envelope: dict, match_dir: Path):
        """Save agent's memory from envelope `memory` field.

        Orchestrator acts as a "mailbox" — stores and delivers, does not read or interpret.
        """
        memory = envelope.get("memory")
        if not memory or not isinstance(memory, str):
            return
        memory = memory.strip()
        if not memory:
            return

        # Enforce hard limit
        if len(memory) > self.MEMORY_MAX_CHARS:
            memory = memory[:self.MEMORY_MAX_CHARS]

        # Store in-memory for next turn's prompt injection
        self._agent_memory[agent_id] = memory

        # Also persist to file for post-match analysis
        memory_path = match_dir / f"memory_{agent_id}.md"
        memory_path.write_text(memory, encoding="utf-8")

    def _build_retry_prompt(self, agent_id: str, turn: int, reason: str, attempt: int, max_attempts: int) -> str:
        match_id = self._config["match_id"]
        return (
            f"[LxM RETRY] Match: {match_id} | Agent: {agent_id} | Turn: {turn}\n"
            f"Attempt: {attempt} of {max_attempts}\n"
            f"Reason: {reason}\n"
            f"Submit a corrected move to: moves/turn_{turn}_{agent_id}.json"
        )

    def _build_eval_prompt(self, agent_id: str) -> str:
        match_id = self._config["match_id"]
        other_agents = [a["agent_id"] for a in self._config["agents"] if a["agent_id"] != agent_id]
        cross_lines = "\n".join(
            f"4. Write cross-evaluation for {target} to: evals/cross_{agent_id}_on_{target}.json"
            for target in other_agents
        )
        return (
            f"[LxM EVAL] Match: {match_id} | Agent: {agent_id}\n"
            f"The match is over. Perform your evaluation.\n"
            f"1. Read rules.md Section \"Evaluation\" for evaluation criteria.\n"
            f"2. Read log.json for complete match history.\n"
            f"3. Write self-evaluation to: evals/self_{agent_id}.json\n"
            f"{cross_lines}"
        )

    def _retry(self, agent_id: str, turn: int, reason: str, attempt: int, max_attempts: int) -> dict | None:
        adapter = self._adapters.get(agent_id)
        if adapter is None:
            return None
        prompt = self._build_retry_prompt(agent_id, turn, reason, attempt, max_attempts)
        return adapter.invoke(self._match_dir, prompt)

    def _filter_state(self, state: dict, agent_id: str) -> dict:
        """Apply per-agent state filtering if the game engine supports it."""
        if hasattr(self._game, 'filter_state_for_agent'):
            return self._game.filter_state_for_agent(state, agent_id)
        return state

    @staticmethod
    def _append_log(match_dir: Path, entry: dict) -> None:
        log_path = match_dir / "log.json"
        log = json.loads(log_path.read_text(encoding="utf-8"))
        log.append(entry)
        log_path.write_text(encoding="utf-8", data=json.dumps(log, indent=2))

    # ── Error Classification & Logging ──

    def _classify_error(self, invoke_result: dict) -> str | None:
        """Classify invoke error type. Returns None if no error."""
        if invoke_result.get("timed_out"):
            return "timeout"

        stderr = invoke_result.get("stderr", "")
        exit_code = invoke_result.get("exit_code", 0)

        if exit_code == 0:
            return None

        stderr_lower = stderr.lower()

        # Quota / rate limit (429)
        if "429" in stderr or "rate limit" in stderr_lower or "quota" in stderr_lower or "resource exhausted" in stderr_lower:
            return "quota"

        # Model not found (404)
        if "404" in stderr or "not found" in stderr_lower or "model not found" in stderr_lower:
            return "model_error"

        # Authentication
        if "401" in stderr or "403" in stderr or "unauthorized" in stderr_lower or "forbidden" in stderr_lower:
            return "auth_error"

        # Connection
        if "connection" in stderr_lower or "network" in stderr_lower or "econnrefused" in stderr_lower:
            return "connection_error"

        # Generic CLI error
        if exit_code != 0:
            return "cli_error"

        return None

    def _record_error(self, agent_id: str, error_type: str,
                      invoke_result: dict, turn: int, match_dir: Path):
        """Record error in tracking dict and append to error log."""
        # Track counts
        if agent_id not in self._error_counts:
            self._error_counts[agent_id] = {}
        counts = self._error_counts[agent_id]
        counts[error_type] = counts.get(error_type, 0) + 1

        # Track consecutive quota errors
        if error_type == "quota":
            self._consecutive_quota_errors += 1
        else:
            self._consecutive_quota_errors = 0

        # Log to stderr
        stderr_preview = (invoke_result.get("stderr", "") or "")[:200]
        print(f"[Error] Turn {turn} {agent_id}: {error_type} (exit {invoke_result.get('exit_code')})"
              f"{' — ' + stderr_preview if stderr_preview else ''}")

        # Append to error log file
        error_log_path = match_dir / "errors.json"
        errors = []
        if error_log_path.exists():
            try:
                errors = json.loads(error_log_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        errors.append({
            "turn": turn,
            "agent_id": agent_id,
            "error_type": error_type,
            "exit_code": invoke_result.get("exit_code"),
            "stderr": (invoke_result.get("stderr", "") or "")[:500],
            "timed_out": invoke_result.get("timed_out", False),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        error_log_path.write_text(encoding="utf-8", data=json.dumps(errors, indent=2))

    def _check_quota_abort(self) -> bool:
        """Return True if consecutive quota errors exceed threshold."""
        return self._consecutive_quota_errors >= self.QUOTA_ABORT_THRESHOLD

    def _bump_and_check_cliff(self, match_dir: Path, turn: int, kind: str) -> dict | None:
        """Increment consecutive-invalid counter; abort match if threshold reached.

        Returns a result dict if the match should terminate, or None to continue.
        Threshold is `time_model.max_consecutive_invalid` (default 6, 0 disables).
        """
        self._consecutive_invalid += 1
        if self._max_consecutive_invalid <= 0:
            return None
        if self._consecutive_invalid < self._max_consecutive_invalid:
            return None
        scores = {a["agent_id"]: 0 for a in self._config.get("agents", [])}
        result = {
            "outcome": "cliff_timeout",
            "winner": None,
            "scores": scores,
            "summary": (
                f"Match aborted: {self._consecutive_invalid} consecutive invalid turns "
                f"(latest: {kind} on turn {turn})"
            ),
            "error_counts": self._error_counts,
            "vitals": self._vitals.to_dict(),
        }
        (match_dir / "result.json").write_text(encoding="utf-8", data=json.dumps(result, indent=2))
        self._state.set_phase("END")
        print(f"[ABORT] cliff_timeout — {result['summary']}")
        return result

    def _abort_quota(self, agent_id: str, game_state: dict, match_dir: Path) -> dict:
        """Abort match due to quota exhaustion."""
        print(f"[ABORT] {self.QUOTA_ABORT_THRESHOLD} consecutive quota errors. Stopping match.")
        result = {
            "outcome": "aborted",
            "winner": None,
            "scores": {},
            "summary": f"Match aborted: {agent_id} quota exhausted ({self.QUOTA_ABORT_THRESHOLD} consecutive 429 errors)",
            "error_counts": self._error_counts,
            "vitals": self._vitals.to_dict(),
        }
        (match_dir / "result.json").write_text(encoding="utf-8", data=json.dumps(result, indent=2))
        self._state.set_phase("END")
        return result

    def get_error_summary(self) -> dict:
        """Return error counts for all agents."""
        return dict(self._error_counts)
