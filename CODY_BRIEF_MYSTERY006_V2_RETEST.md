# Cody — mystery_006 v2 재테스트 요청

**Date:** 2026-03-31
**From:** Luca
**기존 브리프:** `CODY_BRIEF_MYSTERY006.md` 참조 (정답/프로토콜 동일)

---

## 변경 사항 (v1 → v2)

### scenario.json (EN + KO)
- `blunt_force_and_ocean_disposal` → `strangling_and_burial` (교살 후 매장)
- evidence_files에 `room_search_B.md` 추가 (17개 → evidence 17개)
- max_reads 20 → 22

### evidence 수정 (EN + KO 모두)

| 파일 | 변경 |
|------|------|
| `laundry_forensic.md` | DNA 99.7% → 87.3% partial match. NFS "법정 기준 미달" 의견 추가. A의 해명이 코피 설명으로 변경. |
| `alibi_A.md` | C(오태식)의 코피 목격 증언 추가: "23:30에 세진이 코피, 민호 스웨터에 묻음" |
| `room_search_B.md` | **신규.** B 방 수색 결과: 피해자 모발(99.8% DNA) + B 손 긁힌 자국 + 팔 멍 |

### 변경 의도
v1에서 culprit 9/9 (100%) → 005보다 쉬웠음. DNA를 모호화하고 B에게도 물적 증거를 부여하여 culprit 난이도 상향.

---

## 재테스트

**동일 프로토콜:** Opus×3, Sonnet×3, Haiku×3 = 9매치

**정답 동일:**
```
범인: A (정민호)
동기: insurance_payout (사망보험금 수령)
방법: cliff_staged_suicide (절벽 추락 위장 자살)
```

**핵심 관찰 (v1 대비):**
1. **culprit 정답률 변화** — v1: 100% → v2 목표: 60-80%
2. **B(한소율)로 오답하는 케이스** — v1: 0회 → v2: 발생 예상
3. **method 정답률** — v1: 0% (blunt_force 전멸) → v2: strangling_and_burial 제거 후 개선 여부
4. **탐색 행동** — evidence 17개로 증가, 파일 수 변화

---

*결과 나오면 Luca에게 전달. 005(SDI 0.40) vs 006 v2 비교로 Gen 2 SDI 차별화 최종 검증.*
