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

from lxm.engine import LxMGame
from lxm.envelope import parse_from_file, parse_from_stdout, validate_envelope
from lxm.state import LxMState


class Orchestrator:
    """Manages a complete match from setup to evaluation."""

    def __init__(self, game: LxMGame, match_config: dict, adapters: dict):
        self._game = game
        self._config = match_config
        self._adapters = adapters
        self._state = LxMState(match_config, game=game)
        self._match_dir: str | None = None
        self._max_retries = match_config.get("time_model", {}).get("max_retries", 2)
        self._timeout_action = match_config.get("time_model", {}).get("timeout_action", "no_op")
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
        """Run the complete match. Returns the final result."""
        assert self._match_dir, "Call setup_match() first"
        match_dir = Path(self._match_dir)

        # Load current game state from state.json
        full_state = json.loads((match_dir / "state.json").read_text(encoding="utf-8"))
        game_state = full_state["game"]

        while self._state.turn <= self._max_turns:
            agent_id = self._state.get_active_agent(game_state)
            adapter = self._adapters[agent_id]
            turn = self._state.turn

            # Build and invoke
            prompt = self._build_turn_prompt(agent_id, turn, game_state)
            invoke_result = adapter.invoke(self._match_dir, prompt)

            # Handle timeout
            if invoke_result.get("timed_out"):
                envelope = None
            else:
                envelope = self.collect_move(self._match_dir, agent_id, turn, invoke_result)

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
                    envelope = self.collect_move(self._match_dir, agent_id, turn, retry_result) if retry_result else None

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
                    return result
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
            else:
                # Apply valid move
                move = valid_envelope["move"]
                current_full_state = self._state.to_dict(game_state)
                summary = self._game.summarize_move(move, agent_id, current_full_state)
                game_state = self._game.apply_move(move, agent_id, current_full_state)

                self._state.record_move(agent_id, move, summary)
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
                (match_dir / "result.json").write_text(encoding="utf-8", data=json.dumps(result, indent=2))
                self._state.set_phase("END")
                print(f"[Result] {result['summary']}")
                # Run evaluation
                self.run_evaluation(self._match_dir)
                return result

            # Advance turn
            full_state = self._state.advance_turn(game_state)
            # Filter state for next agent if the game supports it
            next_agent_id = self._state.get_active_agent(game_state)
            write_state = self._filter_state(full_state, next_agent_id)
            (match_dir / "state.json").write_text(encoding="utf-8", data=json.dumps(write_state, indent=2))

        # Max turns reached
        result = self._game.get_result(self._state.to_dict(game_state))
        (match_dir / "result.json").write_text(encoding="utf-8", data=json.dumps(result, indent=2))
        self._state.set_phase("END")
        print(f"[Result] {result['summary']}")
        return result

    def collect_move(self, match_dir: str, agent_id: str, turn: int, invoke_result: dict) -> dict | None:
        """Collect move from file first, then stdout."""
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
            return self._fill_envelope(envelope, agent_id, turn)
        return None

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

        # Discovery phase: use file mode for initial turns per agent
        if agent_turns < self._discovery_turns:
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

    def _prepend_shells(self, agent_id: str, prompt: str, full_state: dict = None) -> str:
        """Prepend [STRATEGY] (hard shell) and [COACHING] (soft shell) to prompt.

        Shell resolution order for hard shell:
        1. Per-agent hard_shell from match_config agents
        2. Role-based shell from role_shells (Avalon etc.)
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

        return prefix + prompt if prefix else prompt

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
