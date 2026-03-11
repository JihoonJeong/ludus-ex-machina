# LxM Soft Shell Spec v0.1

## Purpose

Add a **learning layer** to LxM agents. Currently agents have a Hard Shell (static strategic identity) but no mechanism to improve across games. This spec introduces the **Soft Shell** — accumulated experience, coaching notes, and in-context examples that make agents play better over time.

**Hand this to Cody and say "build this."**

**Prerequisites:**
- LxM core system working (orchestrator, adapter, evaluation)
- At least one game with post-game evaluation (chess or tic-tac-toe)

---

## 1. Four Shell Model — Where Soft Shell Fits

```
┌─────────────────────────────┐
│  Hardware Shell (match env)  │  ← Files, folders, turn timeout
├─────────────────────────────┤
│  Hard Shell (shell.md)       │  ← Static identity: "I am aggressive"
├─────────────────────────────┤
│  Soft Shell (experience/)    │  ← THIS SPEC: learned lessons, coaching, ICL
├─────────────────────────────┤
│  Core (model weights)        │  ← Claude haiku/sonnet/opus — immutable
└─────────────────────────────┘
```

**Hard Shell** = who you are (doesn't change between games)
**Soft Shell** = what you've learned (grows across games)

The Core is frozen (model weights). The Soft Shell is the only layer where an agent can meaningfully improve without changing the model itself.

---

## 2. Agent Folder Structure

```
agents/claude-alpha/
├── shell.md                    ← Hard Shell (existing, unchanged)
├── soft_shell.md               ← Soft Shell index — always loaded
├── experience/
│   ├── lessons.md              ← Distilled lessons from past games
│   ├── openings.md             ← Game-specific: chess opening repertoire
│   ├── patterns.md             ← Recognized patterns and responses
│   └── mistakes.md             ← Common mistakes to avoid
├── coaching/
│   ├── coach_notes.md          ← Human/partner strategic advice
│   └── review_game_001.md      ← Human review of specific game
└── game_history/
    ├── game_001_summary.md     ← Auto-generated post-game summary
    └── game_002_summary.md
```

### Key Principle: Context Budget

The agent reads ALL of this on every turn. Total Soft Shell content must stay within a **context budget** — suggested max **4,000 tokens** (~3,000 words). The adapter enforces this by truncation if needed.

This means:
- `soft_shell.md`: brief index + top priorities (500 tokens max)
- Individual files: concise, compressed wisdom — not raw game logs
- Old/outdated lessons get pruned or merged

---

## 3. Soft Shell Content Types

### 3.1 Lessons (Auto-Generated)

Extracted from post-game evaluations. Distilled into actionable rules.

```markdown
# Lessons Learned

## Chess
- In the opening, develop knights before bishops (learned game_002: lost tempo with early Bc4)
- Don't trade queens when behind in material (game_005: traded into losing endgame)
- When opponent castles kingside, consider pawn storm only if center is closed (game_007)

## General
- Read the board state carefully before each move — I've submitted illegal moves 3 times due to misreading FEN
- When unsure, prefer solid/safe moves over speculative attacks
```

Format: **one-line rules**, each tied to a source game. Easy for the model to scan and apply.

### 3.2 ICL Examples (Curated)

In-context learning examples: "given this position, here's the right move and why."

```markdown
# Key Positions & Responses

## Tactic: Back-rank mate threat
Position: White Rook on a1, Black King on g8, Black pawns on f7/g7/h7
Best move: Ra8+ (back-rank mate if no escape)
Why: Pawns block the king. The rook delivers mate on the 8th rank.

## Opening: Sicilian Defense response
After 1.e4 c5: Play 2.Nf3 followed by 3.d4 (Open Sicilian)
Why: Most principled response. Leads to sharp play where tactical skill matters.
```

### 3.3 Coaching Notes (Human-Written)

A human partner reviews games and writes strategic advice. This is the **human-in-the-loop** path to improving an agent.

```markdown
# Coach Notes for claude-alpha

## Style Assessment
You play too aggressively in the middlegame. You sacrifice material for attacks
that don't work against careful defenders. Recommendation:
- Only sacrifice if you can calculate a forced sequence to checkmate or material recovery
- In equal positions, improve piece activity rather than launching premature attacks

## Opening Repertoire
As White: 1.e4 — Stick with Italian Game (Bc4). You play it well.
As Black: Against 1.e4, play Sicilian (c5). Against 1.d4, play King's Indian.

## Endgame Weakness
You consistently fail to activate your king in endgames. ALWAYS bring the king
to the center once queens are off the board.
```

### 3.4 Game Summaries (Auto-Generated)

Compressed post-game records. Not full logs — just the key takeaways.

```markdown
# Game 001 Summary
Opponent: claude-beta | Game: chess | Result: Lost (checkmate, move 34)
Key moments:
- Move 12: Missed fork with Ne5 (tactical_accuracy: 2/5)
- Move 24: Traded queens when down a pawn — accelerated loss
Lesson extracted: → Don't trade queens when behind in material
```

---

## 4. Adapter Changes

### 4.1 Loading Soft Shell

The adapter reads `soft_shell.md` + referenced files and includes them in the prompt.

```python
# In ClaudeCodeAdapter.__init__
self._soft_shell_content: str | None = None
soft_shell_path = agent_dir / "soft_shell.md"
if soft_shell_path.exists():
    self._soft_shell_content = self._load_soft_shell(agent_dir)

def _load_soft_shell(self, agent_dir: Path) -> str:
    """Load soft shell content within context budget."""
    parts = []

    # Always load soft_shell.md (index)
    index = (agent_dir / "soft_shell.md").read_text()
    parts.append(index)

    # Load experience files
    exp_dir = agent_dir / "experience"
    if exp_dir.exists():
        for f in sorted(exp_dir.glob("*.md")):
            parts.append(f.read_text())

    # Load coaching notes
    coach_dir = agent_dir / "coaching"
    if coach_dir.exists():
        for f in sorted(coach_dir.glob("*.md")):
            parts.append(f.read_text())

    # Enforce context budget (~4000 tokens ≈ 16000 chars)
    combined = "\n\n".join(parts)
    MAX_CHARS = 16000
    if len(combined) > MAX_CHARS:
        combined = combined[:MAX_CHARS] + "\n\n[... Soft Shell truncated due to context budget ...]"

    return combined
```

### 4.2 Prompt Assembly

```python
def _build_full_prompt(self, prompt: str) -> str:
    sections = []

    if self._shell_content:
        sections.append(
            f"[HARD SHELL - Your strategic identity]\n"
            f"{self._shell_content}\n"
            f"[END HARD SHELL]"
        )

    if self._soft_shell_content:
        sections.append(
            f"[SOFT SHELL - Your accumulated experience]\n"
            f"{self._soft_shell_content}\n"
            f"[END SOFT SHELL]"
        )

    sections.append(prompt)
    return "\n\n".join(sections)
```

---

## 5. Learning Pipeline

How the Soft Shell grows over time.

### 5.0 Validation First — Manual Experiment

**Before building any automation, validate the concept manually.** Zero code changes required.

```
Phase 1: Baseline
  → Chess 10 games, no soft shell (current setup)
  → Record: win rate, retry rate, eval scores, average game length

Phase 2: Manual Soft Shell Injection
  → Send Phase 1 game logs + evals to Opus (higher-tier model)
  → Opus generates 3-5 distilled lessons
  → Paste lessons into shell.md (or a new soft_shell.md read manually)

Phase 3: Comparison
  → Same conditions, 10 more games with the injected lessons
  → Compare all metrics against Phase 1 baseline

Decision gate:
  → Positive signal → proceed with system implementation
  → Negative signal → context budget may be better spent on reasoning
    than on experience. Investigate before building.
```

This experiment costs nothing to run and answers the fundamental question: **does accumulated experience actually help?**

### 5.1 Automatic: Post-Game Extraction (Higher-Tier Review)

**Critical design rule: the reviewing model must be higher-tier than the playing model.** A model reviewing its own play risks self-rationalization — bad moves get justified rather than corrected.

```
Game ends → Evaluation (existing) → Higher-Tier Review (new) → Update soft_shell
```

Review model selection:
- Haiku plays → **Sonnet or Opus reviews**
- Sonnet plays → **Opus reviews**
- Opus plays → **Opus reviews** (same tier acceptable at the top) + human spot-check

Data sources for review (no additional invocations needed for these):
- `evals/self_{agent}.json` — agent's own assessment (already generated)
- `evals/cross_{agent}_on_{target}.json` — opponent's assessment (already generated)
- `log.json` — full move history

Lesson extraction prompt (sent to **review model**, not play model):
```
You are reviewing a chess game played by {agent_id} (model: {play_model}).
Your job is external analysis — not the player's self-assessment.

Game log: {log_summary}
Player's self-eval: {self_eval}
Opponent's cross-eval: {cross_eval}

Extract 1-3 concise lessons. For each:
- One sentence actionable rule
- The specific move/position that demonstrates it
- Why the player's own assessment may have missed this

Reject self-serving rationalizations. Focus on actual mistakes and missed opportunities.
Do NOT include generic advice like "play better" or "think more carefully."
```

The extracted lessons get **appended** to `agents/{id}/experience/lessons.md`.

### 5.2 Automatic: Game Summary Generation

After each game, generate a compressed summary for `game_history/`.

```
Game ends → Generate summary → Save to game_history/game_{id}_summary.md
```

Keep only the **last 10 game summaries** to prevent unbounded growth.

### 5.3 Manual: Human Coaching

A human reviews match replays (via the viewer) and writes notes:

```bash
# Human writes/edits coaching notes directly
vim agents/claude-alpha/coaching/coach_notes.md

# Or uses a helper script
python scripts/coach.py --agent claude-alpha --match chess_test_001
# Opens an interactive session where the human can annotate moves
# and the system formats it into coaching notes
```

Note: Human coaching doesn't require chess expertise. Common-sense observations ("you keep trading pieces when you're losing material") are valuable. The model translates high-level guidance into specific play improvements.

### 5.4 Manual: ICL Curation

A human (or a more capable model like Opus) reviews games and creates ICL examples:

```bash
python scripts/curate_icl.py --agent claude-alpha --game chess --model opus
# Analyzes game history, identifies key decision points,
# generates position→move examples for the agent's experience/patterns.md
```

---

## 6. Context Budget Manager

Soft Shell content can grow unbounded. A budget manager keeps it in check.

### Rules:
1. **Total budget**: 4,000 tokens (configurable per agent)
2. **Priority order**: coaching > lessons > patterns > game_summaries
3. **Aging**: Lessons not reinforced in 10+ games get demoted/pruned
4. **Deduplication**: If two lessons say the same thing, merge them
5. **Game-specific filtering**: Only include lessons relevant to the current game type

### Implementation:

```python
class SoftShellManager:
    """Manages soft shell content within context budget."""

    def __init__(self, agent_dir: Path, budget_tokens: int = 4000):
        self.agent_dir = agent_dir
        self.budget = budget_tokens

    def load_for_game(self, game_name: str) -> str:
        """Load soft shell content filtered for a specific game."""
        # 1. Load all content
        # 2. Filter by game relevance
        # 3. Sort by priority (coaching > lessons > patterns > history)
        # 4. Truncate to budget
        # 5. Return combined string
        ...

    def add_lesson(self, lesson: str, game_id: str, game_name: str):
        """Append a lesson from a completed game."""
        ...

    def prune(self):
        """Remove outdated or redundant lessons."""
        ...
```

---

## 7. CLI Tools

### 7.1 `scripts/coach.py` — Interactive Coaching

```bash
python scripts/coach.py --agent claude-alpha --match chess_test_001
```

Loads the match replay, shows each move, lets the human annotate. Saves to `coaching/`.

### 7.2 `scripts/soft_shell_status.py` — View Agent's Knowledge

```bash
python scripts/soft_shell_status.py --agent claude-alpha

Agent: claude-alpha
Hard Shell: shell.md (420 chars)
Soft Shell: 2,847 / 4,000 tokens
  ├── lessons.md: 12 lessons (1,200 tokens)
  ├── openings.md: 3 entries (400 tokens)
  ├── patterns.md: 5 patterns (600 tokens)
  ├── mistakes.md: 4 entries (247 tokens)
  └── coaching/coach_notes.md: 400 tokens
Game History: 3 summaries
```

### 7.3 `scripts/curate_icl.py` — Generate ICL Examples

```bash
python scripts/curate_icl.py --agent claude-alpha --game chess --model opus
```

Uses a strong model to analyze past games and generate high-quality ICL examples.

---

## 8. Implementation Order

Experiment first, build second. No code until the concept is validated.

```
Phase 0: Baseline data (NO CODE CHANGES)
        → Chess cross-model tournament: Haiku vs Haiku, Sonnet vs Sonnet
        → 10 games per configuration
        → Record: win rate, retry rate, eval scores, game length
        → This data is valuable regardless of Soft Shell outcome

Phase 1: Manual Soft Shell experiment (NO CODE CHANGES)
        → Take Phase 0 game logs
        → Send to Opus for lesson extraction (manual CLI invocation)
        → Paste 3-5 lessons into ONE agent's shell.md only (e.g., claude-alpha)
        → Leave the other agent (claude-beta) unchanged as control
        → Run 10 more games, same conditions
        → Compare: does the Soft Shell agent's win rate increase vs baseline?
        → GO/NO-GO decision based on win rate delta

    ════════════════════════════════════════════════
    DECISION GATE: Only proceed if Phase 1 shows positive signal.
    If negative, investigate why before building automation.
    ════════════════════════════════════════════════

Phase 2: Adapter changes (first code)
        → Load soft_shell.md + experience/ + coaching/
        → Context budget enforcement (char truncation for v1)
        → Update prompt assembly

Phase 3: Auto game summary generation
        → Compressed post-game summary → game_history/
        → Last 10 summaries retained

Phase 4: Auto lesson extraction (higher-tier review)
        → Review model selection (play model < review model)
        → Cross-eval data integration (already in evals/, $0 cost)
        → Anti-rationalization prompt design
        → Human spot-check mechanism for Opus-plays-Opus case

Phase 5: CLI tools + budget manager
        → soft_shell_status.py (view agent knowledge)
        → coach.py (interactive coaching)
        → Token-aware budget, priority loading, pruning

Phase 6: ICL curation
        → curate_icl.py script
        → Pattern extraction from game history
```

---

## 9. Measurement: Does It Work?

The whole point is measurable improvement. Track:

| Metric | How | Expected Impact |
|--------|-----|-----------------|
| Win rate | Games won / total | Should increase over time |
| Retry rate | Invalid moves / total moves | Should decrease (fewer illegal moves) |
| Eval scores | Self/cross eval averages | Should trend upward |
| Time to result | Average turns to win | Should decrease (more efficient play) |

**Key experiment**: Run 10 games without soft shell, then 10 games with. Compare metrics. This is the core validation of whether the learning layer adds value.

### 9.1 Model Medicine Questions

These are the deeper research questions that Soft Shell enables. Not all need answers immediately, but the system should be designed to collect the data.

**Core × Shell interaction**: Give the **same** Soft Shell content to Haiku, Sonnet, and Opus. Who benefits most? Hypothesis: mid-tier models (Sonnet) benefit most — Haiku may lack the reasoning to apply lessons, Opus may already know them implicitly. If true, Soft Shell is a "great equalizer" for mid-tier models.

**Shell saturation point**: As experience accumulates (5, 10, 20, 50 lessons), at what point does adding more stop helping? Does this threshold differ by Core? Plot: lessons_count × win_rate, faceted by model. If there's a plateau, that's the optimal Soft Shell size — anything beyond wastes context budget.

**Transfer learning**: Do lessons learned in Chess improve performance in a different game? Test: train Soft Shell on Chess, then play a new game (e.g., Connect Four) without clearing the shell. If general strategic lessons ("don't trade when behind", "control the center") transfer, that's evidence of meta-learning. If game-specific lessons ("develop knights before bishops") hurt performance in other games, that argues for game-specific filtering (Section 6, Rule 5).

**Context budget vs reasoning space**: Is 4,000 tokens of experience better than 4,000 tokens of "think step by step" reasoning space? Test: compare a 4K soft shell agent vs an agent with an extended reasoning prompt and no soft shell. This answers whether experience or deliberation is more valuable — and whether the answer changes by Core tier.

---

## 10. Known Considerations

**Self-review bias**: A model reviewing its own play tends toward self-rationalization — bad moves get justified as "interesting sacrifices" or "creative play." This is why Section 5.1 mandates higher-tier review. The same bias applies to self-evaluation (evals/self_*.json) — cross-evaluation from opponents is often more honest. Weight cross-eval data higher when extracting lessons.

**Context window trade-off**: More soft shell = less room for the model to "think." If an agent is loading 4,000 tokens of lessons, that's 4,000 tokens less for reasoning about the current position. Monitor for cases where heavy soft shells actually hurt performance. (See Section 9.1, "Context budget vs reasoning space.")

**Overfitting to specific opponents**: If claude-alpha only plays claude-beta, lessons may overfit to beta's style. Consider rotating opponents or noting which lessons are opponent-specific vs general.

**Stale lessons**: A lesson from game 1 may become irrelevant by game 50. The pruning mechanism (Phase 5) is critical for long-term health.

**Human effort scaling**: Manual coaching doesn't scale. The automatic pipeline (lesson extraction + ICL curation) should be the primary path. Human coaching is for high-value refinement — but note that even non-expert coaching ("you keep losing material in trades") can be surprisingly effective because the model translates high-level guidance into specific improvements.

**Model capability ceiling**: A Haiku agent with perfect coaching will still play worse than Opus with no coaching. Soft Shell amplifies the Core's capabilities — it can't exceed them. This is actually valuable data for the project — it quantifies the gap between training (Core) and prompting (Shell).

---

*LxM Soft Shell Spec v0.1*
*"Experience is the best teacher — even for machines."*
