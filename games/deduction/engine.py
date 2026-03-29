"""Deduction Game — AI 추리 게임.

에이전트가 탐정 역할. 단서 파일을 선택적으로 읽고, 메모를 작성하고,
범인(Who) + 동기(Why) + 수단(How)을 추론해서 제출.

Move types:
  - read: 단서 파일 읽기
  - note: 추론 메모 작성
  - submit: 최종 답변 제출

Solo mode (1 agent) 먼저 구현. Race mode (2 agents) 나중에.
"""

import json
from pathlib import Path

from lxm.engine import LxMGame

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


class DeductionGame(LxMGame):
    """AI Deduction Game. CLI-native — agents explore evidence folders."""

    def __init__(self, scenario_id: str = "mystery_001"):
        self._scenario_id = scenario_id
        self._scenario = self._load_scenario(scenario_id)

    def _load_scenario(self, scenario_id: str) -> dict:
        scenario_path = SCENARIOS_DIR / scenario_id / "scenario.json"
        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario not found: {scenario_path}")
        return json.loads(scenario_path.read_text(encoding="utf-8"))

    def _load_case_brief(self) -> str:
        brief_path = SCENARIOS_DIR / self._scenario_id / "case_brief.md"
        if brief_path.exists():
            return brief_path.read_text(encoding="utf-8")
        return "No case brief available."

    def _load_evidence(self, filename: str) -> str:
        evidence_path = SCENARIOS_DIR / self._scenario_id / "evidence" / filename
        if evidence_path.exists():
            return evidence_path.read_text(encoding="utf-8")
        return f"File not found: {filename}"

    def get_rules(self) -> str:
        return """# Deduction Game Rules

You are a detective investigating a case. Your goal is to determine:
- **Who** committed the crime (culprit)
- **Why** they did it (motive)
- **How** they did it (method)

## Actions

Each turn, choose ONE action:

1. **READ** — Read an evidence file
   ```json
   {"type": "deduction_action", "action": "read", "file": "filename.md"}
   ```

2. **NOTE** — Write reasoning notes (optional, helps organize thoughts)
   ```json
   {"type": "deduction_action", "action": "note", "content": "Your notes here..."}
   ```

3. **SUBMIT** — Submit your final answer (ends the game)
   ```json
   {"type": "deduction_action", "action": "submit", "answer": {"culprit": "A/B/C", "motive": "reason", "method": "how"}}
   ```

## Scoring
- Culprit correct: +1 point
- Motive correct: +1 point
- Method correct: +1 point
- Efficiency bonus: fewer files read = higher bonus

## Tips
- Read the case brief carefully first
- Not all evidence is equally important — choose wisely
- Submit when you're confident — reading everything isn't always necessary
"""

    def initial_state(self, agents: list[dict]) -> dict:
        evidence_files = self._scenario.get("evidence_files", [])
        # Also include any extra files in evidence/ not listed in scenario.json
        evidence_dir = SCENARIOS_DIR / self._scenario_id / "evidence"
        if evidence_dir.exists():
            all_files = sorted(f.name for f in evidence_dir.iterdir() if f.suffix == ".md")
            # Merge: scenario list + any extra files
            evidence_files = sorted(set(evidence_files) | set(all_files))

        agent_states = {}
        for agent in agents:
            agent_id = agent["agent_id"]
            agent_states[agent_id] = {
                "files_read": [],
                "files_available": list(evidence_files),
                "notes": "",
                "submitted": False,
                "answer": None,
                "read_count": 0,
                "last_read_content": None,
            }

        return {
            "current": {
                "phase": "investigating",
                "turn": 1,
                "agents": agent_states,
                "scenario_id": self._scenario_id,
            },
            "context": {
                "max_reads": self._scenario.get("max_reads", 20),
                "total_evidence": len(evidence_files),
                "difficulty": self._scenario.get("difficulty", "medium"),
                "title": self._scenario.get("title", "Unknown Case"),
                "suspects": self._scenario.get("suspects", []),
                "suspect_names": self._scenario.get("suspect_names", {}),
                "case_brief": self._load_case_brief(),
            },
        }

    def get_timeout_move(self, agent_id: str, state: dict) -> dict | None:
        """On timeout, auto-submit with empty answer."""
        agent = state.get("game", state).get("current", {}).get("agents", {}).get(agent_id, {})
        if not agent.get("submitted"):
            return {
                "type": "deduction_action",
                "action": "submit",
                "answer": {"culprit": "", "motive": "", "method": ""},
            }
        return None

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state.get("game", state)
        current = game["current"]
        agent = current["agents"].get(agent_id)

        if not agent:
            return {"valid": False, "message": f"Unknown agent: {agent_id}"}

        if agent["submitted"]:
            return {"valid": False, "message": "Already submitted answer"}

        if move.get("type") != "deduction_action":
            return {"valid": False, "message": "move.type must be 'deduction_action'"}

        action = move.get("action")
        if action not in ("read", "note", "submit"):
            return {"valid": False, "message": "action must be: read, note, or submit"}

        if action == "read":
            filename = move.get("file", "")
            if not filename:
                return {"valid": False, "message": "read action requires 'file' field"}
            if filename not in agent["files_available"]:
                return {"valid": False, "message": f"File not available: {filename}. Available: {agent['files_available']}"}
            max_reads = game.get("context", {}).get("max_reads", 20)
            if agent["read_count"] >= max_reads:
                return {"valid": False, "message": f"Max reads ({max_reads}) reached. Must submit."}

        elif action == "note":
            content = move.get("content", "")
            if not content:
                return {"valid": False, "message": "note action requires 'content' field"}
            if len(content) > 2000:
                return {"valid": False, "message": "Note too long (max 2000 chars)"}

        elif action == "submit":
            answer = move.get("answer", {})
            if not isinstance(answer, dict):
                return {"valid": False, "message": "submit requires 'answer' dict"}
            if "culprit" not in answer:
                return {"valid": False, "message": "answer must include 'culprit'"}
            # Validate against options if available (don't reject if no options defined)
            motive_opts = self._get_options("motive")
            if motive_opts and answer.get("motive") and answer["motive"] not in motive_opts:
                return {"valid": False, "message": f"motive must be one of: {motive_opts}. Got: {answer['motive']}"}
            method_opts = self._get_options("method")
            if method_opts and answer.get("method") and answer["method"] not in method_opts:
                return {"valid": False, "message": f"method must be one of: {method_opts}. Got: {answer['method']}"}

        return {"valid": True, "message": None}

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state.get("game", state)
        current = game["current"]
        context = game["context"]
        agent = current["agents"][agent_id]
        action = move["action"]

        if action == "read":
            filename = move["file"]
            content = self._load_evidence(filename)
            if filename not in agent["files_read"]:
                agent["files_read"].append(filename)
            agent["read_count"] += 1
            agent["last_read_content"] = content

        elif action == "note":
            agent["notes"] = move["content"]

        elif action == "submit":
            agent["submitted"] = True
            agent["answer"] = move["answer"]
            current["phase"] = "submitted"

        return {"current": current, "context": context}

    def is_over(self, state: dict) -> bool:
        game = state.get("game", state)
        current = game["current"]
        # Game ends when all agents have submitted
        for agent in current["agents"].values():
            if not agent["submitted"]:
                return False
        return True

    def get_result(self, state: dict) -> dict:
        game = state.get("game", state)
        current = game["current"]
        context = game["context"]
        answer_key = self._scenario["answer"]

        results = {}
        aliases = self._scenario.get("answer_aliases", {})
        answer_ko = self._scenario.get("answer_ko", {})

        for agent_id, agent in current["agents"].items():
            answer = agent.get("answer", {}) or {}

            # Accuracy (0-3)
            culprit_correct = 1 if answer.get("culprit", "").upper() == answer_key["culprit"].upper() else 0
            # Score motive/method — use options if available, else alias fallback
            motive_opts = self._get_options("motive")
            method_opts = self._get_options("method")
            motive_aliases = list(aliases.get("motive", []))
            method_aliases = list(aliases.get("method", []))
            if answer_ko.get("motive"):
                motive_aliases.append(answer_ko["motive"])
            if answer_ko.get("method"):
                method_aliases.append(answer_ko["method"])

            if motive_opts:
                motive_correct = self._score_option_match(
                    answer.get("motive", ""), answer_key["motive"], motive_opts, motive_aliases,
                )
            else:
                motive_correct = self._score_text_match(
                    answer.get("motive", ""), answer_key["motive"], motive_aliases,
                )

            if method_opts:
                method_correct = self._score_option_match(
                    answer.get("method", ""), answer_key["method"], method_opts, method_aliases,
                )
            else:
                method_correct = self._score_text_match(
                    answer.get("method", ""), answer_key["method"], method_aliases,
                )
            accuracy = culprit_correct + motive_correct + method_correct

            # Efficiency
            total = context.get("total_evidence", 1)
            files_read = len(agent.get("files_read", []))
            efficiency = 1 - (files_read / total) if total > 0 else 0

            # Final score
            final_score = accuracy * (1 + efficiency * 0.5)

            results[agent_id] = {
                "accuracy": accuracy,
                "culprit_correct": bool(culprit_correct),
                "motive_correct": motive_correct,
                "method_correct": method_correct,
                "files_read": files_read,
                "total_evidence": total,
                "efficiency": round(efficiency, 3),
                "final_score": round(final_score, 2),
                "answer": answer,
                "correct_answer": answer_key,
            }

        # Winner = highest final_score
        best_agent = max(results, key=lambda a: results[a]["final_score"])
        best_score = results[best_agent]["final_score"]

        scores = {aid: r["final_score"] for aid, r in results.items()}

        summary_parts = []
        for aid, r in results.items():
            summary_parts.append(
                f"{aid}: {r['accuracy']}/3 correct "
                f"({r['files_read']}/{r['total_evidence']} files read, "
                f"score {r['final_score']})"
            )

        return {
            "outcome": "solved" if best_score > 0 else "unsolved",
            "winner": best_agent if len(results) > 1 else None,
            "scores": scores,
            "summary": ". ".join(summary_parts),
            "details": results,
        }

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        action = move.get("action", "?")
        if action == "read":
            return f"Read {move.get('file', '?')}"
        elif action == "note":
            content = move.get("content", "")
            preview = content[:60] + "..." if len(content) > 60 else content
            return f"Note: {preview}"
        elif action == "submit":
            answer = move.get("answer", {})
            return f"SUBMIT: culprit={answer.get('culprit')}, motive={answer.get('motive')}, method={answer.get('method')}"
        return f"Unknown action: {action}"

    def get_evaluation_schema(self) -> dict:
        return {"type": "deduction", "metrics": ["accuracy", "efficiency", "final_score"]}

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        game = state.get("game", state)
        current = game["current"]
        context = game["context"]
        agent = current["agents"].get(agent_id)

        if not agent or agent["submitted"]:
            return None

        case_brief = context.get("case_brief", "")
        suspects = context.get("suspect_names", {})
        files_read = agent["files_read"]
        files_available = [f for f in agent["files_available"] if f not in files_read]
        notes = agent.get("notes", "")
        last_content = agent.get("last_read_content")
        read_count = agent.get("read_count", 0)
        max_reads = context.get("max_reads", 20)

        parts = []

        # Case brief (always shown)
        parts.append(f"=== CASE: {context.get('title', 'Unknown')} ({context.get('difficulty', '?')}) ===\n")
        parts.append(case_brief)
        parts.append("")

        # Suspects
        if suspects:
            parts.append("=== SUSPECTS ===")
            for sid, name in suspects.items():
                parts.append(f"  {sid}: {name}")
            parts.append("")

        # Last read content (if any)
        if last_content and turn > 1:
            parts.append(f"=== LAST FILE READ ===")
            parts.append(last_content)
            parts.append("")

        # Progress
        parts.append(f"=== YOUR PROGRESS ===")
        parts.append(f"Files read ({len(files_read)}/{context.get('total_evidence', '?')}): {', '.join(files_read) if files_read else 'None'}")
        parts.append(f"Reads remaining: {max_reads - read_count}")
        if files_available:
            parts.append(f"Available files: {', '.join(files_available)}")
        else:
            parts.append("All files read.")
        if notes:
            parts.append(f"Your notes: {notes}")
        parts.append("")

        # Action prompt
        parts.append("=== YOUR TURN ===")
        parts.append("Choose ONE action:")
        parts.append('  READ:   {"type": "deduction_action", "action": "read", "file": "<filename>"}')
        parts.append('  NOTE:   {"type": "deduction_action", "action": "note", "content": "<your reasoning>"}')

        # Build SUBMIT options
        suspect_ids = "/".join(context.get("suspects", ["A", "B", "C"]))
        motive_opts = self._scenario.get("motive_options") or self._scenario.get("motive_options_ko")
        method_opts = self._scenario.get("method_options") or self._scenario.get("method_options_ko")

        if motive_opts and method_opts:
            motive_str = " / ".join(motive_opts)
            method_str = " / ".join(method_opts)
            parts.append(f'  SUBMIT: {{"type": "deduction_action", "action": "submit", "answer": {{"culprit": "{suspect_ids}", "motive": "<PICK ONE EXACTLY>", "method": "<PICK ONE EXACTLY>"}}}}')
            parts.append(f"    MOTIVE — pick one exactly as written: {motive_str}")
            parts.append(f"    METHOD — pick one exactly as written: {method_str}")
            parts.append(f"    WARNING: motive and method MUST be copied exactly from the options above. Free text will be rejected.")
        else:
            parts.append(f'  SUBMIT: {{"type": "deduction_action", "action": "submit", "answer": {{"culprit": "{suspect_ids}", "motive": "...", "method": "..."}}}}')

        if read_count >= max_reads:
            parts.append(f"\n⚠ Max reads ({max_reads}) reached. You must SUBMIT now.")

        return "\n".join(parts)

    def filter_state_for_agent(self, state: dict, agent_id: str) -> dict:
        """Hide other agents' state in Race mode."""
        # Solo mode: no filtering needed
        return state

    def _get_options(self, field: str) -> list[str]:
        """Get combined EN + KO options for a field (motive/method)."""
        opts = list(self._scenario.get(f"{field}_options", []))
        opts_ko = self._scenario.get(f"{field}_options_ko", [])
        return opts + opts_ko

    def _score_option_match(self, given: str, correct: str,
                            options: list[str], aliases: list[str]) -> float:
        """Score with options: exact match only. Falls back to alias if no options."""
        if not given:
            return 0

        # If options exist, do exact matching (EN or KO option)
        if options:
            given_clean = given.strip()
            correct_clean = correct.strip()
            if given_clean == correct_clean:
                return 1.0
            # Check if the given answer matches the KO version of the correct answer
            answer_ko = self._scenario.get("answer_ko", {})
            ko_correct = answer_ko.get(
                "motive" if correct in self._scenario.get("motive_options", []) else "method",
                ""
            )
            if ko_correct and given_clean == ko_correct.strip():
                return 1.0
            return 0

        # No options: fall back to alias matching
        return self._score_text_match(given, correct, aliases)

    @staticmethod
    def _score_text_match(given: str, correct: str,
                          aliases: list[str] | None = None) -> float:
        """Score text answer. Exact/alias match = 1, partial = 0.5, miss = 0.

        Aliases provide multilingual and synonym matching.
        """
        if not given:
            return 0
        given_lower = given.lower().strip().replace("_", " ").replace("-", " ")
        correct_lower = correct.lower().strip().replace("_", " ").replace("-", " ")

        # Exact match
        if given_lower == correct_lower:
            return 1.0

        # Alias match: if any alias keyword appears in the given answer → full credit
        if aliases:
            for alias in aliases:
                alias_lower = alias.lower().strip()
                if alias_lower in given_lower:
                    return 1.0

        # Partial match: key words overlap with correct answer
        given_words = set(given_lower.split())
        correct_words = set(correct_lower.split())
        if given_words & correct_words:
            return 0.5

        return 0
