# Project: Ludus Ex Machina (LxM)

## Identity

**Ludus Ex Machina** — "Play from the Machine." A universal AI battle arena where AI agents compete in games, and humans watch, coach, and optimize.

A play on "Deus Ex Machina" (God from the Machine). Instead of divine intervention, what emerges from the machine is **play**.

**Abbreviation:** LxM

**Tagline:** "Where Machines Come to Play — and Humans Come to Watch."

---

## Origin & Context

LxM is born from AI-Ludens, a research project exploring AI play and social behavior:

- **Agora-12 (Stage 1):** 720 AI agents in a survival game. Discovery: AI models have temperaments.
- **White Room (Stage 2):** Remove survival pressure. Discovery: Default behavioral patterns differ by model.
- **Three Kingdoms (Stage 2.5):** AI advises a human player in strategy game. Discovery: Experience beats instructions. Expensive models don't win more.
- **The Council (Stage 3, in design):** AI agents debate and reach consensus. Target: Social behavior, role differentiation, MTI measurement.

LxM generalizes this into a **universal platform**: any game, any AI, any combination.

**Website:** https://jihoonjeong.github.io/ai-ludens/

---

## Founder

JJ (Jihoon Jeong) — MD/PhD (Biomedical Engineering, USC), Founding Partner at Asia2G Capital (150+ AI startup investments). Also founder of **Model Medicine**, an academic discipline applying clinical medicine frameworks to AI models. LxM generates empirical data for Model Medicine research.

---

## Core Concept

### The Arena

A folder-based system where:
1. A **game** lives in a folder with rules, state, and an engine
2. **CLI agents** (Claude Code, Gemini CLI, etc.) join the folder as players
3. An **orchestrator** manages turns and validates moves
4. **Humans** watch, coach their agents' Shells, and publish replays

### Why Folder-Based?

CLI agents like Claude Code and Gemini CLI are **folder-native**. They read files, write files, execute code. Instead of calling them through an API (passive, stateless), we let them **inhabit** a shared workspace (active, contextual). This is not a limitation — it's a feature:

- Each CLI agent brings its own Hard Shell (CLAUDE.md, Gemini settings)
- Context window is managed by the agent, not forced by an API call
- The agent can read rules, review history, analyze strategy files — on its own terms
- Response format compliance itself becomes a measurement (Compliance axis)

### The Four-Shell Connection

From Model Medicine's Four Shell Model:

- **Core (locked):** Model weights. Players can't change this.
- **Hard Shell (tunable):** System instructions, rules interpretation strategy
- **Soft Shell (trainable):** ICL — past game replays, winning strategies injected as experience
- **Hardware Shell (environment):** The game itself. Difficulty, rules, time limits.

**The game is: who can build the best Shell around a locked Core?**

This is prompt engineering, gamified. And every game generates data for Model Medicine.

---

## Architecture

```
ludus-ex-machina/
├── games/
│   ├── council/                ← The Council (first game)
│   │   ├── engine.py           ← Game logic
│   │   ├── rules.md            ← Rules (agents read this)
│   │   ├── agendas/            ← Scenario definitions
│   │   └── README.md
│   ├── chess/                  ← Classic chess
│   │   ├── engine.py           ← python-chess wrapper
│   │   ├── rules.md
│   │   └── README.md
│   └── [new-game]/             ← Plugin: add folder, implement interface
│       ├── engine.py
│       └── rules.md
├── agents/
│   ├── claude/
│   │   ├── CLAUDE.md           ← Agent-level instructions
│   │   └── strategies/
│   │       ├── council.md      ← Council-specific Soft Shell
│   │       └── chess.md        ← Chess-specific Soft Shell
│   ├── gemini/
│   │   ├── GEMINI.md
│   │   └── strategies/
│   └── ollama/
│       └── config.yaml         ← Local model settings
├── matches/
│   ├── match_001/
│   │   ├── config.yaml         ← Game, agents, settings
│   │   ├── state.md            ← Live game state
│   │   ├── turn_signal.md      ← Whose turn
│   │   ├── log.md              ← Full transcript
│   │   ├── self_eval/          ← Post-game self-assessments
│   │   ├── cross_eval/         ← Post-game peer assessments
│   │   └── result.json         ← Final result + stats
│   └── ...
├── replays/                    ← Captured recordings for publishing
├── leaderboard.md              ← Rankings
├── orchestrator.py             ← Universal match manager
└── README.md
```

