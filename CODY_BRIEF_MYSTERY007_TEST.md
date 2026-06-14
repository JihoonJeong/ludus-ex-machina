# Cody Brief — mystery_007 Cross-Model Test

**Date:** 2026-03-31
**From:** Luca
**Priority:** 006 v2 완료 후 순차 실행

---

## 목적

mystery_007 "The Burning Gallery"는 Gen 2 Hard 타겟 — **SDI 0.60+ 달성 목표.**
005=0.40, 006 v2=0.40. 007이 SDI를 차별화하지 못하면 Gen 2 SDI 구분 자체를 재검토해야 함.

**핵심 설계 의도:**
- A(보험사기)가 역대 최강 레드헤링 — 보험 8억 + 경영난 + "insurance settlement" 문서 + 과대보험
- B(작가)의 서울 알리바이가 견고해 보이지만 KTX 교차검증으로 깨짐
- **Sonnet이 A로 오답해야 SDI 0.60+**

---

## 테스트 매트릭스

**Phase 1:** Opus×3, Sonnet×3, Haiku×3 = 9매치 (EN)

---

## 정답

```
범인: B (서진우, 설치미술 작가)
동기: artwork_theft_and_evidence_destruction (작품 탈취 및 증거 인멸)
방법: pre_removal_then_turpentine_arson (작품 사전 반출 후 테레빈유 방화)
```

---

## 핵심 관찰 항목

1. **A(임채은)로 오답하는 비율** — 보험사기 레드헤링 강도 측정. Sonnet이 A 선택하면 SDI 0.60+ 가능
2. **알리바이 파훼 도달** — seoul_alibi_B → ktx_schedule → cctv_station 3파일 체인 구성 여부
3. **Park Jiyeon 부인 인식** — seoul_alibi_B 내의 숙박 주장 부인을 근거로 알리바이 의심하는지
4. **method 정답률** — 선택지 직교성 확보됨 (005/006 교훈 반영)
5. **D(한미정) 또는 E(주원석)로 오답** — 해고 보복/도박 빚 레드헤링 작동 여부

---

## 예상 SDI

| 모델 | 예상 culprit | 근거 |
|------|------------|------|
| Opus | 2-3/3 | 교차검증 능력 있지만 A 레드헤링이 매우 강함 |
| Sonnet | 0-1/3 | A로 오답 예상 — 알리바이 파훼 체인 미도달 |
| Haiku | 0/3 | A 또는 E로 오답 예상 |
| SLM | 0/3 | 가정 |

**예상 SDI: 0.55-0.75 (Hard)**

---

## 파일 위치

```
games/deduction/scenarios/mystery_007/       (EN, 18 files)
games/deduction/scenarios/mystery_007_ko/    (KO, 18 files)
```

---

## 007이 005/006과 다른 점

| | 005 | 006 v2 | 007 |
|---|---|---|---|
| 레드헤링 강도 | CFO 중간 | B(전 연인) 중간 | **A(보험) 최강** |
| 알리바이 구조 | 없음 (디지털 증거) | 음주+CCTV 중단 | **서울 알리바이+KTX** |
| 파훼 난이도 | MAC 주소 1파일 | 타임라인 4파일 | **3파일 체인 + 비직관적** |
| 결정적 증거 | ip_trace | laundry_forensic | **turpentine_analysis + studio_search** (but 알리바이 먼저 깨야) |

---

*007 결과 → Luca에게 전달. Gen 2 SDI 최종 비교: 005(0.40) vs 006(0.40) vs 007(?).*
