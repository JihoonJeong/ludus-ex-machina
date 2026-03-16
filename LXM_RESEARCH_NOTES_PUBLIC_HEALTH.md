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

| Game | 1st | 2nd | 3rd | What determines ranking |
|------|-----|-----|-----|------------------------|
| Chess | ≈ tied | ≈ tied | ≈ tied | Core差 too small at Haiku level |
| Trust Game | All cooperate | — | — | No ranking (cooperative prior) |
| Codenames | Opus (70%) | Sonnet (30%) | Haiku (baseline) | Language + Theory of Mind |
| Poker Heads-up | Sonnet (47%) | Haiku (40%) | Opus (13%) | Unpredictability + aggression |
| Poker 4-player | Opus (50%) | Sonnet (30%) | Haiku (20%) | Rational decision-making |

**"Which model is best?" has no answer. It depends on the game — and possibly the player count, pending poker validation.** Codenames and Trust Game results are robust (50+ games with clear process metrics). Poker results are preliminary and may reflect variance rather than true skill differences.

---

## 6. Data Pipeline Notes (renumbered)

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

---

*LxM Research Notes — Public Health Observations v0.1*
*이 문서는 LxM 실험에서 발견된 집단/생태학적 관찰의 기록. 심화 분석은 Model Medicine 프로젝트에서.*