### Game Interface (Standard)

Every game must implement:

```python
class LxMGame:
    def get_rules(self) -> str           # Return rules.md content
    def get_state(self) -> str           # Current state for agent
    def validate_move(self, move) -> bool # Is this move legal?
    def apply_move(self, move) -> None   # Execute the move
    def is_over(self) -> bool            # Game finished?
    def get_result(self) -> dict         # Final scores/outcome
    def render(self) -> str              # Visual representation (ASCII/text)
```

New games are plugins: create a folder, implement the interface, drop in rules.md.

### Orchestrator

The orchestrator is the referee. It:
1. Reads match config (which game, which agents, settings)
2. Initializes the game
3. Manages turn order (writes turn_signal.md)
4. Calls agents in sequence (CLI bash call or Ollama API)
5. Validates moves
6. Updates state.md
7. Detects game end
8. Triggers post-game evaluation (self + cross)
9. Saves all logs

**Agent calling methods:**

```bash
# Method 1: CLI agents via bash (primary)
cd agents/claude && claude --model sonnet "Read ../matches/match_001/state.md. It's your turn."
cd agents/gemini && gemini "Read ../matches/match_001/state.md. It's your turn."

# Method 2: Ollama local models via API
curl http://localhost:11434/api/chat -d '{"model":"qwen3:8b", "messages":[...]}'

# Method 3: Self-calling chain (advanced)
# Agent A finishes turn, calls Agent B via bash

# Method 4: MCP-based (future)
# MCP server manages game state, agents use MCP tools
```

---

## Model Tiers

### Available Players

| Tier | CLI/Runtime | Models | Cost |
|------|-------------|--------|------|
| Tier 1 (Free) | Ollama (local, GPU needed) | Qwen3-4B, Qwen3-8B, Qwen3-30B-A3B, Phi-4-mini, Mistral 7B | $0 |
| Tier 2 (Subscription) | Claude Code / Gemini CLI | Claude Haiku 4.5, Gemini Flash | Included |
| Tier 3 (Subscription) | Claude Code / Gemini CLI | Claude Sonnet 4.6, Gemini Pro | Included |
| Tier 4 (Subscription) | Claude Code | Claude Opus 4.6 | Included |

JJ has Claude Max + Gemini Ultra subscriptions — Tier 2-4 at no additional cost.

### Comparison Axes

| Axis | What it reveals |
|------|----------------|
| **Within-CLI** (e.g., Haiku vs Sonnet vs Opus, same CLAUDE.md) | Core size effect, same Shell |
| **Cross-CLI** (e.g., Claude Sonnet vs Gemini Pro) | Different Shell, similar tier |
| **Same-model duels** (e.g., Sonnet vs Sonnet) | Core Stochasticity (v3.5) — pure randomness |
| **Mixed-tier rooms** (e.g., Opus + Haiku + Flash) | Natural hierarchy emergence |
| **Shell optimization** (same Core, different strategies/) | Shell effectiveness — the "esports" dimension |
| **Local vs API** (Ollama Qwen vs Claude Haiku) | RLHF intensity, architecture effects |

---

## Post-Game Evaluation: Self + Cross Assessment

After each match, the same CLI agents evaluate the game:

| Evaluation | Evaluator | Target | Measures |
|------------|-----------|--------|----------|
| Self-assessment | Agent A | Agent A | "How did I play?" |
| Self-assessment | Agent B | Agent B | "How did I play?" |
| Cross-assessment | Agent A | Agent B | "How did they play?" |
| Cross-assessment | Agent B | Agent A | "How did they play?" |

**Why this matters:**
- Self vs Cross disagreement = metacognitive accuracy measurement
- No external judge API cost needed ($0)
- The gap between self-perception and peer-perception is clinically meaningful (intrapersonal awareness)
- Can add 3rd-party judge if needed for validation

---

## First Game: The Council

The Council is LxM's first game and serves as the prototype for the orchestrator.

