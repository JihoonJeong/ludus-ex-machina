"""Match orchestrator for LxM."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from lxm.engine import LxMGame
from lxm.envelope import parse_from_file, parse_from_stdout, validate_envelope
from lxm.state import LxMState


class Orchestrator:
    """Manages a complete match from setup to evaluation."""

    def __init__(self, game: LxMGame, match_config: dict, adapters: dict):
        self._game = game
        self._config = match_config
        self._adapters = adapters
        self._state = LxMState(match_config)
        self._match_dir: str | None = None
        self._max_retries = match_config.get("time_model", {}).get("max_retries", 2)
        self._timeout_action = match_config.get("time_model", {}).get("timeout_action", "no_op")
        self._max_turns = match_config.get("time_model", {}).get("max_turns", 100)

    def setup_match(self, base_dir: str = "matches") -> str:
        """Create the match folder and initialize all files."""
        match_id = self._config["match_id"]
        match_dir = Path(base_dir) / match_id
        match_dir.mkdir(parents=True, exist_ok=True)
        (match_dir / "moves").mkdir(exist_ok=True)
        (match_dir / "evals").mkdir(exist_ok=True)

        self._match_dir = str(match_dir.resolve())

        # Copy PROTOCOL.md
        protocol_src = Path("PROTOCOL_v0.2.md")
        if protocol_src.exists():
            shutil.copy2(protocol_src, match_dir / "PROTOCOL.md")
        else:
            protocol_src = Path("PROTOCOL.md")
            if protocol_src.exists():
                shutil.copy2(protocol_src, match_dir / "PROTOCOL.md")

        # Write rules.md
        (match_dir / "rules.md").write_text(self._game.get_rules())

        # Write match_config.json
        (match_dir / "match_config.json").write_text(json.dumps(self._config, indent=2))

        # Generate initial state
        game_state = self._game.initial_state(self._config["agents"])
        full_state = self._state.start(game_state)
        (match_dir / "state.json").write_text(json.dumps(full_state, indent=2))

        # Write empty log
        (match_dir / "log.json").write_text("[]")

        return self._match_dir

    def run(self) -> dict:
        """Run the complete match. Returns the final result."""
        assert self._match_dir, "Call setup_match() first"
        match_dir = Path(self._match_dir)

        # Load current game state from state.json
        full_state = json.loads((match_dir / "state.json").read_text())
        game_state = full_state["game"]

        while self._state.turn <= self._max_turns:
            agent_id = self._state.get_active_agent()
            adapter = self._adapters[agent_id]
            turn = self._state.turn

            # Build and invoke
            prompt = self._build_turn_prompt(agent_id, turn)
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
                    (match_dir / "result.json").write_text(json.dumps(result, indent=2))
                    self._state.set_phase("END")
                    print(f"[Result] {result['summary']}")
                    return result
                # no_op: skip turn
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
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                print(f"[Turn {turn}] {agent_id}: {summary}")

            # Update state.json
            full_state = self._state.to_dict(game_state)
            (match_dir / "state.json").write_text(json.dumps(full_state, indent=2))

            # Check game over
            if self._game.is_over(full_state):
                result = self._game.get_result(full_state)
                (match_dir / "result.json").write_text(json.dumps(result, indent=2))
                self._state.set_phase("END")
                print(f"[Result] {result['summary']}")
                # Run evaluation
                self.run_evaluation(self._match_dir)
                return result

            # Advance turn
            full_state = self._state.advance_turn(game_state)
            (match_dir / "state.json").write_text(json.dumps(full_state, indent=2))

        # Max turns reached
        result = self._game.get_result(self._state.to_dict(game_state))
        (match_dir / "result.json").write_text(json.dumps(result, indent=2))
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
            return envelope

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
        return parse_from_stdout(stdout)

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

    def _build_turn_prompt(self, agent_id: str, turn: int) -> str:
        match_id = self._config["match_id"]
        return (
            f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}\n"
            f"It is your turn.\n"
            f"1. Read PROTOCOL.md for universal rules.\n"
            f"2. Read rules.md for game-specific rules.\n"
            f"3. Read state.json for current situation.\n"
            f"4. Submit your move by writing to: moves/turn_{turn}_{agent_id}.json"
        )

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

    @staticmethod
    def _append_log(match_dir: Path, entry: dict) -> None:
        log_path = match_dir / "log.json"
        log = json.loads(log_path.read_text())
        log.append(entry)
        log_path.write_text(json.dumps(log, indent=2))
