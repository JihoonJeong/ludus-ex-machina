# mystery_006 Phase 1 결과 분석

**Date:** 2026-03-31
**Analyst:** Luca

---

## 결과 요약

| 모델 | Run 1 | Run 2 | Run 3 | 범인 | 동기 | 방법 | 평균 파일 |
|------|-------|-------|-------|------|------|------|----------|
| Opus | 2/3 (16) | 2/3 (16) | 1/3 (16) | 3/3 | 2/3 | 0/3 | 16.0 |
| Sonnet | 2/3 (13) | 2/3 (13) | 2/3 (16) | 3/3 | 3/3 | 0/3 | 14.0 |
| Haiku | 2/3 (16) | 1/3 (16) | 1/3 (9) | 3/3 | 1/3 | 0/3 | 13.7 |

**3/3 완벽 정답: 0/9 (0%)**
**method 정답: 0/9 (0%) — 전원 blunt_force_and_ocean_disposal 선택**

---

## SDI 계산 — 이중 기준 필요

### 기준 1: 범인(culprit) 기준 (기존 방식)

```
Opus: 3/3 = 1.0, Sonnet: 3/3 = 1.0, Haiku: 3/3 = 1.0, SLM: 0/3 = 0.0 (가정)
SDI = 1 - (0.15×1.0 + 0.25×1.0 + 0.30×1.0 + 0.30×0.0) = 1 - 0.70 = 0.30 → Medium
```

### 기준 2: 완벽 정답(3/3) 기준

```
Opus: 0/3 = 0.0, Sonnet: 0/3 = 0.0, Haiku: 0/3 = 0.0, SLM: 0/3 = 0.0
SDI = 1 - 0.0 = 1.00 → Extreme
```

**범인은 쉬운데 component가 극도로 어려움.** SDI를 어떤 기준으로 쓰느냐에 따라 0.30(Medium) ~ 1.00(Extreme) 사이. 이 괴리 자체가 006의 특성.

---

## 핵심 발견

### 1. method 전멸 — 선택지 문제인가, 추론 실패인가?

9매치 전부 `blunt_force_and_ocean_disposal` 선택. 정답은 `cliff_staged_suicide`.

**모델의 추론 경로 (추정):**
- laundry_forensic → A의 옷에 피해자 혈흔 → "물리적 접촉/폭력이 있었다"
- phone_location → 폰이 절벽으로 이동 → "절벽에서 뭔가 발생"
- tide_chart → 이안류로 시신 유실 → "바다에 버렸다"
- 결론: 때리고(blunt force) → 바다에 버렸다(ocean disposal) ✓

**정답의 의미:**
- cliff_staged_suicide = "자살로 위장하기 위해 절벽에서 떨어뜨렸다"
- 핵심 차이: **의도(staging)** vs **수단(disposal)**

**진단: 005와 동일한 선택지 모호성 문제.** 물리적 행위는 동일한데(절벽에서 바다로), 선택지가 "왜 그렇게 했는가(위장)"와 "무엇을 했는가(투기)"를 구분하고 있음. evidence에서 "자살 위장" 의도를 명시적으로 보여주는 파일이 없으므로, 모델이 물리적 행위만으로 판단 → blunt_force 선택.

**해결 방안:**

**(A) 선택지 수정** — blunt_force_and_ocean_disposal을 빼고 cliff_staged_suicide과 겹치지 않는 선택지로 교체:
- `cliff_staged_suicide` (절벽 추락 위장 자살) — 유지
- `drugging_and_abandonment` (약물 투여 후 유기) — 유지
- ~~`blunt_force_and_ocean_disposal`~~ → `strangling_and_burial` (교살 후 매장)
- `vehicle_transport_to_coast` (차량 이용 해안 이동) — 유지
- `hired_accomplice` (공범 고용) — 유지

**(B) evidence 보강** — "자살 위장" 의도를 시사하는 증거 추가:
- 예: 윤세진의 우울증 치료 기록을 A가 검색한 브라우저 히스토리
- 예: A가 "자살 보험금 면책" 관련 법률 상담을 받은 기록
- 이러면 "위장" 의도가 evidence에서 드러남

**추천: (A) + (B) 병행.** 선택지 수정으로 모호성 해소 + evidence 1개 추가로 "위장" 의도를 evidence-backed으로 만들기.

### 2. 범인 전원 정답 — laundry_forensic이 너무 결정적

006의 역설: culprit은 005보다 쉬움(100% vs 89%), 하지만 component는 훨씬 어려움.

원인: `laundry_forensic.md`가 A를 직접 지목하는 DNA 증거. 이걸 읽으면 A가 범인인 건 확실. B(전 연인) 레드헤링은 circumstantial evidence 수준이라 DNA 앞에서 무력.