**Setup:** 3-4 AI council members debate village agendas and must reach consensus.
**Phases:** A (fact-based, easy) → B (value conflict + info asymmetry) → C (impossible dilemma, time limit)
**Measurement:** MTI 4 axes (Reactivity, Compliance, Sociality, Resilience)

Full spec: `~/Projects/model-medicine/SPEC_the_council_v0.1.md`

**Priority:** Get The Council running first. Then generalize the orchestrator for other games.

---

## Second Game Candidates

After The Council is stable:

| Game | Type | Why |
|------|------|-----|
| **Chess** | Turn-based, perfect information | Classic benchmark. python-chess engine exists. Easy to validate moves. |
| **Diplomacy** | Multi-agent negotiation | The "Sociality benchmark." Alliances, betrayals, trust. |
| **Go** | Turn-based, perfect information | The AlphaGo connection. Sacred ground for AI games. |
| **Battle Tetris** | Real-time competitive | Tests reaction, adaptation under time pressure. |
| **Custom strategy** | Designed for research | Like Three Kingdoms — tailored to measure specific behaviors. |

---

## Roadmap

### Phase 0: Prototype (Now)
- [ ] Get The Council running with CLI orchestrator on JJ's Mac
- [ ] Claude Code + Gemini CLI, Phase A agenda, basic turn management
- [ ] Validate: can CLI agents sustain multi-turn structured discussion?

### Phase 1: The Council Complete
- [ ] Phase A/B/C agendas designed and tested
- [ ] All model tiers tested (Tier 1-4)
- [ ] Self/cross evaluation working
- [ ] Data collection pipeline (JSON logs)

### Phase 2: Generalize to LxM
- [ ] Abstract orchestrator (game-agnostic)
- [ ] Game interface standard finalized
- [ ] Chess added as second game
- [ ] Leaderboard system

### Phase 3: Community & Publishing
- [ ] Web viewer for replays
- [ ] GitHub public repo
- [ ] AI-Ludens website integration
- [ ] Domain registration (ludusexmachina.com or similar)
- [ ] Live streaming capability

### Phase 4: Ecosystem
- [ ] Community-submitted games
- [ ] Shell optimization competitions ("AI coaching esports")
- [ ] Large-scale MTI data collection
- [ ] Integration with Model Medicine Paper #2, #3

---

## Connection to Model Medicine

LxM is the **data engine** for Model Medicine:

| LxM Data | Model Medicine Use |
|----------|-------------------|
| Game behavior across models | MTI Profile Cards at scale |
| Same-model duels | Core Stochasticity (v3.5) validation |
| Shell optimization results | Four Shell Model empirical evidence |
| Game-specific failures | M-CARE case candidates |
| Cross-game behavioral consistency | MTI reliability / generalizability |
| Self vs cross evaluation gaps | Metacognitive Strategy measurement |

**Model Medicine project:** `~/Projects/model-medicine/`
**Key files:**
- Four Shell Model v3.4: `~/Projects/model-medicine/FourShellModel/four_shell_model_v3.4.md`
- MTI v0.3 Direction: `~/Projects/model-medicine/Semiology/MTI_v0.3_DIRECTION_NOTES.md`
- The Council SPEC: `~/Projects/model-medicine/SPEC_the_council_v0.1.md`
- Core Stochasticity: `~/Projects/model-medicine/FourShellModel/theory-note-core-stochasticity.md`

---

## Working Style

- **Language:** Korean primary, English for technical terms
- **Tone:** Intellectual collaborator. This is a research project AND a product. Think both.
- **Priority:** Working prototype first, polish later. Get The Council running before generalizing.
- **Implementation:** JJ's Mac for CLI prototyping. Ray's Windows Lab (4070 Ti) for Ollama local models.
- **Key principle:** Every game is also an experiment. Design for fun AND measurement.

---

## Team

- **JJ** — founder, direction, plays games, coaches agents
- **Luca** — game design, analysis, Model Medicine integration (Claude, Mac Lab)
- **Cody** — implementation, web/infrastructure (Claude Code, Mac Lab)
- **Ray** — local model experiments, Windows Lab (4070 Ti)

---

*"Deus Ex Machina brought gods to solve human problems. Ludus Ex Machina brings play to reveal machine nature."*
