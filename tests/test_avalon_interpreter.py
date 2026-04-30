"""Tests for AvalonRuleInterpreter — narrative → move extraction."""

from lxm.interpreters.rules_avalon import AvalonRuleInterpreter


def make_context(phase, *, agent_id="hearth", quest_number=1,
                 quest_sizes=None, seat_order=None):
    return {
        "agent_id": agent_id,
        "game_state": {
            "current": {
                "phase": phase,
                "quest_number": quest_number,
                "quest_sizes": quest_sizes or [2, 3, 2, 3, 3],
                "seat_order": seat_order or ["hearth", "bot_b", "bot_c", "bot_d", "bot_e"],
            }
        },
    }


class TestVote:
    def setup_method(self):
        self.it = AvalonRuleInterpreter()

    def test_approve_simple(self):
        r = self.it.interpret("I vote approve.", make_context("vote"))
        assert r.move == {"type": "vote", "choice": "approve"}
        assert r.path == "rule"

    def test_reject_simple(self):
        r = self.it.interpret("Rejecting this team.", make_context("vote"))
        assert r.move == {"type": "vote", "choice": "reject"}

    def test_approve_with_reasoning(self):
        text = "Q1 with team [hearth, bot_b]. As Good, I'll approve — clean composition."
        r = self.it.interpret(text, make_context("vote"))
        assert r.move == {"type": "vote", "choice": "approve"}

    def test_negated_approve_flips(self):
        # "won't approve" → reject signal
        text = "I won't approve this. Rejecting."
        r = self.it.interpret(text, make_context("vote"))
        assert r.move == {"type": "vote", "choice": "reject"}

    def test_no_signal(self):
        r = self.it.interpret("Thinking about this carefully.", make_context("vote"))
        assert r is None

    def test_close_call_returns_none(self):
        # Both signals present, low margin → defer to AI fallback.
        text = "I could approve or reject. Approve makes sense; rejecting also valid."
        r = self.it.interpret(text, make_context("vote"))
        assert r is None


class TestQuestAction:
    def setup_method(self):
        self.it = AvalonRuleInterpreter()

    def test_success(self):
        r = self.it.interpret("Playing success on this quest.",
                              make_context("quest"))
        assert r.move == {"type": "quest_action", "choice": "success"}

    def test_sabotage(self):
        r = self.it.interpret("I'll sabotage this run.",
                              make_context("quest"))
        assert r.move == {"type": "quest_action", "choice": "sabotage"}

    def test_play_clean(self):
        r = self.it.interpret("As Good I play clean.", make_context("quest"))
        assert r.move == {"type": "quest_action", "choice": "success"}

    def test_drop_a_fail(self):
        r = self.it.interpret("Time to drop a fail and shift the count.",
                              make_context("quest"))
        assert r.move == {"type": "quest_action", "choice": "sabotage"}


class TestProposal:
    def setup_method(self):
        self.it = AvalonRuleInterpreter()

    def test_named_team(self):
        text = "I propose hearth and bot_b for quest 1."
        r = self.it.interpret(text, make_context("propose", quest_number=1))
        assert r.move == {"type": "proposal", "team": ["hearth", "bot_b"]}

    def test_self_implicit(self):
        # Leader 'hearth' says "self plus bot_c" — interpreter prepends leader.
        text = "Proposing self plus bot_c."
        r = self.it.interpret(text, make_context("propose", agent_id="hearth"))
        assert r.move["team"] == ["hearth", "bot_c"]

    def test_team_size_three(self):
        text = "Team: bot_b, bot_c, hearth for Q2."
        r = self.it.interpret(text, make_context("propose", quest_number=2))
        # quest_sizes[1] = 3 → all three names used
        assert sorted(r.move["team"]) == sorted(["hearth", "bot_b", "bot_c"])

    def test_extra_names_truncated(self):
        text = "Pick hearth, bot_b, bot_c, bot_d — actually let me think."
        # team_size=2 for Q1 → first two in text order
        r = self.it.interpret(text, make_context("propose", quest_number=1))
        assert len(r.move["team"]) == 2
        assert r.move["team"] == ["hearth", "bot_b"]

    def test_too_few_names_returns_none(self):
        text = "I'm leaning toward bot_b for the team, but unsure."
        # only 1 named, team_size=2 → ambiguous
        r = self.it.interpret(text, make_context("propose", quest_number=1))
        assert r is None


class TestPhaseGating:
    def setup_method(self):
        self.it = AvalonRuleInterpreter()

    def test_no_phase_returns_none(self):
        r = self.it.interpret("approve approve approve",
                              {"agent_id": "hearth", "game_state": {}})
        assert r is None

    def test_unknown_phase_returns_none(self):
        r = self.it.interpret("approve",
                              make_context("game_over"))
        assert r is None

    def test_empty_response_returns_none(self):
        r = self.it.interpret("", make_context("vote"))
        assert r is None

    def test_vote_keywords_during_quest_phase_route_to_quest(self):
        # In quest phase, a response that says "approve" without success/sabotage
        # cues should NOT be misclassified — quest extractor returns None,
        # not the wrong move shape.
        r = self.it.interpret("I approve.", make_context("quest"))
        assert r is None


class TestRegistry:
    def test_avalon_interpreter_registered(self):
        from lxm.interpreters.registry import get_interpreter
        it = get_interpreter("avalon")
        assert it is not None
        assert it.game == "avalon"
