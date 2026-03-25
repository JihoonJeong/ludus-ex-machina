"""Codenames game engine for LxM.

4-player team game: 2 teams × (spymaster + guesser).
Spymaster gives one-word clues, guesser finds team's words on a 5×5 board.
"""

import copy
import random
from pathlib import Path

from lxm.engine import LxMGame
from games.codenames.wordlist import WORD_LIST


class CodenamesGame(LxMGame):
    """Codenames — 2v2 word association game with asymmetric information."""

    GRID_SIZE = 5
    RED_FIRST_COUNT = 9  # Starting team gets 9
    OTHER_COUNT = 8
    NEUTRAL_COUNT = 7
    ASSASSIN_COUNT = 1

    def get_rules(self) -> str:
        rules_path = Path(__file__).parent / "rules.md"
        return rules_path.read_text(encoding="utf-8")

    def _build_teams(self, agents: list[dict]) -> dict:
        """Build team mapping from agent configs."""
        teams = {"red": {}, "blue": {}}
        for a in agents:
            team = a.get("team")
            role = a.get("role")
            if team and role:
                teams[team][role] = a["agent_id"]
        return teams

    def _get_agent_role(self, agent_id: str, teams: dict) -> str | None:
        """Return 'spymaster' or 'guesser' for a given agent_id."""
        for team_data in teams.values():
            for role, aid in team_data.items():
                if aid == agent_id:
                    return role
        return None

    def _get_agent_team(self, agent_id: str, teams: dict) -> str | None:
        """Return 'red' or 'blue' for a given agent_id."""
        for team_name, team_data in teams.items():
            for role, aid in team_data.items():
                if aid == agent_id:
                    return team_name
        return None

    def initial_state(self, agents: list[dict]) -> dict:
        teams = self._build_teams(agents)

        # Select 25 random words
        words = random.sample(WORD_LIST, 25)

        # Assign categories: 9 red, 8 blue, 7 neutral, 1 assassin
        categories = (
            ["red"] * self.RED_FIRST_COUNT
            + ["blue"] * self.OTHER_COUNT
            + ["neutral"] * self.NEUTRAL_COUNT
            + ["assassin"] * self.ASSASSIN_COUNT
        )
        random.shuffle(categories)

        # Build 5×5 board and answer key
        board = []
        answer_key = []
        for row in range(self.GRID_SIZE):
            board_row = []
            key_row = []
            for col in range(self.GRID_SIZE):
                idx = row * self.GRID_SIZE + col
                board_row.append({
                    "word": words[idx],
                    "revealed": False,
                    "revealed_as": None,
                })
                key_row.append(categories[idx])
            board.append(board_row)
            answer_key.append(key_row)

        return {
            "current": {
                "board": board,
                "answer_key": answer_key,
                "active_team": "red",
                "active_role": "spymaster",
                "current_clue": None,
                "guesses_remaining": 0,
                "teams": teams,
                "remaining": {
                    "red": self.RED_FIRST_COUNT,
                    "blue": self.OTHER_COUNT,
                },
            },
            "context": {
                "clue_history": [],
                "guess_history": [],
                "turns_played": 0,
                "key_events": [],
            },
        }

    def get_active_agent_id(self, state: dict) -> str | None:
        """Return the agent who should move next based on team/role state."""
        game = state.get("game", {})
        current = game.get("current", {})
        teams = current.get("teams", {})
        active_team = current.get("active_team")
        active_role = current.get("active_role")

        if not active_team or not active_role or not teams:
            return None

        team_data = teams.get(active_team, {})
        return team_data.get(active_role)

    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current = game["current"]
        teams = current["teams"]
        active_team = current["active_team"]
        active_role = current["active_role"]

        # Check agent is the active one
        expected_agent = teams.get(active_team, {}).get(active_role)
        if agent_id != expected_agent:
            return {"valid": False, "message": f"Not your turn. Expected {expected_agent}"}

        move_type = move.get("type")

        if active_role == "spymaster":
            # Must give a clue
            if move_type != "clue":
                return {"valid": False, "message": "Spymaster must give a clue (type='clue')"}

            word = move.get("word", "")
            number = move.get("number")

            if not isinstance(word, str) or not word.strip():
                return {"valid": False, "message": "Clue word must be a non-empty string"}
            if " " in word.strip():
                return {"valid": False, "message": "Clue must be a single word (no spaces)"}
            if not isinstance(number, int) or number < 0 or number > 9:
                return {"valid": False, "message": "Clue number must be an integer 0-9"}

            # Clue word must not be on the board (unrevealed)
            clue_upper = word.strip().upper()
            for row in current["board"]:
                for cell in row:
                    if not cell["revealed"] and cell["word"].upper() == clue_upper:
                        return {"valid": False, "message": f"Clue word '{word}' is on the board"}

            return {"valid": True, "message": None}

        elif active_role == "guesser":
            if move_type == "pass":
                return {"valid": True, "message": None}

            if move_type != "guess":
                return {"valid": False, "message": "Guesser must guess (type='guess') or pass (type='pass')"}

            if current["guesses_remaining"] <= 0:
                return {"valid": False, "message": "No guesses remaining"}

            guess_word = move.get("word", "").strip().upper()
            if not guess_word:
                return {"valid": False, "message": "Guess word must be non-empty"}

            # Must be an unrevealed word on the board
            found = False
            for row in current["board"]:
                for cell in row:
                    if cell["word"].upper() == guess_word and not cell["revealed"]:
                        found = True
                        break
                if found:
                    break

            if not found:
                return {"valid": False, "message": f"'{guess_word}' is not an unrevealed word on the board"}

            return {"valid": True, "message": None}

        return {"valid": False, "message": f"Unknown active_role: {active_role}"}

    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict:
        game = state["game"]
        current = copy.deepcopy(game["current"])
        context = copy.deepcopy(game["context"])

        move_type = move["type"]

        if move_type == "clue":
            clue_word = move["word"].strip()
            clue_number = move["number"]

            current["current_clue"] = {"word": clue_word, "number": clue_number}
            current["guesses_remaining"] = clue_number + 1
            current["active_role"] = "guesser"

            context["clue_history"].append({
                "team": current["active_team"],
                "word": clue_word,
                "number": clue_number,
                "turn": context["turns_played"] + 1,
            })
            context["turns_played"] += 1

        elif move_type == "guess":
            guess_word = move["word"].strip().upper()

            # Find and reveal the word
            category = None
            for r, row in enumerate(current["board"]):
                for c, cell in enumerate(row):
                    if cell["word"].upper() == guess_word and not cell["revealed"]:
                        category = current["answer_key"][r][c]
                        cell["revealed"] = True
                        cell["revealed_as"] = category
                        break
                if category is not None:
                    break

            current["guesses_remaining"] -= 1

            # Update remaining count
            if category in ("red", "blue"):
                current["remaining"][category] -= 1

            # Record guess
            context["guess_history"].append({
                "team": current["active_team"],
                "word": guess_word,
                "category": category,
                "correct": category == current["active_team"],
            })

            if category == "assassin":
                # Game will end — record event
                context["key_events"].append({
                    "type": "assassin",
                    "team": current["active_team"],
                    "word": guess_word,
                })
            elif category == current["active_team"]:
                # Correct guess — continue if guesses remain
                if current["guesses_remaining"] <= 0:
                    self._switch_team(current)
                    context["turns_played"] += 1
                # else: guesser continues
            else:
                # Wrong (opponent, neutral) — turn ends
                if category != "neutral":
                    context["key_events"].append({
                        "type": "opponent_revealed",
                        "team": current["active_team"],
                        "word": guess_word,
                        "category": category,
                    })
                self._switch_team(current)
                context["turns_played"] += 1

        elif move_type == "pass":
            self._switch_team(current)
            context["turns_played"] += 1

        return {"current": current, "context": context}

    def _switch_team(self, current: dict) -> None:
        """Switch to the other team's spymaster turn."""
        current["active_team"] = "blue" if current["active_team"] == "red" else "red"
        current["active_role"] = "spymaster"
        current["current_clue"] = None
        current["guesses_remaining"] = 0

    def is_over(self, state: dict) -> bool:
        game = state["game"]
        current = game["current"]
        remaining = current["remaining"]

        # A team found all their words
        if remaining["red"] == 0 or remaining["blue"] == 0:
            return True

        # Assassin was revealed
        for row in current["board"]:
            for cell in row:
                if cell["revealed"] and cell.get("revealed_as") == "assassin":
                    return True

        return False

    def get_result(self, state: dict) -> dict:
        game = state["game"]
        current = game["current"]
        remaining = current["remaining"]
        teams = current["teams"]
        context = game["context"]

        # Check for assassin
        assassin_team = None
        for event in context.get("key_events", []):
            if event["type"] == "assassin":
                assassin_team = event["team"]
                break

        if assassin_team:
            winner_team = "blue" if assassin_team == "red" else "red"
            outcome = "assassin"
            summary = f"Team {winner_team} wins — Team {assassin_team} hit the assassin!"
        elif remaining["red"] == 0:
            winner_team = "red"
            outcome = "complete"
            summary = f"Team red found all their words! ({remaining['blue']} blue remaining)"
        elif remaining["blue"] == 0:
            winner_team = "blue"
            outcome = "complete"
            summary = f"Team blue found all their words! ({remaining['red']} red remaining)"
        else:
            winner_team = None
            outcome = "unknown"
            summary = "Game ended without clear winner"

        # Scores: team members share win/loss
        scores = {}
        for team_name, team_data in teams.items():
            for role, aid in team_data.items():
                scores[aid] = 1.0 if team_name == winner_team else 0.0

        return {
            "outcome": outcome,
            "winner": winner_team,
            "winning_team": winner_team,
            "scores": scores,
            "summary": summary,
            "analysis": {
                "clues_given": len(context.get("clue_history", [])),
                "guesses_made": len(context.get("guess_history", [])),
                "remaining": remaining,
            },
        }

    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str:
        if move["type"] == "clue":
            return f'Clue: "{move["word"]}" for {move["number"]}'
        elif move["type"] == "guess":
            word = move["word"].strip().upper()
            # Find category
            game = state["game"]
            for r, row in enumerate(game["current"]["board"]):
                for c, cell in enumerate(row):
                    if cell["word"].upper() == word and not cell["revealed"]:
                        category = game["current"]["answer_key"][r][c]
                        return f'Guessed "{word}" → {category}'
            return f'Guessed "{word}"'
        elif move["type"] == "pass":
            return "Passed (ended guessing)"
        return str(move)

    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None:
        """Build inline codenames prompt based on role (spymaster vs guesser)."""
        game = state["game"]
        current = game["current"]
        match_id = state.get("lxm", {}).get("match_id", "")
        teams = current["teams"]

        role = self._get_agent_role(agent_id, teams)
        team = self._get_agent_team(agent_id, teams)
        if not role or not team:
            return None

        board = current["board"]
        answer_key = current["answer_key"]
        remaining = current["remaining"]

        # Build board display
        board_lines = []
        for r in range(self.GRID_SIZE):
            row_parts = []
            for c in range(self.GRID_SIZE):
                cell = board[r][c]
                word = cell["word"]
                if cell["revealed"]:
                    row_parts.append(f"[{word}={cell['revealed_as']}]")
                else:
                    if role == "spymaster":
                        cat = answer_key[r][c]
                        row_parts.append(f"{word}({cat})")
                    else:
                        row_parts.append(word)
            board_lines.append("  " + "  ".join(row_parts))

        board_str = "\n".join(board_lines)

        # Unrevealed words list (for guessers)
        unrevealed = []
        for r in range(self.GRID_SIZE):
            for c in range(self.GRID_SIZE):
                if not board[r][c]["revealed"]:
                    unrevealed.append(board[r][c]["word"])

        # Recent clue history
        clue_history = game.get("context", {}).get("clue_history", [])
        recent_clues = clue_history[-5:] if clue_history else []
        clue_lines = []
        for cl in recent_clues:
            clue_lines.append(f"  {cl['team']}: \"{cl['word']}\" for {cl['number']}")
        clue_str = "\n".join(clue_lines) if clue_lines else "  (none yet)"

        lines = [
            f"[LxM] Match: {match_id} | Agent: {agent_id} | Turn: {turn}",
            f"Codenames | Team: {team.upper()} | Role: {role.upper()}",
            f"Remaining: red={remaining['red']}, blue={remaining['blue']}",
            f"",
            f"Board:",
            board_str,
            f"",
            f"Recent clues:",
            clue_str,
            f"",
        ]

        if role == "spymaster":
            lines.extend([
                f"Your task: Give a one-word clue and a number (how many words it relates to).",
                f"The clue word must NOT be any unrevealed word on the board.",
                f"",
                f'Do NOT read any files. Write your move JSON to: moves/turn_{turn}_{agent_id}.json',
                f'Copy this exactly (replace WORD and NUMBER):',
                f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                f'"move":{{"type":"clue","word":"WORD","number":NUMBER}}}}',
            ])
        else:
            # Guesser
            current_clue = current.get("current_clue")
            guesses_left = current.get("guesses_remaining", 0)
            if current_clue:
                lines.append(f'Current clue: "{current_clue["word"]}" for {current_clue["number"]}')
            lines.append(f"Guesses remaining: {guesses_left}")
            lines.append(f"Unrevealed words: {', '.join(unrevealed)}")
            lines.extend([
                f"",
                f'Do NOT read any files. Write your move JSON to: moves/turn_{turn}_{agent_id}.json',
                f'To guess a word (replace WORD with an unrevealed word from the board):',
                f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                f'"move":{{"type":"guess","word":"WORD"}}}}',
                f'To pass (stop guessing):',
                f'  {{"protocol":"lxm-v0.2","match_id":"{match_id}","agent_id":"{agent_id}","turn":{turn},'
                f'"move":{{"type":"pass"}}}}',
            ])

        return "\n".join(lines)

    def get_evaluation_schema(self) -> dict:
        return {
            "description": "Evaluate Codenames performance by role",
            "fields": {
                "clue_quality": "1-5: How creative and effective were the spymaster's clues?",
                "clue_risk": "1-5: Did the spymaster take appropriate risks (multi-word clues vs safe single-word)?",
                "guess_accuracy": "1-5: Did the guesser correctly interpret the clues?",
                "team_synergy": "1-5: How well did the spymaster-guesser pair coordinate?",
                "assassin_awareness": "Did the spymaster avoid clues that might lead to the assassin?",
                "best_clue": "The single best clue of the game and why",
                "worst_clue": "The most misleading or ineffective clue and why",
                "overall_comment": "Free text assessment",
            },
        }

    def filter_state_for_agent(self, state: dict, agent_id: str) -> dict:
        """Mask answer key for guessers — they only see revealed categories."""
        game = state.get("game", {})
        current = game.get("current", {})
        teams = current.get("teams", {})

        role = self._get_agent_role(agent_id, teams)

        if role != "guesser":
            # Spymasters see everything
            return state

        filtered = copy.deepcopy(state)
        f_current = filtered["game"]["current"]
        board = f_current["board"]
        answer_key = f_current["answer_key"]

        # Mask unrevealed categories
        masked_key = []
        for r, row in enumerate(answer_key):
            masked_row = []
            for c, category in enumerate(row):
                if board[r][c]["revealed"]:
                    masked_row.append(category)
                else:
                    masked_row.append("unknown")
            masked_key.append(masked_row)
        f_current["answer_key"] = masked_key

        return filtered
