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

## 8. SLM Codenames — Cloud-SLM Wall is Ability-Dependent (2026-03-29)

**Source:** Ray, Windows Lab. 4 SLM models (exaone, mistral, llama, qwen3), Codenames round-robin, 29 games.

### The Finding

SLM은 Codenames를 거의 못 한다.

| 결과 | 비율 |
|------|------|
| Assassin 히트 | 52% |
| Unknown (턴 제한 초과) | 45% |
| 정상 완료 | **3%** (1/29) |

전체 타임아웃 54% (687/1273). qwen3 Spymaster가 332회 타임아웃으로 거의 작동 불능.

### SLM Codenames 리더보드

| 모델 | 승률 | Assassin 히트 |
|------|------|---------------|
| mistral | 40% | 5 |
| exaone | 29% | 6 |
| llama | 21% | 2 |
| qwen3 | 20% | 2 |

### Cross-Game 서열 비교

| | 포커 1v1 | 포커 4인 | Codenames | Deduction (Cloud) |
|---|---|---|---|---|
| 1위 | exaone | qwen3 | mistral | Opus |
| 2위 | mistral | llama | exaone | Sonnet=Haiku |
| 3위 | llama | mistral≈exaone | llama | |
| 4위 | qwen3 | | qwen3 | |

**4개 게임, 4개 다른 서열.** 만능 모델은 없다. 게임마다 요구하는 능력 축이 다르고, 같은 모델이 어떤 게임에서는 1위, 다른 게임에서는 꼴찌.

### Interpretation

**Cloud-SLM 벽은 능력 축에 따라 완전히 다르다:**

| 능력 축 | Cloud-SLM 벽 | 근거 |
|---------|-------------|------|
| 구조적 추론 (포커) | **없음** | exaone ≥ Haiku > Flash |
| 언어 연상 (Codenames) | **절대적** | SLM 정상 완료 3% vs Cloud 정상 작동 |
| 논리 추론 (Deduction) | **있음** | Opus 3/3, Sonnet=Haiku 1/3 |

포커에서 "모델 크기 ≠ 게임 능력"이었지만, Codenames에서는 모델 크기(또는 언어 학습량)가 결정적. 7-8B SLM은 "한 단어로 여러 카드를 연결하는 연상"이라는 핵심 능력이 부족.

### Key Principle 업데이트

기존 #8: "Cloud-SLM wall is game-dependent — Does not exist in poker"
수정 → "Cloud-SLM wall is ability-dependent — absent in structural reasoning (poker), absolute in language association (Codenames), present in logical deduction"

### Cross-Tier Codenames 실험 취소

SLM 정상 완료 3%이므로 Cloud와 비교 자체가 무의미. 실험 2 (SLM vs Haiku/Flash Codenames)는 진행하지 않음.

---

## 9. SLM Deduction — Cloud-SLM Wall is a Gradient (2026-03-30)

**Source:** Ray, Windows Lab. 4 SLM models × mystery_001 (Phase 1), mistral × 3 scenarios (Phase 2).

### Phase 1: Easy Screening (mystery_001 × 4 SLM × 3회)

| 모델 | 평균점수 | 범인 정답 | 동기 정답 | 방법 정답 | 평균 파일 수 |
|------|---------|----------|----------|----------|------------|
| mistral (7B) | 1.69 | 2/3 | 0/3 | 3/3 | 11.7/12 |
| qwen3 (8B) | 0.99 | 0/3 | 0/3 | 2/3 | 0.7/12 |
| llama31 (8B) | 0.97 | 0/3 | 0/3 | 2/3 | 1.0/12 |
| exaone35 (7.8B) | 0.97 | 0/3 | 0/3 | 2/3 | 1.0/12 |

### Phase 2: mistral 난이도 확장

| 시나리오 | 난이도 | 평균점수 | 범인 | 동기 | 방법 | 평균 파일 |
|---------|-------|---------|------|------|------|----------|
| mystery_001 | Easy | 1.69 | 2/3 | 0/3 | 3/3 | 11.7/12 |
| mystery_002 | Medium | 0.48 | 0/3 | 0/3 | 1/3 | 3.0/11 |
| mystery_003 | Hard | 1.95 | 0/3 | 2/3 | 2/3 | 0.7/14 |

### 핵심 발견

**1. Cloud-SLM 벽은 연속 스펙트럼이다:**

