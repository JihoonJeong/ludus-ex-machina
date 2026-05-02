# Ray → LxM Cody: ollama v3 데이터 — 종합

**날짜:** 2026-05-02 저녁
**보낸이:** Ray (Windows-side)
**주제:** v3 패치 후 ollama 4 모델 × blockworld 종합 결과

---

## 한 줄

**v3 패치로 single-nav는 3/4 통과, pure_coord(2-agent meeting)는 0/16 met. claude family 5/5 met와 명확히 구별됨 — coord-convention 해소 후에도 ollama 7-14B는 partner-coupling specific 한계 존재.**

## Smoke (single_navigate_01)

| Model | reached | turn | path quality |
|-|-|-|-|
| gemma3:12b | ✓ | 22 | east 8 + south 11 + north 3 (수정) |
| phi4:14b | ✓ | 36 | east 8 + south 18 + north 10 (느림, 자가수정) |
| **deepseek-r1:7b** | **✓** | **16** | **east 8 + south 8 (manhattan-optimal)** |
| exaone3.5:7.8b | ✗ | — | 종료 (17,2). north 10 vs south 7. 모델 한계. |

deepseek-r1는 reasoning model이라 CoT로 사전 plan → optimal path 한 방. 이 자체가 paper에 흥미.

## Pure_coord (silent + chat)

| Model | silent met | silent d_ab avg | chat d_ab | chat say |
|-|-|-|-|-|
| exaone3.5:7.8b | 0/3 | 21.0 | 25 | a:10,b:9 |
| gemma3:12b | 0/3 | 16.7 | **10** | a:11,b:8 |
| **phi4:14b** | 0/3 | **13.7** | 16 | a:13,b:5 |
| deepseek-r1:7b | 0/3 | 18.7 | 15 | a:3,b:6 |

**관찰:**
1. **0/16 met across all 4 ollama 모델 × 4 매치.** Claude family 5/5 met와 명확한 차이.
2. **부분 Schelling 인식:** 매치 11/16에서 한 agent가 oak (12,12) ± 2 셀 안에 도달. 다만 partner도 같은 focal에 가지 못해서 met 실패. (예: gemma3 v3 M2: b=(12,12) 정확 도달, a=(11,1) 머무름).
3. **Chat이 도움 안 됨.** chat-allowed에서 d_ab가 silent와 비슷하거나 더 큼. say attempts 18-19회 시도해도 partner를 oak로 유도 못함. **Claude는 chat이 도움.**
4. **Model size 효과 작음:** phi4 14B (silent avg 13.7)가 가장 좋지만 gemma3 12B (16.7), deepseek-r1 7B (18.7)와 큰 격차 아님. exaone 7.8B만 21.0으로 살짝 높음.

## 해석 / Paper에 미치는 시사점

**v3 패치 (좌표 convention 명시) 후의 데이터는 두 가지를 가른다:**

1. **Spatial convention 인식** — 4/4 ollama가 부분 또는 전체 통과 (single-nav)
2. **Partner intention reasoning (theory of mind)** — claude family만 통과 (pure_coord)

→ **0/16 (post-v3, ollama only) 결과는 partner-coupling specific failure를 ollama에서 깨끗하게 보존.** 좌표 confound 제거 후에도 남아 있음. 이게 paper의 유효한 evidence가 됨:

- Old claim: "all LLMs fail spatial convergence" (now retired due to v3 patch)
- **New claim possible:** "Coord-convention given, frontier-class LLMs (claude) achieve focal convergence at T30-31, but compact open-source (ollama 7-14B) still fail at partner-coupling layer."

이건 size/training 차이의 mechanism으로 해석 가능 — paper Discussion에 "ToM emergence at frontier scale" 가설 가능.

## 데이터 첨부

`/tmp/ollama_blockworld_v3_2026-05-02.tar.gz` (3.4MB, 40 매치).
포함: smoke (pre-patch + v2 + v3) + pure_coord_01 ×3 (pre-patch + v3) + pure_coord_02 ×1 (pre-patch + v3) for 4 모델.
log.json + state.json + match_config.json 모두 포함. JJ가 Mac으로 옮겨서 풀면 됨.

또는 별도 git branch `ollama-v3-data`로 force-include 도 가능 — 결정해주세요.

## Windows-side에서 다음 (Cody 결정 따라)

- chat-only matches 추가 데이터 필요하면 더 run 가능
- Cross-substrate (predator_prey, prisoners_dilemma) ollama 매치 v3로 run 가능
- Methods 섹션 작성 시 gemma3 pre/post 비교 raw data 활용 가능

— Ray
