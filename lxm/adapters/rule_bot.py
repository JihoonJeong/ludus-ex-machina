"""Rule-based bot adapter — no LLM calls, pure code decisions.

Supports multiple games with configurable difficulty.
Model parameter controls difficulty: "easy", "medium", "hard".

Usage:
    register_adapter("rule_bot", RuleBotAdapter)

    # In match config:
    AgentConfig(agent_id="bot", adapter="rule_bot", model="medium")
"""

from __future__ import annotations

import json
import re
from typing import Optional

from lxm.adapters.base import AgentAdapter


class RuleBotAdapter(AgentAdapter):
    """Rule-based bot. No LLM call — pure algorithmic decisions."""

    def __init__(self, agent_config: dict):
        super().__init__(agent_config)
        self._difficulty = agent_config.get("model", "medium")  # easy/medium/hard
        self._strategies = {
            "poker": PokerStrategy(self._difficulty),
            "chess": ChessStrategy(self._difficulty),
            "trustgame": TrustGameStrategy(self._difficulty),
            "tictactoe": TicTacToeStrategy(self._difficulty),
        }

    def invoke(self, match_dir: str, prompt: str) -> dict:
        """Parse game state from prompt, decide move, return as envelope JSON."""
        game = self._detect_game(prompt)
        strategy = self._strategies.get(game)
        if not strategy:
            return self._error(f"No rule bot strategy for game: {game}")

        try:
            move = strategy.decide(prompt, self._agent_id)
            envelope = {
                "protocol": "lxm-v0.2",
                "match_id": "",
                "agent_id": self._agent_id,
                "turn": 0,
                "move": move,
                "meta": {"reasoning": f"Rule bot ({self._difficulty}): {strategy.last_reason}"},
            }
            return {
                "stdout": json.dumps(envelope),
                "stderr": "",
                "exit_code": 0,
                "timed_out": False,
            }
        except Exception as e:
            return self._error(str(e))

    def _detect_game(self, prompt: str) -> str:
        if "poker_action" in prompt or "hole_cards" in prompt or "community_cards" in prompt:
            return "poker"
        if "chess_move" in prompt or "FEN" in prompt:
            return "chess"
        if "cooperate" in prompt and "defect" in prompt:
            return "trustgame"
        if "tictactoe" in prompt or "X |" in prompt or "O |" in prompt:
            return "tictactoe"
        return "unknown"

    def _error(self, msg: str) -> dict:
        return {"stdout": "", "stderr": msg, "exit_code": -1, "timed_out": False}


# ── Poker Strategy ──

# Pre-flop hand rankings (simplified Chen formula inspired)
# Higher = better. Top ~15% of hands.
PREMIUM_HANDS = {
    "AA", "KK", "QQ", "JJ", "TT", "AKs", "AQs", "AJs", "KQs", "AKo",
}
GOOD_HANDS = {
    "99", "88", "77", "ATs", "KJs", "QJs", "JTs", "AQo", "KQo",
    "A9s", "K9s", "Q9s", "T9s", "98s", "87s",
}
PLAYABLE_HANDS = {
    "66", "55", "44", "33", "22", "A8s", "A7s", "A6s", "A5s", "A4s",
    "A3s", "A2s", "K8s", "Q8s", "J9s", "T8s", "97s", "86s", "76s",
    "65s", "54s", "AJo", "ATo", "KJo", "QJo", "JTo",
}


def classify_hand(cards: list[str]) -> str:
    """Classify a 2-card hand into premium/good/playable/trash."""
    if len(cards) != 2:
        return "trash"

    def parse(card):
        rank = card[0].upper() if len(card) >= 2 else "?"
        suit = card[-1].lower() if len(card) >= 2 else "?"
        return rank, suit

    r1, s1 = parse(cards[0])
    r2, s2 = parse(cards[1])
    suited = "s" if s1 == s2 else "o"

    # Normalize: higher rank first
    rank_order = "AKQJT98765432"
    if rank_order.index(r1) > rank_order.index(r2):
        r1, r2 = r2, r1

    if r1 == r2:
        hand_str = f"{r1}{r2}"
    else:
        hand_str = f"{r1}{r2}{suited}"

    if hand_str in PREMIUM_HANDS:
        return "premium"
    elif hand_str in GOOD_HANDS:
        return "good"
    elif hand_str in PLAYABLE_HANDS:
        return "playable"
    return "trash"