| 게임 | 능력 축 | Cloud-SLM 벽 |
|------|---------|-------------|
| 포커 | 구조적 추론 | **없음** (exaone ≥ Haiku) |
| Deduction | 논리적 추론 + 증거 종합 | **부분적** (Easy만 가능, 1개 모델만) |
| Codenames | 언어 연상 | **절대적** (SLM 3% 성공) |

벽은 이진(있다/없다)이 아니라 gradient — "없음 → 부분적 → 절대적"의 연속선.

**2. Exploration Behavior (탐색 행동) — 새로운 측정 차원:**

| 모델 | 평균 파일 읽기 (001) | 범인 정답 |
|------|---------------------|----------|
| mistral | 11.7/12 | 2/3 ✅ |
| llama | 1.0/12 | 0/3 ❌ |
| exaone | 1.0/12 | 0/3 ❌ |
| qwen3 | 0.7/12 | 0/3 ❌ |

exaone/llama/qwen3는 증거를 거의 안 읽고 바로 답 제출. "읽고 → 추론하고 → 제출하라"는 지시의 "읽기" 단계를 건너뜀. 추론 능력 부족이 아니라 **instruction following 패턴의 차이.**

mistral의 차별점: 체계적 탐색. 증거를 거의 전부 읽고(11.7/12), 그 위에서 추론. Codenames SLM에서도 mistral 1위 — mistral의 Core 특성은 "지시를 충실히 따르는 것."

**한글 실험과의 연결:** Section 6에서 한글로 바꾸면 같은 모델이 7배 더 탐색. 이번엔 모델을 바꾸면 16배 차이(0.7 vs 11.7). **탐색 행동은 Hardware Shell(언어)과 Core(모델) 모두에 의해 조절됨.**

**3. SLM 서열: 4게임 4서열**

| 순위 | 포커 1v1 | 포커 4인 | Codenames | Deduction |
|------|---------|---------|-----------|----------|
| 1위 | exaone | qwen3 | mistral | **mistral** |
| 2위 | mistral | llama | exaone | (나머지 동률) |
| 3위 | llama | mistral≈exaone | llama≈qwen3 | |
| 4위 | qwen3 | | | |

Key Principle #1 "만능 모델 없음"이 SLM 레벨에서도 재현.

**4. mystery_003 높은 점수의 함정:**
mistral 003(Hard) 1.95점이지만 범인 0/3, 증거 0.7개. 동기/방법을 찍어서 맞춘 것. 선택지 5개 중 랜덤 기대값 20%이므로 2/3 정답은 통계적으로 설명 가능. **점수만 보면 오해 — 탐색 행동과 범인 정답률을 함께 봐야 실력 측정.**

### Key Principle 업데이트

기존 #8 수정 → **"Cloud-SLM wall is a gradient: absent in structural reasoning (poker), partial in logical deduction (Easy only, mistral only), absolute in language association (Codenames)."**

추가 원칙: **"Exploration Behavior is a measurable Core trait."** 같은 지시를 받아도 모델마다 탐색 깊이가 16배 차이. RLHF 스타일의 직접적 행동 발현이며, Deduction Game이 이를 정량화하는 유효한 도구.

---

## 10. SDI 보정 실패 → 시나리오 구조적 원칙 발견 (2026-03-30)

**Source:** Cody, SDI 보정 84매치 (Claude 36 + Gemini/OpenAI 48)

### 발견: SDI가 차별화 안 됨

| 시나리오 | SDI | 문제 |
|---------|-----|------|
| mystery_001 | 0.80 (Extreme) | Claude 못 푸는데 GPT-5.4는 파일 0개로 풀 |
| mystery_002 | 0.30 (Medium) | 전부 동일 |
| mystery_003 | 0.30 (Medium) | 전부 동일 |
| mystery_004 | 0.30 (Medium) | 전부 동일 |

### 근본 원인: 증거 구조의 일방성

case_brief 정보량은 "표면적 난이도"를 조절하지만, **진짜 난이도는 "증거 구조"가 결정.**

- 3명 용의자 중 증거가 한 명에게 압도적으로 집중
- 다른 용의자의 혐의가 너무 약해서 즉시 배제 가능
- evidence 아무 거나 읽어도 범인이 튀어나오는 구조
- brief를 줄여도 정보 분포 자체가 편향되어 있으면 난이도 조절 불가

