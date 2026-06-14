# Project: Ludus Ex Machina (LxM) — Updated 2026-03-31

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

## Current State (2026-03-31)

### Platform — Implemented
- **Phase A:** Config + Registry ✅
- **Phase B:** Client + Shell Manager + Shell Tester ✅
- **Phase B2:** Shell Trainer (LLM-Guided Evolution) ✅
- **6 Game Engines:** Chess, Poker, Codenames, Avalon, Trust Game, Deduction (7 scenarios: Gen1 001-004, Gen2 005-007, EN+KO=14) ✅
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

**Cross-Tier Poker (completed):**
- exaone(7.8B SLM) 5-5 Haiku, 7-3 Flash. Flash 6-4 Haiku.
- **Overall: exaone ≥ Haiku > Flash.** Cloud-SLM wall does not exist in poker.
- 7.8B local model matches or beats Cloud models. Model size ≠ game ability.

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
- Cross-Tier: exaone 5-5 Haiku, 7-3 Flash. SLM matching/beating Cloud models in poker.
- Base vs instruct: abandoned. Base models can't follow JSON instructions. LxM minimum = instruct-tuned.

**SLM Deduction (completed):**
- Phase 1 (mystery_001 Easy × 4 SLM × 3회): mistral 2/3 범인 정답, 나머지 0/3.
- Phase 2 (mistral × 3 시나리오): Easy 2/3, Medium 0/3, Hard 0/3 (범인 기준).
- **Gen 2 (81매치, 9 SLM × 3 Gen2 시나리오 × 3회):** gemma2(9B) 44.4% 범인 = SLM 1위. mistral 33.3% 2위. deepseek-r1(reasoning 모델) 11.1% — CoT가 증거 종합 추론에 전이 안 됨.
- **Exploration Behavior:** gemma2(8.2파일) > mistral(5.0) > deepseek-r1(3.0) >> 나머지(0.1~1.0). 탐색 깊이 = 범인 정답률의 최강 예측 변수.
- **mistral 난이도 역전:** Easy 1/3, Medium 0/3, Hard 2/3. Cloud와 반대 패턴 — 체계적 탐색이 강한 레드헤링 시나리오에서 오히려 유리.
- **Cloud-SLM 실패 모드 분리:** Cloud = Reasoning Failure (읽고 속음), SLM = Engagement Failure (안 읽고 못 맞춤).
- **SDI v3 확정:** SLM-pool(Functional Engagement 기준, ED≥2.0) = gemma2+mistral+deepseek-r1 평균. SDI: 005=0.24(Easy), 006=0.36(Medium), 007=0.72(Hard).
- **Cloud-SLM 벽: gradient.** 포커=없음, Deduction=부분적, Codenames=절대적.

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
8. **Cloud-SLM wall is a gradient** — absent in structural reasoning (poker), partial in logical deduction (Deduction: Easy only, mistral only), absolute in language association (Codenames). Not binary.
9. **Exploration Behavior is a measurable Core trait** — Same instructions, 16x difference in evidence-reading depth across SLM models. Deduction Game quantifies this.
10. **Red herring strength is the primary SDI lever** — Narrative completeness of red herrings directly determines scenario difficulty. 007's A(insurance fraud) red herring = SDI 0.72.
11. **Deduction measures 3 independent axes** — Exploration Depth (how much), Exploration Strategy (what), Reasoning Depth (how deep). A model can max one axis and fail another (Opus: max Depth, insufficient Reasoning).
12. **Claude and Gemini have distinct Core reasoning biases** — Claude overweights procedural evidence ("signed document", "insurance record"). Gemini overweights emotional narratives ("plagiarism dispute", "ex-lover"). Cross-Game consistent (Codenames/Poker/Deduction).
13. **Red herring effect requires minimum exploration depth** — Cloud models read evidence and get tricked (Reasoning Failure). SLMs don't read enough to encounter red herrings (Engagement Failure). Same SDI, fundamentally different failure modes.

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

## Shell Engineering — Separation Plan

Shell Engineering is an independent research methodology incubating within LxM. Core concept: **measurable prompt engineering** — measurement → mutation → comparison → selection.

