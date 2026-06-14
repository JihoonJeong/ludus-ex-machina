# 연구 노트 v0.7 추가 섹션 — Section 12-15

**이 파일의 내용을 LXM_RESEARCH_NOTES_PUBLIC_HEALTH.md의 Section 12 이후에 추가하고, 기존 Section 13(Platform Status)을 Section 15로 교체.**
**버전 표기: v0.6 → v0.7**

---

## 12. Generation 2 Deduction — SDI 차별화 달성 (2026-03-31)

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

## 13. Deduction 측정 차원 — 3축 독립 모델 (2026-03-31)

### 13.1 Exploration Depth (탐색 깊이) — 얼마나 읽느냐

Sonnet: 일관되게 3-4파일 (효율 전략). Haiku/Opus: 시나리오에 따라 전부 읽음.

### 13.2 Exploration Strategy (탐색 전략) — 무엇을 읽느냐

005 Sonnet: server_access_log → ip_trace (범인 맞춤, 동기 실패 — divorce_settlement 미열람).
007 Sonnet: insurance_detail → financial_crisis (A 직행). 같은 전략이 시나리오에 따라 성공/실패.

### 13.3 Reasoning Depth (추론 깊이) — 읽은 것을 얼마나 깊이 추론하느냐

007 Opus: 16파일 전부 읽고(Depth 최대), 핵심 파일 모두 포함(Strategy 최적), 그런데도 2/3 A 오답.
알리바이를 액면 그대로 수용하고 "이 알리바이가 깨질 수 있는가?" → KTX 교차 추론까지 미도달.

### 3축 독립성

| 모델 | Depth | Strategy | Reasoning | 007 결과 |
|------|-------|----------|-----------|---------|
| Opus | 최대 | 최적 | **부족** | 1/3 |
| Sonnet | **최소** | 편향 | N/A | 0/3 |
| G 3 Flash | 높음 | 양호 | **충분** | 2/3 |

---

## 14. 레드헤링 취약 유형 — 회사 간 Core 편향 (2026-03-31)

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

## 15. Platform Status (2026-03-31)

| 항목 | 상태 |
|------|------|
| 게임 | 7개 (TicTacToe, Chess, Trust Game, Codenames, Poker, Avalon, Deduction) |
| 시나리오 | **7개** (Gen1: 001-004, Gen2: 005-007), **EN+KO=14** |
| 어댑터 | 5개 (Claude, Gemini CLI, Codex CLI, Ollama, Rule Bot) |
| Deduction Gen 2 | **SDI 0.33-0.77. Cross-Company 5모델 45매치 검증** |
| Phase C 서버 | P0 완료 |

다음 단계: SLM Gen 2 테스트 → SDI 확정 → Phase C P1 → GitHub public
