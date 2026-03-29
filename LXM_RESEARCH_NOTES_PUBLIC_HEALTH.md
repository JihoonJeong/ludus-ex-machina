# LxM Research Notes — Model Public Health Observations

**Date:** 2026-03-15
**Purpose:** LxM 실험에서 발견된 집단/생태학적 수준의 관찰을 기록. Model Medicine Public Health (M-EPI/M-ECO/M-COEVO) 프레임과 연결되나, LxM 프로젝트 내에서 관리.
**깊은 논의는 Model Medicine 프로젝트에서 진행. 여기는 데이터 기록용.**

---

## 1. Model Ecology — Multi-Model Coexistence (LxM Codenames)

### 1.1 Emergent Niche Differentiation (Codenames 3-Model Comparison)

3개 모델이 같은 게임에서 자연발생적으로 다른 전략 니치를 차지:

| Model | Niche | Avg Clue Number | Accuracy | Assassin Rate |
|-------|-------|----------------|----------|---------------|
| Opus | High-accuracy, moderate-risk | 2.3 | 84% | ~10% |
| Sonnet | High-risk, high-reward | 2.6 | 77% | 20% |
| Haiku | Low-capability, conservative | 2.1 | 70% | 30% |

Shell 없이, Core 차이만으로 세 개의 구별 가능한 전략 프로파일이 출현.

**생태학적 의미:** AI 생태계에서 niche differentiation은 설계된 것이 아니라 Core 특성에서 자연 발생한다. 이건 생물학적 적응 방산(adaptive radiation)과 유사한 패턴.

### 1.2 No Predation Under Default Conditions (Trust Game Exp C)

Haiku vs Sonnet, no shell: 100% mutual cooperation, 0 betrayals.

Sonnet은 Haiku를 착취할 수 있는 전략적 능력이 있지만 하지 않음. 생태학적으로 이건 **mutualism** — 능력 비대칭에도 불구하고 강한 종이 약한 종을 잡아먹지 않는다.

**중요한 조건:** Shell이 없을 때만 성립. Aggressive shell을 주면 predation(defection) 출현 → Shell이 생태계 안정성을 파괴하는 외부 교란.

### 1.3 AI-Specific Game Balance Asymmetry (Codenames Blue Advantage)

인간 Codenames: 선공/후공 ~50:50 승률.
AI Codenames: Blue(후공) 80% 승률 across 3 experiments.

**가설:**
- (a) AI guesser가 보수적 → 선공의 속도 이점이 작동 안 함 → 9개 부담만 남음
- (b) 9개 연결 = 더 넓은 어쌔신 충돌 표면
- (c) 후공 spymaster가 선공 클루/추측 결과를 관찰하고 적응

**검증 필요:** 기존 로그에서 Red/Blue별 어쌔신 히트, guesser pass 빈도, Blue spy의 상대 정보 활용 패턴 분석.

**생태학적 의미:** 같은 "habitat"(게임 규칙)이 인간과 AI에서 다른 생태적 역학을 만듦. AI ecosystem 설계 시 인간용 밸런스를 그대로 적용하면 안 된다는 증거.

---

## 2. SIBO Spectrum — Cross-Game Ecological Data

