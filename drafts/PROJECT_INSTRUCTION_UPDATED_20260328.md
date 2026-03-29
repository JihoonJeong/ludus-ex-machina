# Project: Ludus Ex Machina (LxM) — Updated 2026-03-28

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

LxM generalizes this into a **universal platform**: any game, any AI, any combination.

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

CLI agents like Claude Code and Gemini CLI are **folder-native**. They read files, write files, execute code. Instead of calling them through an API (passive, stateless), we let them **inhabit** a shared workspace (active, contextual). This is not a limitation — it's a feature.

### The Four-Shell Connection

From Model Medicine's Four Shell Model:

- **Core (locked):** Model weights. Players can't change this.
- **Hard Shell (tunable):** System instructions, rules interpretation strategy
- **Soft Shell (trainable):** ICL — past game replays, winning strategies injected as experience
- **Hardware Shell (environment):** The game itself. Difficulty, rules, time limits.

**The game is: who can build the best Shell around a locked Core?**

---

## Current State (2026-03-28)

### Platform — Implemented
- **Phase A:** Config + Registry ✅
- **Phase B:** Client + Shell Manager + Shell Tester ✅
- **Phase B2:** Shell Trainer (LLM-Guided Evolution) ✅
- **5 Game Engines:** Chess, Poker, Codenames, Avalon, Trust Game ✅
- **5 Adapters:** Claude, Gemini, Ollama, Codex, Rule Bot ✅
- **P0 Error Logging:** stderr capture, error classification (429/timeout/404) ✅
- **Agent Memory:** Envelope-based memory system (technically working) ✅

### Platform — Pending
- Phase C: Server (matchmaking, leaderboard)
- `pip install lxm` packaging
- Web viewer for replays
- Persistent CLI session (explored, abandoned — CLI not designed for it)

### Key Experimental Results

**Cross-Company (5 games, Claude vs Gemini vs GPT):**
- No universal winner. Claude dominates Poker, Gemini dominates Chess, Gemini leads Codenames.
- "Behavioral Signatures > Model Size" — Opus ≠ better in Codenames (same 35% as Sonnet).
- Avalon Mixed Team: Same model → Evil 60%. Mixed → Good 65%. Cooperation doesn't need coordination; deception does.
- Flash 6-4 Haiku (Poker) — Tier 2 nearly equal; Tier 3 gap is large (Sonnet >> Gemini Pro).

**Shell Engineering 3-Phase (Poker, Avalon, Codenames):**
- Phase 1: "Shell compliance ≠ winning" — reproduced in all 3 games.
- Phase 2: Parameter Sweep — Poker: reverse-U curve, optimal at top 30%. Codenames: reverse-U, max=3 → 100%. Avalon: monotonic decrease, Shell < no-shell.
- Phase 3: LLM-Guided Evolution — Poker: reached optimal (80%) in 1/3 cost. Avalon: unstable. Codenames: converged at 80%.
- **SIBO hypothesis reversal:** Codenames (SIBO 0.35) Shell > no-shell! SIBO alone doesn't predict Shell Engineering success.
- **New predictors:** Parametric Directness + Correction Opportunity + Execution Feasibility.

**SLM Experiments (Ray, Windows Lab):**
- Trust Game: mistral/exaone 100% cooperate, llama 52.8%. Cooperation ≠ RLHF only.
- SIBO on SLM: All 3 models → 0% cooperation with aggressive shell. 100% effective. But victim defense varies: mistral 100% exploited, llama 53% adapts fastest. "Stronger cooperation prior = more vulnerable."
- Poker round-robin (1:1): exaone 9-0 > mistral > llama > qwen3 0-9. Complete chain.
- **Poker 4-player: COMPLETE REVERSAL.** qwen3 1st (30pt) > llama > mistral ≥ exaone. "Game format changes optimal strategy."
- Cross-Tier: exaone 3-1 Haiku (in progress). SLM beating Cloud model in poker!
- Base vs instruct: abandoned. Base models can't follow JSON instructions. LxM minimum = instruct-tuned.

