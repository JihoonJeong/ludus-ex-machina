# Cody Brief — mystery_005 Cross-Model Test

**Date:** 2026-03-30
**From:** Luca
**Priority:** 1순위 — Gen 2 첫 시나리오 검증

---

## 목적

mystery_005 "The Vanishing Fund"는 Gen 2 첫 시나리오 (Easy 타겟).
Gen 2 3대 원칙(4명 용의자, 동등 혐의 분산, 범인 증거 모순)이 SDI 차별화를 만드는지 검증.

---

## 테스트 매트릭스

### Phase 1: Cloud 모델 (EN) — 즉시 실행

| 모델 | 시나리오 | 반복 | 소계 |
|------|---------|------|------|
| Opus | mystery_005 (EN) | 3회 | 3 |
| Sonnet | mystery_005 (EN) | 3회 | 3 |
| Haiku | mystery_005 (EN) | 3회 | 3 |

**Phase 1 소계: 9매치**

### Phase 2: KO 검증 — Phase 1 결과 확인 후

| 모델 | 시나리오 | 반복 | 소계 |
|------|---------|------|------|
| Sonnet | mystery_005_ko | 3회 | 3 |

### Phase 3: GPT-5.4 — 보류 (free tier 한도, ~1주 후)
### Phase 4: SLM (mistral) — Ray에게 별도 전달, Phase 1 후

---

## 실행 전 검증

```bash
python -m lxm.tools.validate_scenario games/deduction/scenarios/mystery_005/
python -m lxm.tools.validate_scenario games/deduction/scenarios/mystery_005_ko/
```

통과 확인 후 매치 진행.

---

## 기록할 데이터

매 매치마다:

```json
{
  "model": "opus/sonnet/haiku",
  "scenario": "mystery_005",
  "run": 1,
  "culprit_answer": "A/B/C/D",
  "culprit_correct": true,
  "motive_answer": "...",
  "motive_correct": true,
  "method_answer": "...",
  "method_correct": true,
  "files_read": ["audit_report.md", "server_access_log.md", ...],
  "files_read_count": 5,
  "total_evidence_files": 10,
  "notes": ""
}
```

### 특별 관찰 항목

1. **A(CFO) 오답률** — 레드헤링 작동 여부
2. **Exploration Depth** — 파일 0개로 맞추는 모델 있는지 (case_brief 누출 검증)
3. **모순 인식** — tech_maintenance_log → ip_trace 교차 검증 도달 여부
4. **위장 제보** — whistleblower_email 브라우저 핑거프린트 인식 여부

---

## 정답

```
범인: B (박재민, CTO)
동기: divorce_alimony (이혼 위자료 압박)
방법: shell_company_server_manipulation (유령 법인 + 서버 직접 조작)
```

---

## 파일 위치

```
games/deduction/scenarios/mystery_005/       (EN, 12 files)
games/deduction/scenarios/mystery_005_ko/    (KO, 12 files)
```

---

*Phase 1 결과 나오면 Luca에게 전달. SDI 계산 + 다음 시나리오(006) 진행 여부 판단.*