### 발견된 3대 구조 원칙

SDI가 의미 있으려면 시나리오가 다음을 충족해야 함:

1. **용의자 4-5명** — 확률 자체를 낮춤 (3명은 33% 랜덤, 5명은 20%)
2. **동등한 혐의 분산** — 최소 2명이 "이 사람이 범인일 수 있다"는 수준의 증거
3. **범인 증거에 모순** — 범인을 가리키는 증거와 범인 무죄 증거가 공존

### Generation 1 vs Generation 2

| | Generation 1 (001-004) | Generation 2 (신규) |
|---|---|---|
| 용의자 | 3명 | 4-5명 |
| 증거 구조 | 일방적 | 분산 + 모순 |
| SDI 보정 | 무의미 | 의미 있음 |
| 용도 | SLM 테스트, 기본 벤치마크 | SDI/DQ 표준화 도구 |

Gen 1은 유지 (폐기 아님). SLM 테스트, 탐색 행동 측정, 기본 벤치마크로는 여전히 유효.
Gen 2를 설계하고 SDI/DQ 보정은 Gen 2에서만 진행.

### Shell Engineering 연결

시나리오 구조(용의자 수, 증거 분포, 모순 여부)는 **Hardware Shell의 측정 가능한 파라미터.** 동일한 추리 능력을 가진 모델이라도 구조가 다르면 성적이 달라진다 — 이건 Hardware Shell 효과의 또 다른 사례.

---

## 11. SDI → DQ: IRT 프레임워크 (2026-03-30)

**발견:** SDI(시나리오 난이도 지수) 시스템이 심리측정학의 Item Response Theory(IRT)와 구조적으로 동치.

**핵심 인사이트:** 시나리오가 충분히 쌓이면(20개+), SDI로 보정된 시나리오 세트를 역으로 모델의 추리력을 단일 수치(DQ: Deduction Quotient)로 추정 가능. IQ 테스트와 동일한 수학적 구조.

**Creator Ecosystem이 스케일링 엔진:** 커뮤니티가 시나리오를 만들수록 문항(시나리오)이 늘고, 문항이 늘수록 DQ 정밀도가 올라감. 콘텐츠가 곧 측정 도구.

**MTI 연결:** DQ는 MTI의 "추론 능력" 차원에 직접 입력. 다른 LxM 게임들도 동일 프레임 적용 가능 (포커=전략, Codenames=언어, Avalon=사회적 추론). MTI 분리 시 인수인계 대상.

**상세 설계:** `LXM_SCENARIO_DIFFICULTY_INDEX.md` Section 8 참조.

---

## 12. Data Pipeline Notes (renumbered)

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

## 13. Generation 2 Deduction — SDI 차별화 달성 (2026-03-31)

**Source:** Gen 2 시나리오 3개 × 5모델 × 3회 = 45매치 (Cross-Company)

### Gen 1 → Gen 2 전환

Gen 1 (001-004): 3명 용의자 + 일방적 증거 → SDI 전부 0.30 동일. 난이도 차별화 실패.

**Gen 2 3대 원칙:**
1. 용의자 4-5명
2. 동등한 혐의 분산 (최소 2명이 "범인급" 증거)
3. 범인 증거에 모순 (유죄+무죄 공존)

### SDI 결과

| 시나리오 | 장르 | 용의자 | SDI (Cross-Company) | 등급 |
|---------|------|--------|-------------------|------|
| 005 The Vanishing Fund | 횡령 | 4명 | **0.33** | ★★☆ Medium |
| 006 v2 The Jeju Disappearance | 실종 | 5명 | **0.40** | ★★☆ Medium |
| 007 The Burning Gallery | 방화+절도 | 5명 | **0.77** | ★★★ Hard |

**Gen 1(0.30 균일) → Gen 2(0.33-0.40-0.77). SDI 차별화 성공.**

### Cross-Company 서열

| 순위 | 모델 | 005 | 006 | 007 | 평균 |
|------|------|-----|-----|-----|------|
| 1 | Opus | 3/3 | 3/3 | 1/3 | 78% |
| 1 | G 3 Flash | 3/3 | 2/3 | 2/3 | 78% |
| 3 | Sonnet | 3/3 | 3/3 | 0/3 | 67% |
| 4 | Haiku | 2/3 | 2/3 | 1/3 | 56% |
| 5 | G 2.5 Pro | 1/3 | 1/3 | 0/3 | **22%** |