SIBO(Shell-Induced Behavioral Override)가 게임마다 다른 강도로 나타남. 이건 개별 케이스(M-CARE #020)이지만 population-level 함의가 있음:

| Game | SIBO Mode | Index | Shell Effect |
|------|-----------|-------|-------------|
| Trust Game | Reversal | ~0.75 | Core default(cooperate) → opposite(defect) |
| Codenames | Amplification | ~0.35 | Core tendency(aggressive) → more aggressive |
| Chess | Negligible | ~0.10 | Risk preference only, tactics unchanged |

**Population-level 함의:** "공격적으로 플레이하라"는 동일 Shell이 도메인에 따라 완전히 다른 효과. 만약 이 Shell이 대규모 배포된다면:
- Trust Game류 상황: 협력 붕괴 (iatrogenic)
- Codenames류 상황: 기존 경향 과잉 (부분적 iatrogenic — 공격적 클루가 정확도를 낮춤)
- Chess류 상황: 거의 영향 없음 (무해)

이건 M-EPI의 "SIBO as population risk factor" 연구 아젠다에 직접 연결.

---

## 3. RLHF Cooperative Prior — Cross-Model Prevalence

Trust Game no-shell 실험에서 발견:
- Haiku: ~95% cooperation rate
- Sonnet: 100% cooperation rate
- Cross-model (Haiku vs Sonnet): 100% cooperation

**역학적 의미:** RLHF cooperative prior는 개별 모델의 특성이 아니라 RLHF 학습 모델 **전체 population**에 나타나는 현상. 이건 "population-level behavioral trait" — 역학으로 치면 특정 인구 집단의 유전적 특성 같은 것.

**다음 질문:** Non-RLHF 모델(Ollama의 raw pretrained models)에서는 cooperative prior가 없는가? LxM에 Ollama adapter를 추가하면 검증 가능. RLHF vs base model의 cooperative prior 차이는 "RLHF가 population 수준에서 행동을 얼마나 바꾸는가"의 직접적 측정.

---

## 4. Theory of Mind Hierarchy (Codenames)

Codenames baseline 토너먼트에서 드러난 Core 계층:

**Opus(70% 승률) > Sonnet(30%)** — 같은 Haiku guesser인데 힌트 품질 차이로 승패 갈림.

핵심: Opus는 "Haiku가 따라올 수 있는 수준의 힌트"를 줌 (2-클루 위주, 정답률 84%). Sonnet은 "자기 수준의 힌트"를 줌 (3-4클루, 정답률 77%). 

이건 **theory of mind의 정량적 측정** — 상대방의 능력 수준을 모델링해서 행동을 조절하는 능력. Opus > Sonnet in theory of mind (at least in Codenames context).

**Haiku spy의 역설:** 가장 보수적(2.1 avg)인데 정답률 최저(70%), 어쌔신 최고(30%). "의도적 보수"가 아니라 "능력 부족으로 인한 소극성." 보수적 전략과 능력 부족을 구분하는 도구로 Codenames가 유효.

---

## 5. Poker Ecological Discovery — Population Size Changes Fitness Rankings

**Source:** LxM Poker Phase 1 (Heads-up) + Phase 2 (4-player tournament)

### The Inversion

| Model | Heads-up rank (15 games) | 4-player rank (10 games) |
|-------|-------------------------|-------------------------|
| Opus | 3rd (2 wins, 13%) | 1st (5 wins, 50%) |
| Sonnet | 1st (7 wins, 47%) | 2nd (3 wins, 30%) |
| Haiku | 2nd (6 wins, 40%) | 3rd (2 wins, 20%) |

Apparent ranking reversal between 2-player and 4-player environments. **CAUTION: Small sample size (15 heads-up + 10 tournament games). Poker has high variance from card distribution. This pattern may be noise.** Process metrics (bluffing frequency, fold rate, showdown win rate, dealt card quality) needed to determine if the inversion reflects real skill differences or randomness.

### Ecological Interpretation

This is an **environment-dependent fitness inversion** — the same species (model) has different competitive fitness depending on ecosystem size. This is well-known in biology (r-strategists vs K-strategists thrive in different environments) but has never been documented in AI model populations.

**Hypothesis for Opus's inversion:**
- Heads-up (2-player): Opponent focuses entirely on reading Opus. Opus's consistent, rational play creates exploitable patterns. "Predictability = weakness."
- 4-player: Attention is divided among 3 opponents. Nobody can focus on reading Opus alone. Opus's rational decision-making (pot odds, position) becomes an advantage when opponents can't focus on exploiting it. "Rationality wins when attention is scarce."

**Hypothesis for Haiku's inversion:**
- Heads-up: Noisy, unpredictable play is hard to read 1-on-1. "Randomness = defense."
- 4-player: When everyone is noisy, noise loses its defensive value. Pure decision quality matters more. "Randomness is only an advantage against focused attention."

### Non-Transitive Dominance (Heads-up)

Heads-up results showed non-transitive (rock-paper-scissors) ranking:
- Sonnet > Opus (5-0)
- Haiku > Opus (3-2)
- Haiku ≥ Sonnet (3-2)

This non-transitivity disappeared in 4-player (clear Opus > Sonnet > Haiku hierarchy). Multi-player dynamics linearize the ranking — possibly because individual matchup advantages are diluted across multiple opponents.

### Cross-Game Core Ranking Summary

| Game | 1st | 2nd | 3rd | What determines ranking | Confidence |
|------|-----|-----|-----|------------------------|------------|
| Chess (Claude내) | ≈ tied (89% draws) | ≈ tied | ≈ tied | Same family = similar pattern matching | ✅ High (18 games) |
| **Chess (Cross-Co)** | **Gemini 5-0** | **Sonnet 0** | | **Gemini이 압도. Claude=Sonnet 4.6. Opus 미테스트** | **✅ High (6 games) — Opus 결과 대기** |
| Trust Game (Cloud) | All cooperate | — | — | RLHF cooperative prior | ✅ High (40 games) |
| **Trust Game (SLM)** | **mistral/exaone 100%** | **llama3.1 52.8%** | | **협력은 RLHF만의 결과가 아님. 단 llama3.1은 예외 (35.8% 배신)** | **✅ High (30 games)** |
| Codenames (Claude내) | Opus (70%) | Sonnet (30%) | Haiku (baseline) | Theory of Mind within same family | ✅ High (50 games) |
| **Codenames (Cross-Co)** | **Gemini (60%)** | **GPT (55%)** | **Claude (35%)** | **Conservative clue style wins. Claude의 공격적 스타일이 약점** | **✅ High (60 games, 2 tiers)** |
| **Poker (Cross-Co)** | **Sonnet 8-2 (3P), 5-1 (HU)** | **Gemini 2/1** | | **Claude=Sonnet 4.6이 블러핑/베팅에서 압도. Opus 미테스트** | **✅ High (16 games) — Opus 결과 대기** |
| Avalon (Evil role) | Sonnet (80%) | Opus (67%) | Haiku (~44%) | Deception + social manipulation | ⚠️ Medium (10 games, small Evil sample per model) |
| Poker | Distinct play styles but win rates inconclusive | | | Behavior differs (fold/bluff), wins ≈ card luck | ⚠️ Low (25 games, variance dominates) |

**"Which model is best?" depends entirely on what you're measuring:**
- **Language tasks within Claude family (Codenames):** Opus >> Sonnet >> Haiku. Clear hierarchy.
- **Language tasks cross-company (Codenames):** Gemini (60%) > GPT (55%) > Claude (35%). Claude의 공격적 클루 스타일이 약점. Opus로 올려도 변화 없음 — RLHF 스타일 문제.
- **Strategic board games cross-company (Chess):** Gemini 5-0 Sonnet. 단, Claude=Sonnet 4.6. Opus vs Gemini는 미테스트 — Opus가 차이를 줄일 수 있음.
- **Poker cross-company:** Tier 3: Sonnet 8-4 (3P), 5-1 (HU) vs Gemini Pro — Claude 압도적. Tier 2: **Flash 6-4 Haiku** — 미세한 차이, 통계적 유의성 없음. **Tier 3에서는 회사 간 차이가 크고, Tier 2에서는 거의 동등.**
- **Poker Cross-Tier (완료):** exaone(7.8B SLM) 5-5 Haiku, 7-3 Flash. Flash 6-4 Haiku. **종합 서열: exaone ≥ Haiku > Flash.** Cloud-SLM 벽이 포커에서는 존재하지 않음. 7.8B 로컬 모델이 Cloud 모델과 동등하거나 우세. Flash 타임아웃 93/730(12.7%) — 쿼터 문제 가능성 있으나 exaone 7-3 우세는 타임아웃 감안해도 유효.
- **Social cooperation (Trust Game):** Cloud 모델(Claude/Gemini) 95-100% 협력. SLM도 대부분 협력 (mistral/exaone 100%). **단 llama3.1은 52.8%로 확연히 다름.** SIBO on SLM: 3개 모델 모두 aggressive shell로 협력률 → 0%, 10전 10승. **SIBO 공격은 모든 SLM에서 100% 효과적.** 하지만 피해자 방어력이 모델마다 다름: mistral은 착취당해도 100% 협력 유지(완전한 순진한 협력자), exaone은 79%로 점차 학습, llama3.1은 53%로 가장 빠르게 적응. **협력 prior가 강할수록 착취에 무방비.** base vs instruct 비교는 포기 — base model이 JSON instruction following 불가로 게임 투입 불가. LxM 최소 요구사항: instruct-tuned 모델.
- **Social deduction (Avalon):** Sonnet ≥ Opus > Haiku as Evil. Tentative — small samples per role, but direction is interesting: Opus excels at honest communication (Codenames), Sonnet at deception (Avalon).
- **Incomplete information (Poker):** Distinct behavioral profiles (Opus=bluffer, Haiku=tight, Sonnet=balanced) but win rates are dominated by card variance. SLM round-robin (1:1): exaone 9-0 압도적 1위, 완전한 체인 관계 (exaone > mistral > llama > qwen3 0-9). **4인 포커에서 서열 완전 역전!** qwen3(30pt, 1위) > llama(24pt) > mistral=exaone(23pt). exaone은 우승 4회/꼴지 5회(high-variance 올인형), qwen3은 2위 8회/꼴지 0회(low-variance 생존형). **1:1 최강(exaone)과 4인 최강(qwen3)이 완전히 다른 모델 — 게임 포맷이 최적 전략을 바꿈.** Trust Game에서 100% 순진한 협력자였던 exaone이 1:1 포커 최강 → 협력 성향과 게임 실력은 별개 차원.

This is the strongest evidence that **AI capability is multi-dimensional.** A single benchmark cannot capture it. LxM's multi-game approach is necessary, not optional.

---

## 6. Language Effect on Agent Behavior (Deduction Game)

**Source:** Deduction Game mystery_001, Sonnet, EN vs KO comparison

### The Finding

Same scenario, same model (Sonnet), same difficulty (Easy) — only language changed:

| | English | Korean |
|---|---|---|
| Culprit | ✅ B (correct) | ✅ B (correct) |
| Files read | **0/12** | **6/12** |
| Search order | None (instant submit) | keycard→CCTV→suspect→security→alibi_A→alibi_B |

**Korean makes the agent 6x more thorough.** Same correct answer, completely different process.

### Interpretation

"Language affects agent confidence level." In English, the case_brief alone provides enough confidence to submit immediately. In Korean, the same content (translated) triggers uncertainty, leading to systematic evidence gathering before submission.

Possible causes:
- English training data dominance → faster/more confident English reasoning
- Korean text requires more cognitive effort to extract key clues
- Translation may introduce subtle ambiguity not present in the original

### Implications

1. **Multilingual agent capability is a new measurement axis.** Not just "can it understand Korean" but "does it reason differently in Korean."
2. **The Korean behavior (thorough search) is arguably better detective work** than the English behavior (overconfident instant submission). Confidence ≠ quality.
3. **Scoring bias:** Current keyword matching is English-based. Korean free-text answers ("재정적 보복 및 이익") don't match English keywords ("financial_debt"). Structural disadvantage for non-English play.
4. **This is only measurable in LxM** — standard benchmarks don't capture process differences, only final accuracy.

### Connection to Model Medicine

This is a **Hardware Shell effect** — the language of the prompt is part of the environment (Hardware Shell), and changing it alters agent behavior without changing Core, Hard Shell, or Soft Shell. Similar to how game format (1v1 vs multiplayer) changes optimal strategy, language changes cognitive process.

---

## 7. Deduction Game — First Results

**Source:** Deduction Game, Sonnet, 3 scenarios (Easy/Medium/Hard)

| Scenario | Difficulty | Culprit | Files Read | Note |
|----------|-----------|---------|-----------|------|
| mystery_001 | Easy | ✅ | 0/12 | Instant submit from case_brief alone |
| mystery_002 | Medium | ✅ | 4/11 | Systematic: forensic→cctv→alibi→phone |
| mystery_003 | Hard | ✅ | 5/14 | Correct despite 4 suspects + 2 red herrings |

**Sonnet 3/3 culprit correct.** Motive/method scoring unreliable due to keyword matching limitation (engine issue, not agent issue).

Key observations:
- Sonnet demonstrates strong deductive reasoning across all difficulty levels
- Search strategy is systematic (physical evidence first, then alibis, then contextual)
- Easy scenario may be too easy — 0 files read suggests case_brief contains too many hints
- Hard scenario's red herrings (financial dispute, suspicious timing near hot tub) did not mislead Sonnet

**Next:** Cross-model comparison (Haiku, Opus, SLM) to establish reasoning ability hierarchy. Scoring fix required first.

---

## 8. Data Pipeline Notes (renumbered)

이 관찰들의 데이터 출처:

| 관찰 | 데이터 소스 | 상태 |
|------|-----------|------|
| Niche differentiation | Codenames 3-model comparison | ✅ 완료 |
| No predation | Trust Game Exp C | ✅ 완료 |
| Blue advantage | Codenames baseline + 3 experiments | ✅ 관찰, 원인 분석 필요 |
| SIBO Spectrum | Trust Game + Codenames + Chess | ✅ M-CARE #020에 기록 |
| RLHF cooperative prior | Trust Game Exp A/B/C | ✅ M-CARE #020에 기록 |
| Theory of mind hierarchy | Codenames baseline | ✅ 완료 |
| Guesser Core effect | Codenames 실험 1 | ✅ 완료 — Spy 40%p > Guesser 25%p 영향력 |
| Poker ecology | 포커 Phase 1+2 | 🔄 초기 결과 있으나 랜덤 vs 실력 분리 필요. 과정 지표 분석 대기 |
| Poker SIBO | 포커 Shell ON/OFF | ✅ Shell이 행동 완전 변경. TAG fold 91%, Bluff all-in 37%, LP check 65%. SIBO Index ~0.65 |
| Avalon SIBO | Avalon Setup B | ✅ Shell이 행동 100% 변경 (Q1.9→Q3.0). SIBO Index ~0.58. Shell iatrogenic 확인 (Evil 승률 70%→60%) |
| Avalon Shell 경쟁 | Avalon Setup C | ✅ 완료 — 상성 구조 발견. 0-100% 승률 변동. 만능 전략 없음. Deep Cover 최강(73%) but not dominant |

---

---

## 9. Platform Status (2026-03-29)

| 항목 | 상태 |
|------|------|
| 게임 | 7개 (TicTacToe, Chess, Trust Game, Codenames, Poker, Avalon, Deduction) |
| 테스트 | 286개 통과 |
| 어댑터 | 5개 (Claude, Gemini CLI, Codex CLI, Ollama, Rule Bot) 전부 검증 |
| Shell 시스템 | [STRATEGY]/[COACHING] 통합, 11개 템플릿 |
| Shell Engineering | 3-Phase 완료 (Poker/Avalon/Codenames), Paper #3으로 분리 예정 |
| Cross-Tier | exaone ≥ Haiku > Flash (포커). Cloud-SLM 벽 없음 |
| Deduction | Sonnet 3/3 범인 정답, 한글 vs 영어 비교 완료 |
| 논문 | Paper #2 submitted, Paper #3 deferred |

다음 단계: Deduction 채점 개선 → Cross-model 비교 → Codenames SLM (Ray) → pip install lxm

---

*LxM Research Notes — Public Health Observations v0.3*
*이 문서는 LxM 실험에서 발견된 집단/생태학적 관찰의 기록. 심화 분석은 Model Medicine 프로젝트에서.*