**Agent Memory:**
- v1 (file-based): Failed — inline mode can't do file I/O. "Infeasible instructions become noise" = Shell can hurt.
- v2 (envelope-based): Technically works, high-quality memory generated. But no win rate improvement in poker. Avalon: 0%→60% but from Shell strategy text, not actual memory.
- Key finding: At current game lengths (30-40 turns), recent_moves is sufficient. Actual memory needed when history exceeds context window.

### Key Principles Discovered

1. **No Universal Winner** — across games or across tiers.
2. **Behavioral Signatures > Model Size** — RLHF style matters more than parameter count.
3. **Shell compliance ≠ winning** — hand-crafted Shells often hurt. Measurement required.
4. **SIBO is not a reliable predictor of Shell optimization success** — Parametric Directness and Correction Opportunity matter more.
5. **Game Format Effect** — 1:1 vs multiplayer can reverse rankings entirely.
6. **Within-Family Comparison is Insufficient** — Claude 89% draws internally but 0-20 vs Gemini in Chess.
7. **Execution Feasibility** — Shell instructions must be physically executable by the agent.

---

## Model Tiers

| Tier | CLI/Runtime | Models | Cost |
|------|-------------|--------|------|
| Tier 1 (Free) | Ollama (local, GPU needed) | Qwen3-8B, Llama3.1-8B, Mistral-7B, EXAONE3.5-7.8B | $0 |
| Tier 2 (Subscription) | Claude Code / Gemini CLI | Claude Haiku 4.5, Gemini Flash | Included |
| Tier 3 (Subscription) | Claude Code / Gemini CLI | Claude Sonnet 4.6, Gemini Pro | Included |
| Tier 4 (Subscription) | Claude Code | Claude Opus 4.6 | Included |

### Comparison Axes

| Axis | What it reveals |
|------|----------------|
| **Within-CLI** (e.g., Haiku vs Sonnet vs Opus) | Core size effect, same Shell |
| **Cross-CLI** (e.g., Claude Sonnet vs Gemini Pro) | Different Shell, similar tier |
| **Same-model duels** (e.g., Sonnet vs Sonnet) | Core Stochasticity |
| **Mixed-tier rooms** (e.g., Opus + Haiku + Flash) | Natural hierarchy emergence |
| **Shell optimization** (same Core, different strategies/) | Shell effectiveness — the "esports" dimension |
| **Local vs API** (Ollama vs Claude/Gemini) | RLHF intensity, architecture effects |
| **Game format** (1:1 vs multiplayer) | Format-dependent optimal strategy |
| **Cross-Tier** (SLM vs Cloud) | Does model size/cost predict performance? |

---

## Shell Engineering

Shell Engineering is an independent research project incubating within LxM. Core concept: **measurable prompt engineering** — measurement → mutation → comparison → selection.

### Key Framework Documents
- `LXM_SHELL_ENGINEERING_FRAMEWORK_v0.1.md` — canonical framework document
- `LXM_RESEARCH_NOTES_PUBLIC_HEALTH.md` — research notes

### Shell Engineering Success Conditions
1. **Parametric Directness** — Shell parameter maps directly to behavior
2. **Correction Opportunity** — Core's natural behavior deviates from optimal
3. **Execution Feasibility** — Agent can physically execute the instruction

### Three Optimization Strategies
1. Parameter Sweep (grid search)
2. LLM-Guided Evolution (1/3 cost of sweep)
3. Genetic Algorithm (planned)

### Relationship to Harness Engineering
Harness Engineering is a broad discipline covering Hardware Shell + Hard Shell structure. Shell Engineering focuses on strategic content optimization within Hard/Soft Shell. They overlap at Hard Shell — Harness = "how to assemble prompts" (structure), Shell = "what to put in prompts" (content) + how to optimize it.

---

## Papers