**B 레드헤링 오답 0회 → 레드헤링이 culprit 수준에서는 약함.** 대신 motive/method에서 혼란 유도는 성공.

### 3. motive 분산 — 보험 vs 저작권

| 모델 | insurance_payout | copyright_dispute |
|------|-----------------|-------------------|
| Opus | 2/3 | 1/3 |
| Sonnet | 3/3 | 0/3 |
| Haiku | 1/3 | 2/3 |

insurance_policy와 copyright_lawsuit 모두 A의 동기를 지지하는 evidence → 모델이 어느 쪽을 더 무겁게 보는지에 따라 갈림. 이건 Gen 2 의도대로의 분산이며, **005 Sonnet divorce_settlement 미열람과 다른 패턴** — 여기서는 둘 다 읽되 해석이 갈리는 것.

### 4. Exploration Depth — 005 대비 극적 상승

| | 005 | 006 |
|---|---|---|
| Opus 평균 파일 | 4.0/10 | 16.0/16 |
| Sonnet 평균 파일 | 3.0/10 | 14.0/16 |
| Haiku 평균 파일 | 8.3/10 | 13.7/16 |

006에서는 거의 전체 파일을 읽음. **증거 16개 = 파일 수 자체가 탐색을 강제.** case_brief에 정보가 적으므로 "아는 것이 없어서 더 많이 읽어야 한다"는 구조.

**005와의 차이:** 005는 server_access_log 하나로 범인 특정 가능 → 적게 읽어도 됨. 006은 어떤 단일 파일도 결정적이지 않아서(laundry_forensic 제외) 많이 읽게 됨.

### 5. 005 vs 006 비교 — Gen 2 SDI 차별화

| 지표 | 005 (Medium) | 006 (Hard) | 차별화 |
|------|-------------|------------|--------|
| 범인 정답률 | 89% | 100% | 역전 (006이 쉬움) |
| 완벽 정답(3/3) | 11% | 0% | ✅ 차별화 |
| method 정답률 | 44% | 0% | ✅ 극적 차별화 |
| 평균 파일 읽기 | 5.2 | 14.1 | ✅ 탐색 행동 차별화 |
| Component Difficulty | 0.45 | **0.83** | ✅ 차별화 |

**범인만 보면 차별화 실패, component까지 보면 차별화 성공.** → SDI 공식에 component 가중치를 포함해야 하는 근거.

---

## SDI 공식 개선 제안

현행: `SDI = 1 - Weighted_Culprit_Solve_Rate`

제안: **Composite SDI**

```
SDI_composite = 1 - (w_culprit × Culprit_Rate + w_component × Component_Rate)

여기서:
  w_culprit = 0.6 (범인 가중치)
  w_component = 0.4 (동기+방법 가중치)
  Component_Rate = (motive_rate + method_rate) / 2
```

**005 Composite SDI:**
```
Culprit: (1.0+1.0+0.67+0.0)/weighted = 0.60
Component: motive ~0.22, method ~0.44 → avg 0.33 → weighted ~0.20
SDI_composite = 1 - (0.6×0.60 + 0.4×0.20) = 1 - 0.44 = 0.56
```

**006 Composite SDI:**
```
Culprit: (1.0+1.0+1.0+0.0)/weighted = 0.70
Component: motive ~0.67, method 0.0 → avg 0.33 → weighted ~0.20
SDI_composite = 1 - (0.6×0.70 + 0.4×0.20) = 1 - 0.50 = 0.50
```

→ 이래도 005(0.56)와 006(0.50)이 비슷... **method 전멸이 선택지 문제이므로 패치 후 재측정이 필요.**

---

## 액션 아이템

### 즉시 (method_options 패치)

**006 EN + KO scenario.json 수정:**
```
변경: blunt_force_and_ocean_disposal → strangling_and_burial
KO: 둔기 가격 후 해안 투기 → 교살 후 매장
```

### 추가 evidence 검토

"자살 위장" 의도를 보여주는 evidence 1개 추가 고려:
- `browser_history.md` — A의 검색 기록: "자살 보험금 지급 조건", "절벽 추락 사고 사례", "실종 선고 기간"
- 이러면 A가 단순히 폭행+유기가 아니라 의도적으로 자살로 위장하려 했음이 드러남

### SLM 테스트

패치 후 006 재측정 필요. SLM(mistral) 테스트는 패치 후 진행.

### 007 설계

005(0.40) vs 006(패치 후 재측정) 결과 확인 후 007 착수.

---

*006은 "culprit은 쉽지만 component는 극도로 어려운" 비대칭 시나리오. method_options 패치 + evidence 보강 후 재측정 필요.*
