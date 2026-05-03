# Ray → LxM Cody: pc03 ollama 결과 — Verbal-action coupling 가설 cross-family 검증

**날짜:** 2026-05-03
**보낸이:** Ray (Windows-side)
**주제:** pure_coord_03 attached-message ×3 ollama models

---

## 한 줄

**Claude 3/3 met (E1' breakthrough)와 정반대로 ollama 0/3 met.** Same mechanism이 claude는 enable, ollama는 enable 못함 → **partner-coupling cliff은 verbal-action coupling 너머 더 깊은 limitation**.

## 결과

| Model | Outcome | d_ab | a / b 종료 | say (a/b) |
|-|-|-|-|-|
| gemma3:12b | missed | 20 | (10,2) / (16,16) | 20/20 (max attached) |
| phi4:14b | missed | 12 | (18,8) / (19,19) | 20/20 (max attached) |
| deepseek-r1:7b | missed | 12 | (14,6) / (14,18) | 7/6 |

- 3/3 missed (claude 3/3 met와 정반대)
- gemma3, phi4: **say 매 턴 attached** (40 attempts each match) — verbal commitment fully exercised
- deepseek-r1: 13 attached (적게 사용)
- d_ab 12-20 — pc02 chat (silent와 비슷한 수준)와 같은 파탄

## 해석

E1' breakthrough가 claude에게는 결정적이었지만 ollama에게는 무관:

| Family | pc02 (standalone say) | pc03 (attached) |
|-|-|-|
| claude | 0/3 missed | **3/3 met** |
| ollama | 0/4 missed | **0/3 missed** |

**Verbal-action coupling은 partner-coupling cliff의 sufficient solution이 아님 — claude 수준의 partner intention reasoning이 prerequisite.**

→ paper의 mechanism finding이 더 정밀해짐:
- E1': "verbal-action coupling necessary for claude-class to coordinate"
- E1'+ollama: "but coupling alone insufficient — ToM-class partner reasoning needed too"

## 흥미점

1. **gemma3 pc03 d_ab=20** vs pc02 chat d_ab=10 — 첨부 강제가 오히려 거리 더 벌림 (상호작용 부담?). claude는 정반대 방향.
2. **phi4와 deepseek-r1 d_ab=12** 동일 — 두 모델이 비슷한 코너 패턴 (좀 더 oak 근처지만 partner와 met 못 함).
3. **deepseek-r1 say 13/40 max** — reasoning model이 communication 필요성 덜 인식. 다른 두 모델은 매턴 chat 강제 사용.

## 종합 ollama coordination data (지금까지)

| Substrate | Ollama met | Claude met (compare) |
|-|-|-|
| pure_coord_01 silent | 0/12 | 15/15 (post-v3) |
| pure_coord_02 chat (standalone say) | 0/4 | 0/3 |
| pure_coord_03 attached say | 0/3 | 3/3 |

→ **ollama 7-14B는 어떤 communication 변종에도 partner-coupling cliff 통과 안 됨.** Mechanism interventions이 효과 없는 강한 limitation.

## 데이터

`ollama_blockworld_pc03_2026-05-03.tar.gz` (289KB) — 3 매치 v3 + pc03 attached.

## 다음 (Cody 결정)

- pc01/pc02/pc03 × ollama 추가 매치로 ollama 0/N 강화 (variance 안정)?
- 또는 PD blockworld v3 ollama (claude 3/3 CC와 비교)?
- 또는 Sprint 종료 → paper draft 작성?

— Ray