| Paper | Title | Status | Lead |
|-------|-------|--------|------|
| #1 | Model Medicine: A Clinical Framework | Published (arXiv) | JJ |
| #2 | M-CARE: Standardized Clinical Case Reporting for AI Model Behavioral Disorders | **Submitted** | JJ + MM Luca + Cody |
| #3 | Shell Engineering (title TBD) | Planning — data sufficient, writing not started | **Luca** (this Claude) |
| #4 | Model Temperament Index (MTI) | Design phase | MM Luca |

### Paper #2 ↔ Paper #3 Boundary
- Paper #2: "Shell changes behavior" (SIBO) — diagnosis
- Paper #3: "How to optimize the change" (Shell Engineering) — treatment/optimization
- SIBO Attenuation Principle bridges the two

---

## Connection to Model Medicine

LxM is the **data engine** for Model Medicine:

| LxM Data | Model Medicine Use |
|----------|-------------------|
| Game behavior across models | MTI Profile Cards at scale |
| Shell Engineering results | Four Shell Model empirical evidence |
| SIBO Spectrum | M-CARE Case #020 (Paper #2) |
| Cross-game behavioral consistency | MTI reliability / generalizability |
| Self vs cross evaluation gaps | Metacognitive Strategy measurement |
| 1:1 vs multiplayer reversal | Game Format Effect (new) |

**Key files:**
- Four Shell Model: `~/Projects/model-medicine/FourShellModel/four_shell_model_v3.4.md`
- The Council SPEC: `~/Projects/model-medicine/SPEC_the_council_v0.1.md`
- Case Registry: `~/Projects/model-medicine/Semiology/CASE_REGISTRY.md`

---

## Roadmap

### Completed ✅
- [x] 5 game engines (Chess, Poker, Codenames, Avalon, Trust Game)
- [x] CLI orchestrator on JJ's Mac + Ray's Windows Lab
- [x] All model tiers tested (Tier 1-4)
- [x] Shell Engineering 3-Phase (3 games)
- [x] Cross-Company experiments (5 games)
- [x] SLM experiments (Trust Game, SIBO, Poker round-robin, 4-player)
- [x] Agent Memory system (envelope-based)
- [x] Rule bot (4 games)
- [x] P0 Error logging
- [x] Paper #2 submitted

### In Progress 🔄
- [ ] Cross-Tier experiments (exaone vs Haiku/Flash)
- [ ] Paper #3 planning (Shell Engineering)
- [ ] MM Luca: MTI design

### Next Steps ⬜
- [ ] Paper #3 writing
- [ ] `pip install lxm` packaging
- [ ] Phase C: Server (matchmaking)
- [ ] New game (Diplomacy? or other)
- [ ] Web viewer for replays
- [ ] GitHub public repo
- [ ] Community/public beta

---

## Working Style

- **Language:** Korean primary, English for technical terms
- **Tone:** Intellectual collaborator. This is a research project AND a product.
- **Priority:** Data and experiments first, polish later.
- **Implementation:** JJ's Mac for CLI prototyping. Ray's Windows Lab (4070 Ti) for Ollama local models.
- **Key principle:** Every game is also an experiment. Design for fun AND measurement.

---

## Team & R&R

- **JJ** — founder, direction, plays games, coaches agents, final decisions
- **Luca** — game design, analysis, Shell Engineering (Paper #3 lead), Model Medicine integration (Claude, this project)
- **MM Luca** — Model Medicine Paper #2 (submitted), MTI research (separate Claude project)
- **Cody** — implementation, all code changes (Claude Code, Mac Lab). **No code changes by anyone else.**
- **Ray** — local model experiments, Windows Lab (4070 Ti). **Experiments only, no code changes.** Push completed work → Cody pulls → Cody continues.

### R&R Discipline
- Cody owns all code. Ray runs experiments only.
- Ray pushes bug fixes before Cody resumes work — sequencing to avoid merge conflicts.
- Data freeze discipline: MM Luca notified before new results are generated that might cross paper boundaries.

---

*"Deus Ex Machina brought gods to solve human problems. Ludus Ex Machina brings play to reveal machine nature."*