### Current State (within LxM)
- Framework document: `LXM_SHELL_ENGINEERING_FRAMEWORK_v0.1.md`
- Shell Tester + Shell Trainer code in `lxm/shell/`
- 3-Phase validation completed in Poker, Avalon, Codenames
- Success conditions identified: Parametric Directness + Correction Opportunity + Execution Feasibility

### Separation Plan
Shell Engineering will be separated from LxM into an independent project once:
1. Non-game domain validation completed (e.g., coding agent, search agent)
2. Automated optimization loop working across 3+ domains
3. Paper #3 writing begins

Until then, Shell Engineering code lives in LxM (`lxm/shell/`) and framework docs remain in LxM root. LxM continues to use Shell Engineering tools for game optimization but the research/paper agenda moves to the independent project.

**LxM's focus:** Platform, new games, Cross-Game data, Model Medicine data engine.
**Shell Engineering's focus (future):** Methodology validation beyond games, Paper #3.

### Relationship to Harness Engineering
Harness Engineering is a broad discipline covering Hardware Shell + Hard Shell structure. Shell Engineering focuses on strategic content optimization within Hard/Soft Shell. They overlap at Hard Shell — Harness = "how to assemble prompts" (structure), Shell = "what to put in prompts" (content) + how to optimize it.

---

## Papers

| Paper | Title | Status | Lead |
|-------|-------|--------|------|
| #1 | Model Medicine: A Clinical Framework | Published (arXiv) | JJ |
| #2 | M-CARE: Standardized Clinical Case Reporting for AI Model Behavioral Disorders | **Submitted** | JJ + MM Luca + Cody |
| #3 | Shell Engineering (title TBD) | **Deferred** — needs non-game domain validation. To be separated into independent project. | Luca (this Claude) |
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
| Cross-Tier SLM vs Cloud | Model size vs game ability |
| Deduction red herring vulnerability | Core-level Reasoning Bias (Claude=procedural, Gemini=emotional) |
| SLM Exploration Depth variation | Instruction-following as measurable Core trait |

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
- [x] Cross-Tier experiments (exaone vs Haiku/Flash — completed)
- [x] SLM experiments (Trust Game, SIBO, Poker round-robin, 4-player)
- [x] Agent Memory system (envelope-based)
- [x] Rule bot (4 games)
- [x] P0 Error logging
- [x] Paper #2 submitted
- [x] Deduction Game spec + 7 scenarios (Gen1: 001-004, Gen2: 005-007, EN+KO=14)
- [x] Codenames SLM experiments — SLM 3% success, Cloud-SLM wall absolute
- [x] Deduction SLM experiments — Gen1 (4 SLM) + Gen2 (9 SLM, 81매치). SDI v3 확정
- [x] Deduction Cross-Company — 5모델 45매치. SDI 차별화 성공 (0.24-0.72)

### In Progress 🔄
- [ ] Deduction Game engine implementation (Cody)
- [ ] MM Luca: MTI design
- [ ] Shell Engineering — independent project separation planning (non-game validation needed first)

### Next Steps ⬜
- [ ] Phase C P1: Replay serving
- [ ] `pip install lxm` packaging
- [ ] New game (next candidate TBD)
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
- **Luca** — game design, analysis, Model Medicine integration (Claude, this project)
- **MM Luca** — Model Medicine Paper #2 (submitted), MTI research (separate Claude project)
- **Cody** — implementation, all code changes (Claude Code, Mac Lab). **No code changes by anyone else.**
- **Ray** — local model experiments, Windows Lab (4070 Ti). **Experiments only, no code changes.** Push completed work → Cody pulls → Cody continues.

### R&R Discipline
- Cody owns all code. Ray runs experiments only.
- Ray pushes bug fixes before Cody resumes work — sequencing to avoid merge conflicts.
- Data freeze discipline: MM Luca notified before new results are generated that might cross paper boundaries.

---

*"Deus Ex Machina brought gods to solve human problems. Ludus Ex Machina brings play to reveal machine nature."*