### mystery_007 — A(보험사기) 레드헤링 대성공

- A 오답률: **60% (15회 중 9회)**
- Sonnet 0/3 전멸 — 3-4파일만 읽고 A 직행
- Opus 1/3 — 16파일 전부 읽고도 2/3 A 오답
- G 2.5 Pro 0/3 — C(표절)로 2회, A로 1회
- method 전원 정답 (9/9) — 선택지 직교성 검증

### SDI 핵심 레버: 레드헤링 강도

| 시나리오 | 레드헤링 대상 | 오답률 (15회) | SDI |
|---------|-------------|-------------|-----|
| 005 | A(CFO) | 20% | 0.33 |
| 006 | B(전 연인) | 20% | 0.40 |
| 007 | A(보험)+C(표절) | **60%** | **0.77** |

레드헤링 오답률과 SDI가 거의 정비례 — **레드헤링 내러티브의 설득력이 SDI의 가장 강력한 조절 변수.**

---

## 14. Deduction 측정 차원 — 3축 독립 모델 (2026-03-31)

### 14.1 Exploration Depth (탐색 깊이) — 얼마나 읽느냐

Sonnet: 일관되게 3-4파일 (효율 전략). Haiku/Opus: 시나리오에 따라 전부 읽음.

### 14.2 Exploration Strategy (탐색 전략) — 무엇을 읽느냐

005 Sonnet: server_access_log → ip_trace (범인 맞춤, 동기 실패 — divorce_settlement 미열람).
007 Sonnet: insurance_detail → financial_crisis (A 직행). 같은 전략이 시나리오에 따라 성공/실패.

### 14.3 Reasoning Depth (추론 깊이) — 읽은 것을 얼마나 깊이 추론하느냐

007 Opus: 16파일 전부 읽고(Depth 최대), 핵심 파일 모두 포함(Strategy 최적), 그런데도 2/3 A 오답.
알리바이를 액면 그대로 수용하고 "이 알리바이가 깨질 수 있는가?" → KTX 교차 추론까지 미도달.

### 3축 독립성

| 모델 | Depth | Strategy | Reasoning | 007 결과 |
|------|-------|----------|-----------|---------|
| Opus | 최대 | 최적 | **부족** | 1/3 |
| Sonnet | **최소** | 편향 | N/A | 0/3 |
| G 3 Flash | 높음 | 양호 | **충분** | 2/3 |

---

## 15. 레드헤링 취약 유형 — 회사 간 Core 편향 (2026-03-31)

### 007 오답 패턴

| 오답 대상 | Claude | Gemini |
|----------|--------|--------|
| A (보험사기 — 절차적) | **8회** | 2회 |
| C (표절 — 감정적) | 0회 | **2회** |

**Claude = 절차적 레드헤링 취약** ("서명 있음", "보험 가입", "승인 기록" 과대평가).
**Gemini = 감정적 레드헤링 취약** ("표절 분쟁", "전 연인", "해고" 내러티브에 끌림).

RLHF 스타일의 회사 간 차이가 추론 편향으로 발현. Model Medicine: **Core 수준의 Reasoning Bias.**

### Cross-Game 편향 일관성

| 게임 | Claude 편향 | Gemini 편향 |
|------|-----------|-----------|
| Codenames | 공격적 클루 | 보수적 클루 |
| Poker | 블러핑 선호 | 폴드 선호 |
| **Deduction** | **절차적 증거 과신** | **감정적 내러티브 과신** |

---

## 16. SLM Gen 2 Deduction — 81매치 결과 (2026-03-31)

**Source:** Ray, Windows Lab. 9 SLM × 3 Gen 2 시나리오 × 3회 = 81매치.

### 9모델 종합

| Model | Size | Culprit% | Motive% | Method% | Avg Files |
|-------|------|----------|---------|---------|-----------|
| gemma2 | 9B | **44.4%** | 22.2% | 22.2% | **8.2** |
| mistral | 7B | 33.3% | 22.2% | 33.3% | 5.0 |
| phi4-mini | 3.8B | 22.2% | 0% | 22.2% | 1.0 |
| exaone3.5 | 7.8B | 22.2% | 11.1% | 22.2% | 0.9 |
| qwen3 | 8B | 11.1% | 22.2% | 66.7% | 0.4 |
| deepseek-r1 | 8B | 11.1% | 0% | 22.2% | 3.0 |
| llama3.1 | 8B | 11.1% | 22.2% | 22.2% | 1.0 |
| gemma3 | 4B | 0% | 0% | 0% | 0.9 |
| smollm2 | 1.7B | 0% | 0% | 0% | 0.1 |

