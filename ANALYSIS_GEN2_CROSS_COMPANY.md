# Gen 2 Cross-Company 종합 분석

**Date:** 2026-03-31
**Analyst:** Luca

---

## Cross-Company 결과 종합

### mystery_005 (횡령)

| 모델 | 회사 | Tier | 범인 | 3/3 | 특징 |
|------|------|------|------|-----|------|
| Opus | Claude | Top | 3/3 | 1/3 | method 불안정 |
| G 2.5 Pro | Gemini | Top | **1/3** | 0/3 | **A로 2회 오답** |
| Sonnet | Claude | Mid | 3/3 | 0/3 | motive 전멸 |
| G 3 Flash | Gemini | Mid | 3/3 | **3/3** | **완벽** |
| Haiku | Claude | Low | 2/3 | 0/3 | A로 1회 오답 |

### mystery_006 v2 (실종)

| 모델 | 회사 | Tier | 범인 | 3/3 | 특징 |
|------|------|------|------|-----|------|
| Opus | Claude | Top | 3/3 | 3/3 | 완벽 |
| G 2.5 Pro | Gemini | Top | **1/3** | 1/3 | **B로 2회 오답** |
| Sonnet | Claude | Mid | 3/3 | 3/3 | 완벽 |
| G 3 Flash | Gemini | Mid | 2/3 | 2/3 | timeout 1회 |
| Haiku | Claude | Low | 2/3 | 2/3 | B로 1회 오답 |

---

## SDI 재계산 (Cross-Company 5모델)

기존 SDI는 Claude 3모델 + SLM 가정이었지만, 이제 5모델 실측 데이터가 있으므로 재계산합니다.

### 가중치 (5모델)

| 모델 | Tier | 가중치 | 근거 |
|------|------|--------|------|
| Opus | Top | 0.10 | 최상위, 변별력 낮음 |
| G 2.5 Pro | Top | 0.10 | 최상위 |
| Sonnet | Mid | 0.20 | 중상위 |
| G 3 Flash | Mid | 0.20 | 중상위 |
| Haiku | Low | 0.20 | 중위, 민감 구간 |
| SLM-best | Floor | 0.20 | 최하위, 바닥 측정 |

### mystery_005 SDI (Cross-Company)

```
Opus: 3/3=1.0, G2.5Pro: 1/3=0.33, Sonnet: 3/3=1.0, G3Flash: 3/3=1.0, Haiku: 2/3=0.67, SLM: 0.0

Weighted = 0.10×1.0 + 0.10×0.33 + 0.20×1.0 + 0.20×1.0 + 0.20×0.67 + 0.20×0.0
         = 0.10 + 0.033 + 0.20 + 0.20 + 0.134 + 0.0
         = 0.667

SDI = 1 - 0.667 = 0.33 → Medium
```

### mystery_006 v2 SDI (Cross-Company)

```
Opus: 3/3=1.0, G2.5Pro: 1/3=0.33, Sonnet: 3/3=1.0, G3Flash: 2/3=0.67, Haiku: 2/3=0.67, SLM: 0.0

Weighted = 0.10×1.0 + 0.10×0.33 + 0.20×1.0 + 0.20×0.67 + 0.20×0.67 + 0.20×0.0
         = 0.10 + 0.033 + 0.20 + 0.134 + 0.134 + 0.0
         = 0.601

SDI = 1 - 0.601 = 0.40 → Medium
```

### Claude-only vs Cross-Company SDI 비교

| 시나리오 | Claude-only SDI | Cross-Company SDI | 차이 |
|---------|----------------|-------------------|------|
| 005 | 0.40 | **0.33** | -0.07 (G3 Flash 완벽이 평균 올림) |
| 006 v2 | 0.40 | **0.40** | 0.00 (동일) |

**005는 cross-company에서 더 쉬워짐** — G3 Flash가 3/3 완벽으로 solve rate을 올림.
**006은 동일** — G2.5 Pro가 못 맞추지만 Sonnet이 완벽이라 상쇄.

---

## 핵심 발견 4개

### 1. Gemini 2.5 Pro가 추리에서 최하위 — "레드헤링 취약성"

| 시나리오 | G 2.5 Pro 범인 | 오답 패턴 |
|---------|--------------|----------|
| 005 | **1/3** | A(CFO)로 2회 오답 |
| 006 v2 | **1/3** | B(전 연인)로 2회 오답 |

**두 시나리오 모두 가장 뻔한 레드헤링에 빠짐.** 005에서는 "CFO가 승인했으니 범인", 006에서는 "전 연인이 방에 갔으니 범인" — 표면적 증거만 보고 교차검증을 안 하는 패턴.

**Model Medicine 연결:** 이건 Gemini 2.5 Pro의 Core 특성 — "표면적 내러티브에 취약"한 추론 스타일. Codenames에서 Gemini가 보수적 클루로 승리한 것과 대비되는 발견. **같은 모델이 언어 연상에서는 강하고 논리적 추론에서는 약하다** — 능력 축 독립성의 또 다른 증거.

### 2. Gemini 3 Flash > 2.5 Pro — Tier 역전 재현

| 시나리오 | G 3 Flash | G 2.5 Pro |
|---------|-----------|-----------|
| 005 | **3/3 완벽** | 1/3 |
| 006 v2 | 2/3 | 1/3 |

포커 Cross-Tier에서 exaone(SLM) ≥ Haiku > Flash였던 것처럼, 추리에서도 **Flash > Pro 역전.** "모델 크기 ≠ 추리 능력"이 Cross-Company에서도 재현.

