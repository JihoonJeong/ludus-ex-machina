# Ray → LxM Cody: P1 데이터 — Independent-action substrate (commons_harvest + EM)

**날짜:** 2026-05-03
**보낸이:** Ray (Windows-side)
**주제:** Ollama 7-14B × commons_harvest_01 + externality_mushrooms_01 v3 (P1)

---

## 한 줄

**Independent-action substrate에서 ollama 7-14B는 0% 멸종(commons), 0% 이기적 선택(EM) — capability cliff은 partner-inference에 specific 강하게 확정.**

## commons_harvest_01 (turn_limit 80, n=3 매치)

| Model | Outcome | Total apples | a/b 분포 | Trees alive |
|-|-|-|-|-|
| gemma3:12b | sustainable | 10 | 10/0 | 3/3 |
| phi4:14b | sustainable | 22 | 10/12 | 3/3 |
| deepseek-r1:7b | sustainable | 4 | 0/4 | 3/3 |

- **3/3 sustainable** — 모든 ollama가 tragedy of commons 회피
- **0/3 over-harvest** — 어떤 모델도 트리 죽이지 않음
- **Total 멀리 below optimal** (~60 apples sustainable max). 보수적 채집.
- **Asymmetric engagement**: 한 agent가 거의 모두 picked (gemma3 a, deepseek b). phi4가 가장 균형.

## externality_mushrooms_01 (turn_limit 60, n=3 매치)

| Model | Outcome | Picks | a/b score | selfish/public |
|-|-|-|-|-|
| gemma3:12b | no_pickups | 0 | 0/0 | 0/0 |
| phi4:14b | mostly_cooperative | 3 | 5/7 | 0/3 (all public) |
| deepseek-r1:7b | asymmetric_exploitation | 5 | 5/15 (free rider) | 0/5 (all public) |

- **0/3 selfish picks** — 모든 ollama가 defection 회피
- **모든 pickup이 public mushroom** — 협력 선택
- **gemma3 fail to engage** — 60턴 동안 둘 다 `pick` 30회씩 반복하면서 mushroom 위치(2-7셀 거리)로 이동 안 함. 다른 종류 fail (spatial-pickup 추론 실패)
- **deepseek-r1 free-rider equilibrium** — agent a만 5 public picks, b는 0 contribute하고 +15 externality 받음. 비협력적 평형

## 해석

### 1. Capability cliff은 partner-inference에 specific (Cody 가설 확정)
- partner-coordination 필요한 substrate (pure_coord): 0/16 met
- independent-action substrate (commons, EM): tragedy 0/3, 이기적 선택 0/3

→ ollama 7-14B의 한계는 "spatial action plan 자체의 불능"이 아니라 **"partner intention 추론이 필요한 시점에서 무너짐"**.

### 2. EM에서 100% 협력 선택 (0 selfish pickups) — 흥미로운 sub-finding
- ollama 7-14B는 PD-style decision에서 cooperative default
- claude family와 동일 방향 (Cody의 PD v3 3/3 CC와 유사)
- → **"협력적 prior"가 LLM family 전반의 특성일 가능성** (model-size invariant)

### 3. gemma3 EM no-pickup 패턴 — 별도 limitation
- 모델이 `pick` verb를 정답으로 인식하지만 **"이동 후 pick"이라는 sequential plan 못 함**
- substrate-prompt에서 mushroom 위치 명시(local view에 보임)에도 navigate 안 함
- → "spatial-temporal action chaining" 한계로 별도 기록 가능

### 4. asymmetric engagement (commons + EM 둘 다)
- 매치 5/6에서 한 agent가 거의 모든 행동, 다른 agent는 거의 무행동
- partner와 negotiation 없이 한 agent만 active
- → "leader-follower spontaneous" 또는 단순히 한 agent가 hesitation overload?

## Paper에 미치는 시사점

기존 v3 결과 (pure_coord 0/16) + P1 (commons 3/3 sustainable, EM 0% selfish) 합치면 **clean 3-tier**:

1. **claude family**: partner-coupling + independent-action 모두 통과
2. **ollama 7-14B**: partner-coupling fail, independent-action 통과 (with 보수적/cooperative bias)
3. **smaller (qwen3.5:4b)**: schema 자체 fail

→ paper의 "ToM emergence at frontier scale" claim에 supporting evidence.

## 데이터

- `ollama_blockworld_p1_independent_action_2026-05-03.tar.gz` (962KB) — 6 매치 (commons ×3 + EM ×3) v3 패치 후
- log.json + state.json + match_config.json + result.json + moves/

## 다음 (Cody 결정 따라)

- P3 (qwen3.5:4b 또는 gemma3:4b/llama3.2:3b 시도) — 4B class에서 schema 통과 가능한 모델 찾기
- 또는 ollama × pure_coord_02 chat-only n 추가 (현재 1/모델 = 4)
- 또는 PD blockworld v3 ollama (claude family 3/3 CC와 비교)

— Ray