### 핵심 발견

**1. gemma2 = 새로운 SLM Deduction 챔피언.**
Gen 1에서는 mistral만 풀었지만, Gen 2에서 gemma2(9B)가 44.4%로 1위. 8.2파일 탐색은 SLM 중 압도적.

**2. Exploration Depth → Culprit% 재확인 (9모델 스케일).**
Gen 1의 4모델 발견(Section 9)이 9모델로 재현. 탐색 깊이와 범인 정답률의 상관이 가장 강력한 예측 변수.

**3. 레드헤링 효과의 전제조건 — "읽어야 속는다".**
Cloud: 007에서 60% A오답(증거를 읽고 레드헤링에 빠짐). SLM: A오답 거의 없음 — 증거를 충분히 안 읽어서 레드헤링에 노출 자체가 안 됨. 실패 모드가 근본적으로 다르다. Cloud = Reasoning Failure, SLM = Engagement Failure.

**4. deepseek-r1 역설 — "Reasoning 모델 ≠ Deduction 모델".**
3.0파일 읽지만 11.1% 범인. 수학/코딩 최적화된 Chain-of-Thought가 증거 종합 추론으로 전이되지 않음.

**5. mistral 난이도 역전.**

| | 005 (Easy) | 006 (Med) | 007 (Hard) |
|---|---|---|---|
| Cloud 평균 | 80% | 73% | 27% |
| gemma2 | 67% | 67% | 0% |
| **mistral** | **33%** | **0%** | **67%** |

Cloud/gemma2는 난이도-정답률 정비례. mistral은 역전 — Hard(007)에서 최고 성적. 가설: 체계적 탐색이 레드헤링이 강한 시나리오에서 모순 발견 기회를 높임.

**6. 5게임 SLM 서열 업데이트.**

| 순위 | 포커1v1 | 포커4인 | Codenames | Deduction Gen1 | Deduction Gen2 |
|------|---------|---------|-----------|---------------|---------------|
| 1위 | exaone | qwen3 | mistral | mistral | **gemma2** |
| 2위 | mistral | llama | exaone | (동률) | mistral |
| 3위 | llama | mistral≈exaone | llama | | phi4≈exaone |

5게임 5서열. Key Principle #1 "만능 모델 없음" SLM에서 완전 재현.

### SDI 업데이트 (v2 → v3)

SLM-pool = Functional Engagement 기준(Avg Files ≥ 2.0) 통과 모델 평균: gemma2, mistral, deepseek-r1.

| 시나리오 | SDI v2 | SDI v3 | 등급 변화 |
|---------|--------|--------|----------|
| 005 | 0.33 | **0.24** | Medium → **Easy** |
| 006 v2 | 0.40 | **0.36** | Medium (유지) |
| 007 | 0.77 | **0.72** | Hard (유지) |

상세: `LXM_SCENARIO_DIFFICULTY_INDEX.md` (v3) 참조.

---

## 17. Platform Status (2026-03-31)

| 항목 | 상태 |
|------|------|
| 게임 | 7개 (TicTacToe, Chess, Trust Game, Codenames, Poker, Avalon, Deduction) |
| 시나리오 | **7개** (Gen1: 001-004, Gen2: 005-007), **EN+KO=14** |
| 어댑터 | 5개 (Claude, Gemini CLI, Codex CLI, Ollama, Rule Bot) |
| Deduction Gen 2 | **SDI 0.24-0.72 확정. Cross-Company 5모델 + SLM 9모델 = 126매치 검증** |
| SDI | **v3 확정** — SLM-pool (Functional Engagement 기준), Cloud/SLM 실패 모드 분리 명시 |
| Phase C 서버 | P0 완료 |

다음 단계: Phase C P1 (리플레이 서빙) → GitHub public

---

*LxM Research Notes — Public Health Observations v0.8*
*이 문서는 LxM 실험에서 발견된 집단/생태학적 관찰의 기록. 심화 분석은 Model Medicine 프로젝트에서.*