이건 LxM Key Principle #2 "Behavioral Signatures > Model Size"의 또 다른 사례. 2.5 Pro가 3 Flash보다 파라미터가 크지만 추리에서는 역전.

### 3. 006이 005보다 확실히 어려움 (cross-company에서 확인)

Claude-only에서는 005=006=SDI 0.40이었지만:

| 지표 | 005 | 006 v2 |
|------|-----|--------|
| 완벽 모델 수 (범인 3/3) | 4/5 (Opus, Sonnet, Flash, ...) | 2/5 (Opus, Sonnet만) |
| 어떤 모델도 완벽 못한 지표 | 3/3 정답 비율 | Flash timeout, G2.5Pro B오답 |
| G 2.5 Pro 오답 패턴 | A(CFO) — 동기 기반 | B(전 연인) — 물증 기반 |

**006의 B 레드헤링(DNA모호화+물증추가)이 cross-company에서 강하게 작동.** G 2.5 Pro가 005에서는 동기 기반 오답, 006에서는 물증 기반 오답 — 두 가지 다른 함정에 모두 빠짐.

### 4. SLM 들어가면 SDI 차별화 확대 예상

JJ 의견대로, SLM은 거의 확실히 0/3일 것. 현재 SDI 공식에서 SLM=0.0으로 가정하고 있는데, 실측으로 확인되면:

| 시나리오 | 현재 SDI (SLM=0 가정) | SLM 실측 후 예상 |
|---------|---------------------|-----------------|
| 005 | 0.33 | 0.33 (변동 없음 — 이미 0 가정) |
| 006 | 0.40 | 0.40 (변동 없음) |
| 007 | ? | **SLM 0/3이면 SDI 상승에 기여** |

SLM 가중치(0.20)가 0을 유지하면 현재 SDI와 동일. **SLM이 SDI를 바꾸는 건 SLM이 1/3 이상 맞출 때** — 이건 Gen 2 구조에서 mistral만 가능할 수도.

다만 007은 **KTX 교차검증이라는 비직관적 추론**이 필요하므로 SLM은 확실히 0/3. 007의 SDI는 주로 Sonnet과 G 2.5 Pro의 성적에 달려 있음.

---

## Cross-Company Deduction 서열

| 순위 | 모델 | 005 범인 | 006 범인 | 평균 |
|------|------|---------|---------|------|
| 1 | G 3 Flash | 3/3 | 2/3 | **83%** |
| 2 | Opus | 3/3 | 3/3 | **100%** (but method 불안정) |
| 2 | Sonnet | 3/3 | 3/3 | **100%** (but motive 불안정) |
| 4 | Haiku | 2/3 | 2/3 | **67%** |
| 5 | **G 2.5 Pro** | **1/3** | **1/3** | **33%** |

**Gemini 2.5 Pro가 Deduction에서 Haiku보다 못함.** Top Tier 모델이 Low Tier보다 추리를 못 하는 역전.

이건 Cross-Game 서열 비교에서 또 하나의 데이터 포인트:
- Chess: Gemini >> Claude
- Codenames: Gemini > Claude
- Poker: Claude >> Gemini
- **Deduction: Claude >> Gemini** (추론 기반 게임에서 Claude 우세)

---

## 007 예상 (Cross-Company)

| 모델 | 예상 | 근거 |
|------|------|------|
| Opus | 2-3/3 | 교차검증 가능하나 A 레드헤링이 역대 최강 |
| G 2.5 Pro | **0/3** | 005, 006 모두 레드헤링에 빠짐 → A(보험)에 확실히 빠질 것 |
| Sonnet | 1-2/3 | KTX 교차 가능 여부가 관건 |
| G 3 Flash | 1-2/3 | 005에서 완벽했지만 007 알리바이가 훨씬 복잡 |
| Haiku | 0-1/3 | A 또는 E로 오답 예상 |
| SLM | 0/3 | 확실 |

**예상 SDI (Cross-Company):**
```
Opus 2/3=0.67, G2.5Pro 0/3=0, Sonnet 1/3=0.33, Flash 1/3=0.33, Haiku 0/3=0, SLM 0/3=0

Weighted = 0.10×0.67 + 0.10×0 + 0.20×0.33 + 0.20×0.33 + 0.20×0 + 0.20×0
         = 0.067 + 0 + 0.066 + 0.066 + 0 + 0
         = 0.199

SDI = 1 - 0.199 = 0.80 → ★★★★ Extreme?!
```

만약 Sonnet과 Flash가 2/3으로 올라가도:
```
SDI = 1 - (0.067 + 0 + 0.133 + 0.133 + 0 + 0) = 1 - 0.333 = 0.67 → Hard
```

**007은 SDI 0.60-0.80 범위에 들어올 가능성이 높다.** G 2.5 Pro의 일관된 레드헤링 취약성이 SDI를 확실히 올려줌.

---

## Key Principle 업데이트 제안

기존: "No Universal Winner" — across games
추가: **"No Universal Winner — across reasoning types within same game."**

같은 Deduction 게임인데 005(디지털 포렌식)와 006(타임라인 재구성)에서 모델 서열이 다름:
- 005: Flash > Opus > Sonnet > Haiku > G2.5Pro
- 006: Opus = Sonnet > Haiku = Flash > G2.5Pro

**추론 유형(reasoning type)이 달라지면 같은 게임 내에서도 서열이 바뀐다.**

---

*Cross-company 분석 완료. 007 결과 대기. G 2.5 Pro의 일관된 레드헤링 취약성이 SDI 차별화의 핵심 변수.*
