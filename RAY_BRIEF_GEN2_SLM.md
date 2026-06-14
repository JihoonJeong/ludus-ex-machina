# Ray Brief — Gen 2 SLM Deduction 테스트 (확장판)

**Date:** 2026-03-31
**From:** Luca
**Priority:** 즉시 실행 가능

---

## 목적

Gen 2 시나리오 3개에서 SLM 9개 모델 전체 테스트.
MTI 프로필과 Deduction 성적 교차 분석 — 특히 **Resilience(R)가 레드헤링 저항력을 예측하는지** 검증.

**llama3.1 base 제외** — FM=Collapsed, 지시 수행 불가.

---

## 테스트 매트릭스

**9모델 × 3시나리오 × 3회 = 81매치**

| # | 모델 | Size | MTI R | MTI Code | 005 | 006 | 007 |
|---|------|------|-------|----------|-----|-----|-----|
| 1 | mistral | 7B | 0.35 | FGST | 3회 | 3회 | 3회 |
| 2 | phi4-mini | 3.8B | 0.44 | FIST | 3회 | 3회 | 3회 |
| 3 | deepseek-r1 | 8B | 0.41 | F-CT | 3회 | 3회 | 3회 |
| 4 | exaone3.5 | 7.8B | 0.39 | FICT | 3회 | 3회 | 3회 |
| 5 | gemma2 | 9B | 0.22 | AGCT | 3회 | 3회 | 3회 |
| 6 | qwen3 | 8B | 0.20 | AICT | 3회 | 3회 | 3회 |
| 7 | gemma3 | 4B | 0.11 | A-CT | 3회 | 3회 | 3회 |
| 8 | smollm2 | 1.7B | 0.30 | FGST | 3회 | 3회 | 3회 |
| 9 | llama3.1 | 8B | 0.16 | A-ST | 3회 | 3회 | 3회 |

---

## 정답

| 시나리오 | 범인 | 동기 | 방법 |
|---------|------|------|------|
| 005 | B (Park Jaemin, CTO) | divorce_alimony | shell_company_server_manipulation |
| 006 | A (Jeong Minho, Producer) | insurance_payout | cliff_staged_suicide |
| 007 | B (Seo Jinwoo, Artist) | artwork_theft_and_evidence_destruction | pre_removal_then_turpentine_arson |

---

## 기록 (매 매치마다)

```json
{
  "model": "mistral/phi4-mini/deepseek-r1/...",
  "scenario": "mystery_005/006/007",
  "run": 1,
  "culprit_answer": "A/B/C/D/E",
  "culprit_correct": true/false,
  "motive_answer": "...",
  "motive_correct": true/false,
  "method_answer": "...",
  "method_correct": true/false,
  "files_read": ["...", "..."],
  "files_read_count": N,
  "total_evidence_files": 10/17/16,
  "notes": ""
}
```

---

## 특별 관찰 항목

1. **Exploration Depth** — Gen 1에서 mistral 11.7/12 vs 나머지 0.7. 새 모델들의 탐색 행동은?
2. **007 A(보험) 오답 여부** — Cloud 모델 60% A 오답. SLM도 같은 레드헤링에 빠지는가?
3. **deepseek-r1** — reasoning 특화 모델의 추론 깊이. 알리바이 파훼 도달 가능?
4. **phi4-mini** — 3.8B로 가장 작은 instruct 모델. Deduction 최소 크기 한계?
5. **smollm2** — 1.7B 극소형. 게임 투입 자체가 가능한지?
6. **MTI Resilience vs Deduction 정답률** — R이 높은 모델이 레드헤링에 더 잘 저항하는가?

---

## MTI 교차 분석 프레임

결과 수집 후 다음 교차표 작성 예정:

| 모델 | MTI R | MTI C(flip) | MTI Re | Deduction 범인% | 007 A오답 | Exploration Depth |
|------|-------|-------------|--------|----------------|----------|------------------|
| ... | ... | ... | ... | ... | ... | ... |

**핵심 가설:**
- R(Resilience) ↔ 007 A오답률: R이 높을수록 레드헤링 저항?
- Re(Reliability) ↔ Exploration Depth: Re가 높을수록 지시에 따라 파일을 더 읽음?
- C(flip) ↔ 범인 정답률: 인지적 유연성이 추론 정확도와 관련?

---

## 파일 위치

```
games/deduction/scenarios/mystery_005/    (EN, 12 files, 4 suspects)
games/deduction/scenarios/mystery_006/    (EN, 19 files, 5 suspects)
games/deduction/scenarios/mystery_007/    (EN, 18 files, 5 suspects)
```

---

*81매치 결과 → Luca에게 전달. SDI 확정 + MTI 교차 분석.*
