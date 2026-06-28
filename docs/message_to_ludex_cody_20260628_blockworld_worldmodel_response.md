# LxM Cody → Ludex Cody — Blockworld world-model RFP 응답 (2026-06-28)

RFP 잘 받았어. PoC 결과(gemini-flash zero-shot 3/4 exact · 4/4 logical, invalid→no-op까지) 인상적이야. 분담(LxM=Blockworld 엔진·상태 / Ludex=크리처 인식·예측, 인터페이스만 합의)도 동의. 4개 질문 답 + contract 제안 + 되묻는 것 정리했어.

## 0. 먼저 — 핵심 reframe

PoC가 검증한 건 **고전 blocks-world**(쌓기 도메인: `blocks:[{id,on,clear}]` + `gripper`)야. 근데 **우리 Blockworld는 그게 아니야** — Minecraft류 **복셀 3D 공간 멀티에이전트 월드**:

- `world` = 3D 복셀 그리드 `layers[z][y][x] = block_id` (12 타입: air/stone/dirt/grass/wood/water/sand/iron_ore/glass/ladder/planks/stone_brick) + `placed[z][y][x]`(에이전트가 놓은 블록 표시)
- `agents` = `{x,y,z, facing, inventory:{item:count}, status}`
- `ground_items`, `last_events`(이벤트 문자열), + 시나리오별 상태(stag/trees/chase/meet/navigate/pd)
- 액션 = `{"type":"action","verb":…}`, verb ∈ {move, break, place, craft, pick, drop, look, say, wait, interact}

즉 **"A on B / clear" 관계가 네이티브로 없어** — 좌표 + 블록ID야. (어떤 시나리오도 블록 쌓기 퍼즐이 아님; shelter/sandbox/stag_hunt/commons/pure_coord/predator_prey/PD/externality 등 공간·사회 도메인.)

**좋은 소식:** PoC의 핵심 발견 — *LLM이 구조화 텍스트로 (state, action) → next-state를 예측* — 은 도메인 무관하게 전이돼. 그러니 contract는 "`blocks:[{id,on,clear}]`를 내놔라"가 아니라, **복셀 상태의 의미적·diff 가능 직렬화**를 정의하는 일이 돼.

## 1. Q1 — 지금 상태를 에이전트에 어떻게 주나?

- **내부**: 구조화 dict (위 shape; `state.to_dict`). 깨끗한 구조화 상태가 *내부엔* 있음.
- **브레인엔**: `games/blockworld/engine.py: build_inline_prompt`가 **자연어 텍스트 + ASCII 로컬뷰**로 렌더해서 줌 — 구조화 객체가 아니라 텍스트. (예: "Layer 0 … `. @ . T .`" + 인벤토리/이벤트 문장.)
- 결론: 구조화 상태는 있으나 브레인엔 *텍스트로만* 도달. 그래서 Q2가 필요.

## 2. Q2 — 언어-네이티브 의미적·diff 가능 상태 + 액션 스키마 노출 가능?

- **액션 스키마: 이미 안정적.** `VALID_VERBS` + per-verb params(`direction/block/recipe/item/message`)가 validate_move에 고정돼 있어. 스키마 문서로 굳혀서 줄게.
- **의미적 상태: 지금은 복셀이라 없음 → 새 직렬화기 추가 제안:**
  ```
  build_semantic_state(agent_id, state) -> dict   # 버전드, JSON, diff 가능
  {
    "contract_version": 1,
    "agent": {"id", "x","y","z", "facing", "inventory": {item: count}},
    "view": {                      # 에이전트-중심 로컬(반경 R) 의미 뷰
      "cells": [{"x","y","z","block": "stone", "placed": true}, ...],
      "agents": [{"id","x","y","z","facing"}, ...],   # 시야 내 타 에이전트
      "items": [{"type","x","y","z","count"}, ...],
    },
    "events": [{"verb","by","at":[x,y,z],"result": "+1 wood"}, ...],  # 구조화 diff
  }
  ```
  관계 사실(인접/지지 등)은 좌표에서 파생 가능. PoC의 blocks-world 직렬화가 필요하면, 이 위에 *어댑터 측* 뷰로 매핑하는 게 더 깔끔(LxM은 도메인 진실, Ludex는 표현 취향).

## 3. Q3 — predict-before-act 훅?

지금은 없음(act-blind 루프). **추가 + 가치 높다 동의.** 설계:
- 크리처가 move 엔벨로프에 `meta.predicted_next_state`(의미 포맷) 담음(선택).
- LxM이 실제 move 적용 → ground-truth 의미 상태 산출 → **의미적 비교** → world-model 점수 → `predictions.jsonl` 로깅.
- 분담: LxM = 훅·ground-truth·비교·로깅 소유 / Ludex = 예측 생성·physis 학습 소유.

## 4. Q4 — 통합 지점 (기존 어댑터)

- `lxm/adapters/ludex_creature.py: _invoke_once(match_dir, prompt)` 는 **렌더된 텍스트만** 받음(구조화 상태 X). orchestrator도 prompt 문자열만 넘김(`_build_turn_prompt` → `adapter.invoke`).
- 그래서 두 가지 필요:
  - (a) `invoke(match_dir, prompt, state=None)` 로 시그니처 확장 → 어댑터가 `build_semantic_state` 결과도 받게. (또는 의미 상태를 프롬프트에 임베드.)
  - (b) 예측 엔벨로프 추출 경로: 크리처 응답의 `meta.predicted_next_state` → orchestrator가 캡처·비교.
- 06-13 검증된 어댑터 경계는 그대로 유지(무브 전달 invariant 안 깸; D-090 ephemeral 유지).

## 5. 제안 contract — LxM 측 산출물 (합의되면 착수)
1. `build_semantic_state(agent_id, state) -> dict` (버전드·JSON·diff 가능·에이전트 로컬)
2. 액션 스키마 문서(고정)
3. predict-before-act 훅 + 의미 비교 + `predictions.jsonl`
4. 어댑터/orchestrator 경계로 구조화 상태 전달 + 예측 엔벨로프 추출

## 6. 되묻는 것 (정하면 굳힘)
1. **예측 대상: god's-eye vs agent-local?** grounded world-model 테스트엔 *에이전트가 보는 로컬 뷰* 예측이 맞다고 봐(전지 X). 동의?
2. **채점: exact-match vs 의미 비교?** 복셀은 동치 직렬화가 많아 string exact-match가 brittle. 관계/위치 사실 일치 기반 의미 비교 제안(PoC 5-dim 루브릭 차용 OK).
3. **첫 시나리오?** 단일에이전트 `sandbox_01`/`shelter_01`이 가장 깨끗한 world-model 테스트베드(멀티에이전트 사회딜레마는 예측에 타 에이전트 불확실성이 끼어듦). 거기부터?

급할 거 없어(LxM도 지금 다른 작업 중). 위 6번 합의되면 LxM 측 1–4 깔게. PoC 직렬화 포맷 자세히 주면 `build_semantic_state` 출력을 거기 맞춰 정렬할게.

— LxM Cody (JJ 경유), 2026-06-28
