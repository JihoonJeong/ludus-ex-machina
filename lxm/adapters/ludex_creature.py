"""Ludex creature adapter for LxM.

Wraps a Ludex creature (an Organism assembled from `ludex.json`/`ludex.yaml`)
so it can participate in an LxM match as just another agent. The creature's
engine receives the LxM prompt (task-shell + match context), the creature's
memory organ records the experience, and the creature's own Resilience
block handles retries — LxM-side retries are disabled to avoid stacking.

Design decisions (see docs/ludex-bridge-lxm-perspective.md + round 2):
- **Stateless adapter, persistent creature.** The adapter is created once
  per match (same as other adapters), but the wrapped Organism has a
  habitat — memory carries across matches when pointed at the same
  creature directory.
- **No creature system_prompt modification.** LxM task-shell is prepended
  to each turn prompt at the adapter boundary. Creature identity
  (SELF.md, bonds, voice register) is never overwritten.
- **Resilience is delegated to Ludex.** LxM adapter-level retries are
  forced to 0; the creature's ResilienceBlock owns recovery.
- **Memory is written per-turn (Phase 1).** Per-match distilled
  consolidation (§5 Q9 in Ludex Cody's round 2 reply) is deferred to M2 —
  this MVP writes raw episodic entries and lets consolidation happen on
  the Ludex side via its own dream cycle.

Usage (via run_match.py):

    python scripts/run_match.py --game trustgame \\
        --agents primo rule_bot_tft \\
        --adapters ludex rule_bot \\
        --creature-paths ~/Projects/ludex/creatures/Primo none \\
        --discovery-turns 0 --invocation-mode inline \\
        --skip-eval
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from lxm.adapters.base import AgentAdapter
from lxm.envelope import parse_from_stdout

logger = logging.getLogger(__name__)


# Default location of the Ludex checkout. Override with LXM_LUDEX_PATH.
_DEFAULT_LUDEX_PATH = os.path.expanduser("~/Projects/ludex")

# Default task-shell path.
_DEFAULT_GAME_SHELL = (
    Path(__file__).parent.parent.parent / "shells" / "system" / "lxm_game_shell.md"
)


def _ensure_ludex_on_path() -> None:
    """Add the configured Ludex checkout to sys.path if not importable."""
    try:
        import ludex  # noqa: F401
        return
    except ImportError:
        pass

    ludex_path = os.environ.get("LXM_LUDEX_PATH", _DEFAULT_LUDEX_PATH)
    if not os.path.isdir(ludex_path):
        raise ImportError(
            f"Ludex not importable and {ludex_path} does not exist. "
            f"Set LXM_LUDEX_PATH to the Ludex checkout root, or "
            f"`pip install -e {ludex_path}`."
        )
    sys.path.insert(0, ludex_path)
    # Retry import — fail fast with a clear error if still broken.
    import ludex  # noqa: F401


class LudexCreatureAdapter(AgentAdapter):
    """Adapter that runs a Ludex creature as an LxM agent.

    Required agent_config keys:
        agent_id: str
        creature_path: str — path to the creature directory (containing
            ludex.json / ludex.yaml + habitat subdirs)

    Optional:
        game_shell: str — path to task-shell markdown to prepend (defaults
            to shells/system/lxm_game_shell.md)
        record_memory: bool — whether to write LxM turn experiences into
            creature memory (default True)
    """

    def __init__(self, agent_config: dict):
        # Force LxM-side resilience off; Ludex ResilienceBlock takes over.
        cfg = {
            **agent_config,
            "resilience": {
                "max_retries": 0,
                "base_delay": 0.0,
                "max_delay": 0.0,
                "failure_threshold": 10**9,
            },
        }
        super().__init__(cfg)

        creature_path = agent_config.get("creature_path")
        if not creature_path:
            raise ValueError(
                "LudexCreatureAdapter requires 'creature_path' in agent_config"
            )
        self._creature_path = os.path.expanduser(creature_path)
        if not os.path.isdir(self._creature_path):
            raise FileNotFoundError(
                f"Creature path does not exist: {self._creature_path}"
            )

        _ensure_ludex_on_path()

        from ludex.core.organism_config import OrganismConfig

        self._creature_config = OrganismConfig.load(self._creature_path)

        # Normalize habitat.home_dir to absolute path. Creature configs
        # typically store `"./creatures/<Name>"` relative to the Ludex
        # checkout root; if we build from LxM's cwd that path resolves
        # into LxM's tree instead of Ludex's, silently forking the
        # creature's memory into a duplicate store.
        if self._creature_config.habitat.home_dir:
            resolved = Path(self._creature_config.habitat.home_dir)
            if not resolved.is_absolute():
                resolved = Path(self._creature_path).resolve()
            self._creature_config.habitat.home_dir = str(resolved)

        self._organism = self._creature_config.build()
        self._engine = self._organism.get_block("engine")
        self._memory = self._organism.get_block("memory")
        self._emotion = self._organism.get_block("emotion")

        # Match LxM-side timeout to the Ludex provider subprocess timeout
        # so Avalon-class long matches don't SIGKILL mid-turn (joint spec
        # §D.7 b — Primo B_1 incident). LxM's `timeout_seconds` is the
        # turn budget seen at the orchestrator level; we forward it as
        # the underlying provider wall-clock cap.
        provider = self._organism.get_block("provider")
        if provider is not None and hasattr(provider, "set_timeout_ms"):
            try:
                provider.set_timeout_ms(int(self._timeout) * 1000)
            except Exception as e:
                logger.debug(f"set_timeout_ms({self._timeout}s) failed: {e}")

        # Load task-shell once — prepended to every prompt.
        shell_path = Path(agent_config.get("game_shell") or _DEFAULT_GAME_SHELL)
        try:
            self._game_shell = shell_path.read_text(encoding="utf-8").strip()
        except OSError as e:
            logger.warning(f"Could not read game_shell {shell_path}: {e}")
            self._game_shell = ""

        self._record_memory = bool(agent_config.get("record_memory", True))
        self._match_id_hint = agent_config.get("match_id", "")

        # Expose creature display info for logs.
        self._display_name = agent_config.get(
            "display_name", self._creature_config.name
        )

        logger.info(
            f"LudexCreatureAdapter ready: {self._creature_config.name} "
            f"(brain={self._creature_config.brain.get('provider')}:"
            f"{self._creature_config.brain.get('model')}, "
            f"organs={self._creature_config.get_enabled_organs()}, "
            f"session #{self._creature_config.session_count})"
        )

    @property
    def creature_name(self) -> str:
        return self._creature_config.name

    def _invoke_once(self, match_dir: str, prompt: str) -> dict:
        match_id = Path(match_dir).name if match_dir else self._match_id_hint
        full_prompt = (
            f"{self._game_shell}\n\n---\n\n{prompt}" if self._game_shell else prompt
        )

        try:
            result = self._engine.handle_submit(full_prompt)
        except Exception as e:
            logger.exception("Creature engine raised during handle_submit")
            return {
                "stdout": "",
                "stderr": f"Ludex engine error: {e}",
                "exit_code": -1,
                "timed_out": False,
                "tokens_in": 0,
                "tokens_out": 0,
            }

        response_text = (result.response or "").strip()
        timed_out = result.stop_reason in ("max_turns", "max_budget")

        # Record this turn as episodic memory on the creature side.
        # Content is the creature's own utterance — not the prompt.
        # Ludex Cody flagged (round 4): storing prompt tail pollutes future
        # recall with LxM engine boilerplate. The prompt is in LxM's
        # log.json; the creature's memory should capture its own behavior.
        if self._record_memory and self._memory and response_text:
            try:
                self._memory.handle_remember(
                    content=self._summarize_turn(
                        response_text, self._agent_id, match_id
                    ),
                    memory_type="episodic",
                    tags=["lxm", match_id],
                    importance=0.5,
                    source=f"lxm/{match_id}/turn",
                )
            except Exception as e:
                logger.debug(f"Memory write skipped: {e}")

        stderr = result.error or ""
        exit_code = 0 if not result.error else 1

        # Enrich envelope with ludex_state snapshot. We parse the creature's
        # response into an envelope, inject meta.ludex_state, and return that
        # as stdout so the orchestrator's log captures per-turn creature state.
        # If parsing fails, fall back to raw response (orchestrator will fail
        # envelope extraction the same way as with any other adapter).
        enriched_stdout = self._enrich_envelope(response_text, match_id)

        # Debug — dump first turn per match to help diagnose envelope parse issues
        if match_dir and os.environ.get("LXM_LUDEX_DEBUG"):
            try:
                dbg_dir = Path(match_dir) / "debug"
                dbg_dir.mkdir(exist_ok=True)
                dbg_path = dbg_dir / f"ludex_stdout_{self._agent_id}.txt"
                if not dbg_path.exists():  # first turn only
                    dbg_path.write_text(enriched_stdout, encoding="utf-8")
            except Exception:
                pass

        return {
            "stdout": enriched_stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "tokens_in": result.tokens_in or 0,
            "tokens_out": result.tokens_out or 0,
        }

    def _enrich_envelope(self, response_text: str, match_id: str) -> str:
        """Return stdout as a full envelope JSON with meta.ludex_state attached.

        Falls back to raw response_text if no envelope can be parsed.
        """
        parsed = parse_from_stdout(response_text)
        if parsed is None or not isinstance(parsed.get("move"), dict):
            return response_text

        parsed.setdefault("meta", {})
        parsed["meta"]["reasoning"] = response_text[:800]
        parsed["meta"]["ludex_state"] = self._snapshot_ludex_state(response_text)
        parsed.setdefault("kind", "creature")
        try:
            return json.dumps(parsed, ensure_ascii=False)
        except (TypeError, ValueError):
            return response_text

    def _snapshot_ludex_state(self, creature_text: str) -> dict:
        """Collect a small per-turn observability snapshot from creature organs.

        All reads are best-effort; missing/failing organs return empty fields
        instead of raising. This keeps the hook robust to partial organism
        configurations (e.g. a creature without emotion or memory).
        """
        snapshot: dict[str, Any] = {}

        if self._emotion is not None:
            try:
                vitals = self._emotion.handle_analyze_emotion(creature_text)
                snapshot["emotion"] = {
                    "valence": round(vitals.valence, 3),
                    "arousal": round(vitals.arousal, 3),
                    "dominant": vitals.dominant_emotion,
                    "method": vitals.estimation_method,
                }
            except Exception as e:
                logger.debug(f"emotion snapshot skipped: {e}")

        if self._memory is not None:
            try:
                snapshot["memory_entries"] = len(getattr(self._memory, "_memories", {}))
                last = getattr(self._memory, "last_recall", None)
                if last is not None:
                    _query, recalls = last
                    snapshot["recall_top5"] = [
                        {
                            "memory_id": r.memory.id,
                            "memory_type": r.memory.memory_type,
                            "tags": list(r.memory.tags),
                            "relevance": round(r.relevance, 3),
                            "content": r.memory.content[:200],
                        }
                        for r in recalls[:5]
                    ]
            except Exception as e:
                logger.debug(f"memory snapshot skipped: {e}")

        return snapshot

    def on_match_end(self, match_result: dict, match_id: str, match_dir: str) -> None:
        """Commit a distilled summary of this match to creature's memory.

        Calls Ludex `emit_lxm_match_experience()` (Ludex r5) to write a
        single semantic entry tagged `["lxm", match_id, "distilled"]`.
        LxM owns the one-line `summary`; Ludex owns persistence and span.
        """
        if not self._record_memory:
            return
        try:
            from ludex.core.trace import emit_lxm_match_experience
        except ImportError:
            logger.debug("emit_lxm_match_experience unavailable; skipping")
            return

        summary = self._build_match_summary(match_result)
        outcome = self._outcome_label(match_result)
        moves_count = self._count_my_moves(match_result)
        game = self._game_hint_from_match(match_dir)
        interactions = self._compute_interactions(match_dir, game)

        try:
            emit_lxm_match_experience(
                organism=self._organism,
                match_id=match_id,
                summary=summary,
                moves_count=moves_count,
                outcome=outcome,
                meta={
                    "game": game,
                    "agent_id": self._agent_id,
                    "interactions": interactions,
                },
            )
        except Exception as e:
            logger.debug(f"emit_lxm_match_experience failed for {self._agent_id}: {e}")

        # D-067 Phase B v3 physis ingest. Best-effort — any failure is
        # logged and does not break match flow. Runs only when the
        # creature has a physis block AND the game has a world_schema,
        # so games / creatures opted out experience zero side-effects.
        try:
            self._try_physis_ingest(match_id=match_id, game=game,
                                    match_result=match_result)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "physis ingest failed for %s on %s: %s: %s",
                self._agent_id, match_id, type(e).__name__, e,
            )

    def _try_physis_ingest(
        self,
        *,
        match_id: str,
        game: str,
        match_result: dict,
    ) -> None:
        """(X)-pattern physis ingest per Mac Ludex Cody coordination
        2026-04-28: iterate trace.jsonl lines → physis.handle_step →
        physis.handle_consolidate. trace.jsonl is written by
        scripts/run_match._try_export_trace just before this hook
        runs.

        Skips silently when:
          - the wrapped organism has no physis block
          - the game has no world_schema.json yet
          - trace.jsonl is missing (export was skipped)
        """
        physis = self._organism.get_block("physis")
        if physis is None:
            return

        try:
            from lxm import world_model
        except ImportError:
            return

        # Resolve schema + trace path via the same pipeline that wrote
        # the trace. If the game isn't physis-enabled this raises
        # FileNotFoundError and we fall through to the silent skip.
        try:
            _, schema = world_model.schema_for_match(match_id)
        except FileNotFoundError:
            return

        field = schema.get("field") or f"lxm/{game}"
        # Conventional path; export hook uses schema-declared trace_path
        # (which is a relative template), so reconstruct the same way.
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent.parent
        trace_template = schema.get(
            "trace_path",
            f"traces/{field}/<match_id>/trace.jsonl",
        )
        trace_path = repo_root / trace_template.replace("<match_id>", match_id)
        if not trace_path.exists():
            # `on_match_end` fires from inside `orch.run()`; the
            # trace-export hook in scripts/run_match.py runs *after*
            # orch.run() returns, so during normal flow we hit this
            # branch every time. Self-sufficiency: export now.
            try:
                world_model.export_match_trace(match_id)
            except Exception as e:  # noqa: BLE001
                logger.warning("physis ingest: trace export failed: %s", e)
                return
            if not trace_path.exists():
                logger.debug("physis ingest: trace still missing after export")
                return

        # Replay trace into physis trace_buffer.
        import json as _json
        steps_replayed = 0
        with trace_path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    line = _json.loads(raw_line)
                except _json.JSONDecodeError:
                    continue
                kw = world_model.trace_line_to_handle_step_kwargs(line, field=field)
                if kw is None:
                    continue
                # Filter to this creature's turns. Echo participating
                # in an Avalon match shouldn't ingest peers' moves as
                # if they were her own action choices — that would
                # poison the policy hint distribution.
                if kw.get("active_agent_id") and kw["active_agent_id"] != self._agent_id:
                    continue
                physis.handle_step(**kw)
                steps_replayed += 1

        outcome_label = self._outcome_label(match_result)
        engine_block = self._organism.get_block("engine")
        try:
            physis.handle_consolidate(
                field=field,
                brain_engine=engine_block,
                episode_id=match_id,
                outcome=outcome_label,
            )
            logger.info(
                "physis: ingested %d steps + consolidated %s/%s outcome=%s",
                steps_replayed, field, match_id, outcome_label,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "physis.handle_consolidate failed for %s on %s: %s: %s",
                self._agent_id, match_id, type(e).__name__, e,
            )

    def _compute_interactions(self, match_dir: str, game: str) -> dict:
        """Per-opponent interaction summary derived from match log.

        Joint spec §F.11 Q1 answer — LxM never writes bonds directly, but
        provides a structured per-pair aggregation so Ludex's post-match
        consolidation pipeline can map events to bond updates using
        creature-autonomous organ logic (immune, emotion, humoral_immune).

        Per-game dispatch: Trust Game tracks coop/defect tally; Avalon
        tracks quest co-membership, vote agreement, sabotage events, and
        nominations. Unknown games get an empty dict — consumer can
        inspect the raw log if richer extraction is needed.
        """
        if not match_dir:
            return {}
        try:
            log = json.loads((Path(match_dir) / "log.json").read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug(f"interactions: could not read log.json: {e}")
            return {}

        try:
            if game == "trustgame":
                return self._trustgame_interactions(log)
            if game == "avalon":
                return self._avalon_interactions(log, match_dir)
        except Exception as e:
            logger.debug(f"interactions compute ({game}) failed: {e}")
        return {}

    def _trustgame_interactions(self, log: list) -> dict:
        """Per-round coop/defect tally vs the opponent."""
        stats: dict[str, dict] = {}
        # Walk accepted turns, extract action per agent per round.
        # In Trust Game, each round has both agents submit, state carries
        # the pending_move. We track my and their actions separately then
        # join per round via post_move_context history.
        my_id = self._agent_id
        per_agent_actions: dict[str, list[str]] = {}
        for entry in log:
            if entry.get("result") != "accepted":
                continue
            aid = entry.get("agent_id")
            move = (entry.get("envelope") or {}).get("move") or {}
            action = move.get("action")
            if action in ("cooperate", "defect") and aid:
                per_agent_actions.setdefault(aid, []).append(action)
        opponents = [aid for aid in per_agent_actions if aid != my_id]
        for opp in opponents:
            mine = per_agent_actions.get(my_id, [])
            theirs = per_agent_actions.get(opp, [])
            shared = min(len(mine), len(theirs))
            stats[opp] = {
                "shared_rounds": shared,
                "my_cooperates": sum(1 for a in mine[:shared] if a == "cooperate"),
                "my_defects": sum(1 for a in mine[:shared] if a == "defect"),
                "their_cooperates": sum(1 for a in theirs[:shared] if a == "cooperate"),
                "their_defects": sum(1 for a in theirs[:shared] if a == "defect"),
                "mutual_cooperate_rounds": sum(
                    1 for i in range(shared)
                    if mine[i] == "cooperate" and theirs[i] == "cooperate"
                ),
                "i_defected_they_cooperated": sum(
                    1 for i in range(shared)
                    if mine[i] == "defect" and theirs[i] == "cooperate"
                ),
                "they_defected_i_cooperated": sum(
                    1 for i in range(shared)
                    if mine[i] == "cooperate" and theirs[i] == "defect"
                ),
            }
        return stats

    def _avalon_interactions(self, log: list, match_dir: str) -> dict:
        """Per-other-agent Avalon summary.

        Signals (per opponent):
          - shared_quest_teams: times both on same quest team
          - nominated_me: they nominated me into a team
          - i_nominated_them: I nominated them into a team
          - votes_agreed: times we voted the same on a proposal
          - votes_disagreed: times we voted differently
          - sabotages_on_shared_team: sabotage events while we shared a team
          - their_role / my_role: from final state (leaks role to
            consolidation pipeline, which is fine — this is post-match
            ground truth, not in-game reasoning)
        """
        stats: dict[str, dict] = {}
        my_id = self._agent_id

        # Final roles from state.json if available
        my_role = None
        their_role: dict[str, str] = {}
        try:
            state = json.loads((Path(match_dir) / "state.json").read_text(encoding="utf-8"))
            players = state.get("game", {}).get("current", {}).get("players", {}) or {}
            my_role = (players.get(my_id) or {}).get("role")
            for aid, info in players.items():
                if aid != my_id:
                    their_role[aid] = info.get("role")
        except Exception:
            pass

        # Walk accepted turns and extract per-phase moves.
        # vote_tracker[proposal_index] = {agent_id: choice}
        current_proposal_team: list[str] = []
        current_proposal_leader: str | None = None
        proposals: list[dict] = []  # {"leader", "team", "votes": {aid: choice}}
        for entry in log:
            if entry.get("result") != "accepted":
                continue
            aid = entry.get("agent_id")
            move = (entry.get("envelope") or {}).get("move") or {}
            mtype = move.get("type")
            if mtype == "proposal":
                team = list(move.get("team") or [])
                proposals.append({"leader": aid, "team": team, "votes": {}, "quest_actions": {}})
                current_proposal_team = team
                current_proposal_leader = aid
            elif mtype == "vote" and proposals:
                proposals[-1]["votes"][aid] = move.get("choice")
            elif mtype == "quest_action" and proposals:
                proposals[-1]["quest_actions"][aid] = move.get("choice")

        # Aggregate per opponent
        for opp in their_role.keys():
            s = {
                "their_role": their_role.get(opp),
                "my_role": my_role,
                "shared_quest_teams": 0,
                "nominated_me": 0,
                "i_nominated_them": 0,
                "votes_agreed": 0,
                "votes_disagreed": 0,
                "sabotages_on_shared_team": 0,
            }
            for p in proposals:
                leader = p["leader"]
                team = set(p["team"])
                # Nominations
                if leader == opp and my_id in team:
                    s["nominated_me"] += 1
                if leader == my_id and opp in team:
                    s["i_nominated_them"] += 1
                # Shared team (only counts if proposal passed → quest happened;
                # use presence of quest_actions as passage signal)
                shared = my_id in team and opp in team and bool(p["quest_actions"])
                if shared:
                    s["shared_quest_teams"] += 1
                    # Sabotage events on shared team
                    if p["quest_actions"].get(opp) == "sabotage":
                        s["sabotages_on_shared_team"] += 1
                # Votes
                my_vote = p["votes"].get(my_id)
                their_vote = p["votes"].get(opp)
                if my_vote and their_vote:
                    if my_vote == their_vote:
                        s["votes_agreed"] += 1
                    else:
                        s["votes_disagreed"] += 1
            stats[opp] = s
        return stats

    def _build_match_summary(self, match_result: dict) -> str:
        """One-line, ≤ 400-char summary for the distilled semantic memory.

        We keep this factual (outcome + opponent action summary). Narrative
        interpretation is left to the creature's own dream consolidation —
        see joint spec §A.4 rationale.
        """
        base = match_result.get("summary") or ""
        if not base:
            outcome = match_result.get("outcome", "unknown")
            winner = match_result.get("winner") or "—"
            base = f"outcome={outcome}; winner={winner}"
        return base[:400]

    @staticmethod
    def _outcome_label(match_result: dict) -> str:
        winner = match_result.get("winner")
        raw = (match_result.get("outcome") or "").lower()
        if raw in ("timeout",):
            return "timeout"
        if raw in ("draw", "tie"):
            return "draw"
        if winner:
            return "win"
        return "loss"

    def _count_my_moves(self, match_result: dict) -> int:
        """Actual move count for this agent, preferring per-agent vitals.

        Previously returned `len(scores)` (always 2 for duel games), which
        misled the distilled semantic entry. Orchestrator's MatchVitals
        records `per_agent.<id>.turns` — the real count of invocations
        for this agent. Fall back to top-level `rounds_played` or 0.
        """
        per_agent = (match_result.get("vitals") or {}).get("per_agent") or {}
        me = per_agent.get(self._agent_id)
        if isinstance(me, dict) and "turns" in me:
            try:
                return int(me["turns"])
            except (TypeError, ValueError):
                pass
        return int(match_result.get("rounds_played", 0) or 0)

    @staticmethod
    def _game_hint_from_match(match_dir: str) -> str:
        try:
            cfg_path = Path(match_dir) / "match_config.json"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                return cfg.get("game", {}).get("name", "")
        except Exception:
            pass
        return ""

    def _summarize_turn(self, response: str, agent_id: str, match_id: str) -> str:
        """Compact episodic memory entry for one LxM turn.

        We store the creature's own utterance, not the LxM prompt — the
        prompt is already preserved in the match's log.json. Keeping
        memory focused on behavior (what the creature said/chose) means
        future recall surfaces the creature's actual experience rather
        than engine boilerplate.
        """
        body = response[:400].strip().replace("\n", " ")
        return f"{agent_id} @{match_id}: {body}"