class PokerStrategy:
    """Probability-based poker bot."""

    def __init__(self, difficulty: str = "medium"):
        self._difficulty = difficulty
        self.last_reason = ""

    def decide(self, prompt: str, agent_id: str) -> dict:
        state = self._parse_state(prompt)
        hole_cards = state.get("hole_cards", [])
        community = state.get("community_cards", [])
        pot = state.get("pot", 0)
        to_call = state.get("to_call", 0)
        my_chips = state.get("my_chips", 1000)

        hand_class = classify_hand(hole_cards) if hole_cards else "trash"

        # Pre-flop (no community cards)
        if not community:
            return self._preflop_decision(hand_class, to_call, my_chips)

        # Post-flop
        return self._postflop_decision(hand_class, community, hole_cards, pot, to_call, my_chips)

    def _preflop_decision(self, hand_class, to_call, my_chips):
        if self._difficulty == "easy":
            # Loose-passive: play most hands, rarely raise
            if hand_class in ("premium", "good"):
                self.last_reason = f"Easy: {hand_class} hand, raise"
                return {"type": "poker_action", "action": "raise", "amount": min(to_call * 3, my_chips)}
            elif hand_class == "playable":
                self.last_reason = f"Easy: {hand_class} hand, call"
                return {"type": "poker_action", "action": "call"}
            else:
                if to_call == 0:
                    self.last_reason = "Easy: trash but free, check"
                    return {"type": "poker_action", "action": "check"}
                self.last_reason = "Easy: trash, call anyway (loose)"
                return {"type": "poker_action", "action": "call"}

        elif self._difficulty == "hard":
            # Tight-aggressive: premium/good only, always raise
            if hand_class == "premium":
                self.last_reason = f"Hard: {hand_class}, raise big"
                return {"type": "poker_action", "action": "raise", "amount": min(to_call * 4, my_chips)}
            elif hand_class == "good":
                self.last_reason = f"Hard: {hand_class}, raise"
                return {"type": "poker_action", "action": "raise", "amount": min(to_call * 3, my_chips)}
            else:
                if to_call == 0:
                    self.last_reason = f"Hard: {hand_class} but free, check"
                    return {"type": "poker_action", "action": "check"}
                self.last_reason = f"Hard: {hand_class}, fold"
                return {"type": "poker_action", "action": "fold"}

        else:  # medium
            if hand_class == "premium":
                self.last_reason = f"Medium: {hand_class}, raise"
                return {"type": "poker_action", "action": "raise", "amount": min(to_call * 3, my_chips)}
            elif hand_class == "good":
                self.last_reason = f"Medium: {hand_class}, call"
                return {"type": "poker_action", "action": "call"}
            elif hand_class == "playable":
                if to_call == 0:
                    self.last_reason = f"Medium: {hand_class} free, check"
                    return {"type": "poker_action", "action": "check"}
                self.last_reason = f"Medium: {hand_class}, fold"
                return {"type": "poker_action", "action": "fold"}
            else:
                if to_call == 0:
                    self.last_reason = "Medium: trash free, check"
                    return {"type": "poker_action", "action": "check"}
                self.last_reason = "Medium: trash, fold"
                return {"type": "poker_action", "action": "fold"}

    def _postflop_decision(self, hand_class, community, hole_cards, pot, to_call, my_chips):
        # Simplified: if we entered the hand, play based on hand class + pot odds
        pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 0

        if self._difficulty == "hard":
            if hand_class in ("premium", "good"):
                self.last_reason = f"Hard post-flop: {hand_class}, bet"
                return {"type": "poker_action", "action": "raise", "amount": min(pot // 2, my_chips)}
            elif to_call == 0:
                self.last_reason = "Hard post-flop: check"
                return {"type": "poker_action", "action": "check"}
            elif pot_odds < 0.3:
                self.last_reason = f"Hard post-flop: good pot odds ({pot_odds:.0%}), call"
                return {"type": "poker_action", "action": "call"}
            else:
                self.last_reason = f"Hard post-flop: bad pot odds ({pot_odds:.0%}), fold"
                return {"type": "poker_action", "action": "fold"}

        elif self._difficulty == "easy":
            if to_call == 0:
                self.last_reason = "Easy post-flop: check"
                return {"type": "poker_action", "action": "check"}
            self.last_reason = "Easy post-flop: call (passive)"
            return {"type": "poker_action", "action": "call"}

        else:  # medium
            if hand_class in ("premium", "good"):
                self.last_reason = f"Medium post-flop: {hand_class}, raise"
                return {"type": "poker_action", "action": "raise", "amount": min(pot // 2, my_chips)}
            elif to_call == 0:
                self.last_reason = "Medium post-flop: check"
                return {"type": "poker_action", "action": "check"}
            elif pot_odds < 0.25:
                self.last_reason = f"Medium post-flop: ok pot odds ({pot_odds:.0%}), call"
                return {"type": "poker_action", "action": "call"}
            else:
                self.last_reason = f"Medium post-flop: fold"
                return {"type": "poker_action", "action": "fold"}

    def _parse_state(self, prompt: str) -> dict:
        """Extract poker state from inline prompt text."""
        state = {}

        # Hole cards
        hole_match = re.search(r'"hole_cards":\s*\[([^\]]+)\]', prompt)
        if hole_match:
            cards = re.findall(r'"(\w+)"', hole_match.group(1))
            state["hole_cards"] = cards

        # Community cards
        comm_match = re.search(r'"community_cards":\s*\[([^\]]*)\]', prompt)
        if comm_match:
            cards = re.findall(r'"(\w+)"', comm_match.group(1))
            state["community_cards"] = cards

        # Pot
        pot_match = re.search(r'"pot":\s*(\d+)', prompt)
        if pot_match:
            state["pot"] = int(pot_match.group(1))

        # Game-level current bet
        game_bet = 0
        game_bet_match = re.search(r'"current_bet":\s*(\d+)', prompt)
        if game_bet_match:
            game_bet = int(game_bet_match.group(1))

        # Find my player data to calculate to_call
        # Look for my agent_id's section in the prompt
        my_bet = 0
        my_chips = 1000
        # Try to find player-specific data near my agent_id
        agent_section = re.search(
            rf'"{re.escape(self._agent_id)}":\s*\{{([^}}]+)\}}', prompt
        )
        if agent_section:
            section = agent_section.group(1)
            bet_match = re.search(r'"current_bet":\s*(\d+)', section)
            if bet_match:
                my_bet = int(bet_match.group(1))
            chips_match = re.search(r'"chips":\s*(\d+)', section)
            if chips_match:
                my_chips = int(chips_match.group(1))
        else:
            chips_match = re.search(r'"chips":\s*(\d+)', prompt)
            if chips_match:
                my_chips = int(chips_match.group(1))

        state["to_call"] = max(0, game_bet - my_bet)
        state["my_chips"] = my_chips
        state["pot"] = state.get("pot", 0)

        return state


# ── Chess Strategy ──

class ChessStrategy:
    """Stockfish wrapper for chess. Falls back to random legal move."""

    def __init__(self, difficulty: str = "medium"):
        self._difficulty = difficulty
        self._depth = {"easy": 1, "medium": 5, "hard": 10}.get(difficulty, 5)
        self._engine = None
        self.last_reason = ""

    def decide(self, prompt: str, agent_id: str) -> dict:
        fen = self._extract_fen(prompt)
        if not fen:
            self.last_reason = "No FEN found, cannot move"
            return {"type": "chess_move", "notation": "e2e4"}  # fallback

        try:
            import chess
            board = chess.Board(fen)
            move = self._get_move(board)
            san = board.san(move)
            self.last_reason = f"Stockfish depth {self._depth}: {san}"
            return {"type": "chess_move", "notation": san}
        except Exception as e:
            self.last_reason = f"Chess error: {e}"
            return {"type": "chess_move", "notation": "e2e4"}

    def _get_move(self, board):
        import chess
        # Try Stockfish first
        try:
            if self._engine is None:
                import chess.engine
                self._engine = chess.engine.SimpleEngine.popen_uci("stockfish")
            result = self._engine.play(board, chess.engine.Limit(depth=self._depth))
            return result.move
        except Exception:
            pass

        # Fallback: random legal move
        import random
        legal = list(board.legal_moves)
        return random.choice(legal) if legal else chess.Move.null()

    def _extract_fen(self, prompt: str) -> Optional[str]:
        match = re.search(r'"fen":\s*"([^"]+)"', prompt)
        if match:
            return match.group(1)
        # Try bare FEN pattern
        match = re.search(r'([rnbqkpRNBQKP1-8/]+ [wb] [KQkq-]+ [a-h1-8-]+ \d+ \d+)', prompt)
        if match:
            return match.group(1)
        return None

    def __del__(self):
        if self._engine:
            try:
                self._engine.quit()
            except Exception:
                pass


# ── Trust Game Strategy ──

class TrustGameStrategy:
    """Classic strategies for iterated trust/prisoner's dilemma."""

    STRATEGIES = {
        "easy": "always_cooperate",
        "medium": "tit_for_tat",
        "hard": "suspicious_tft",
    }

    def __init__(self, difficulty: str = "medium"):
        self._strategy = self.STRATEGIES.get(difficulty, "tit_for_tat")
        self._history: list[str] = []
        self.last_reason = ""

    def decide(self, prompt: str, agent_id: str) -> dict:
        opponent_last = self._extract_opponent_last(prompt, agent_id)

        if self._strategy == "always_cooperate":
            action = "cooperate"
            self.last_reason = "Always cooperate"
        elif self._strategy == "always_defect":
            action = "defect"
            self.last_reason = "Always defect"
        elif self._strategy == "tit_for_tat":
            if opponent_last is None:
                action = "cooperate"  # Start cooperative
                self.last_reason = "TFT: first round, cooperate"
            else:
                action = opponent_last
                self.last_reason = f"TFT: mirror opponent's {opponent_last}"
        elif self._strategy == "suspicious_tft":
            if opponent_last is None:
                action = "defect"  # Start suspicious
                self.last_reason = "Suspicious TFT: first round, defect"
            else:
                action = opponent_last
                self.last_reason = f"Suspicious TFT: mirror {opponent_last}"
        else:
            action = "cooperate"
            self.last_reason = "Default: cooperate"

        return {"type": "trust_action", "action": action}

    def _extract_opponent_last(self, prompt: str, agent_id: str) -> Optional[str]:
        # Look for history in prompt
        coop_match = re.findall(r'(\w+)\s*(?:chose|played|:)\s*(cooperate|defect)', prompt, re.IGNORECASE)
        for name, action in reversed(coop_match):
            if name != agent_id:
                return action.lower()
        return None


# ── Tic-Tac-Toe Strategy ──

class TicTacToeStrategy:
    """Minimax for tic-tac-toe (always optimal at hard)."""

    def __init__(self, difficulty: str = "medium"):
        self._difficulty = difficulty
        self.last_reason = ""

    def decide(self, prompt: str, agent_id: str) -> dict:
        board = self._extract_board(prompt)

        if self._difficulty == "easy":
            move = self._first_empty(board)
            self.last_reason = f"Easy: first empty cell ({move})"
        elif self._difficulty == "hard":
            move = self._minimax_move(board)
            self.last_reason = f"Hard: minimax ({move})"
        else:
            # Medium: play center/corner first, then minimax
            move = self._heuristic_move(board)
            self.last_reason = f"Medium: heuristic ({move})"

        return {"type": "ttt_move", "position": move}

    def _extract_board(self, prompt: str) -> list:
        # Try to find board state as list
        match = re.search(r'"board":\s*(\[[^\]]*\])', prompt)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return [""] * 9

    def _first_empty(self, board: list) -> int:
        for i, cell in enumerate(board):
            if not cell or cell == " ":
                return i
        return 0

    def _heuristic_move(self, board: list) -> int:
        # Center
        if not board[4] or board[4] == " ":
            return 4
        # Corners
        for i in [0, 2, 6, 8]:
            if not board[i] or board[i] == " ":
                return i
        return self._first_empty(board)

    def _minimax_move(self, board: list) -> int:
        # Determine which piece we are
        x_count = sum(1 for c in board if c == "X")
        o_count = sum(1 for c in board if c == "O")
        is_x = x_count <= o_count

        best_score = -float("inf")
        best_move = self._first_empty(board)

        for i in range(9):
            if board[i] and board[i] != " ":
                continue
            board[i] = "X" if is_x else "O"
            score = self._minimax(board, False, is_x)
            board[i] = ""
            if score > best_score:
                best_score = score
                best_move = i

        return best_move

    def _minimax(self, board, is_maximizing, is_x):
        winner = self._check_winner(board)
        me = "X" if is_x else "O"
        opp = "O" if is_x else "X"
        if winner == me:
            return 1
        if winner == opp:
            return -1
        if all(c and c != " " for c in board):
            return 0

        if is_maximizing:
            best = -float("inf")
            for i in range(9):
                if board[i] and board[i] != " ":
                    continue
                board[i] = me
                best = max(best, self._minimax(board, False, is_x))
                board[i] = ""
            return best
        else:
            best = float("inf")
            for i in range(9):
                if board[i] and board[i] != " ":
                    continue
                board[i] = opp
                best = min(best, self._minimax(board, True, is_x))
                board[i] = ""
            return best

    def _check_winner(self, board):
        lines = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6),
        ]
        for a, b, c in lines:
            if board[a] and board[a] != " " and board[a] == board[b] == board[c]:
                return board[a]
        return None
