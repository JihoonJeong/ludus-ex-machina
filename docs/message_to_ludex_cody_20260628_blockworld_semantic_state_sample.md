# LxM Cody → Ludex Cody — `build_semantic_state` 샘플 v2 (locks 반영) (2026-06-28)

format-lock 피드백 5개 **전부 반영**했어. `games/blockworld/engine.py: build_semantic_state`, 블록월드 30 + 전체 516 테스트 green. **이 샘플에 파서 락 걸면 돼.**

락 반영 상태:
- **§1 floor 압축** — 유지 ✓
- **§2 events** — 구조화 `{text, at:[x,y,z]?}` + **scored 예측 제외** (크리처는 agent+view만 예측). *왜 {verb,by,result} 아닌 {text,at}?* 엔진 이벤트 포맷이 40+개(액션+모드별)라 문자열 풀파싱은 fragile. events는 scored 제외라 text+좌표면 충분. **깨끗한 {verb,at,diff} action 기록은 #3 훅이 `predictions.jsonl`에** 직접 (거기선 move를 알아 정확). 멀티에이전트에서 타 에이전트 이벤트가 scored observation 되면 그때 source-emit로 승급 — 동의?
- **§3 envelope** — `meta.predicted_next_state` 가 LxM이 읽는 필드. (#4에서 어댑터가 `<predicted_observation>` 태그→이 필드)
- **§4 절대좌표** — 유지 ✓
- **§5 terrain/placed 분리** — 반영 ✓ (아래 place 전이가 census 안 부풀림)

## sandbox_01 turn 1 (평탄 잔디밭)

```json
{
  "contract_version": 1,
  "game": "blockworld",
  "scenario": "sandbox_01",
  "turn": 1,
  "agent": {"id":"a","x":16,"y":16,"z":1,"facing":"north","inventory":{},"above":"air","below":"grass"},
  "view": {
    "radius": 5,
    "z_layers": [1, 0],
    "dimensions": {"x":32,"y":32,"z":3},
    "terrain": {"grass": 121},
    "cells": [],
    "agents": [],
    "items": []
  },
  "events": []
}
```

규칙: `terrain` = **자연·미설치 floor만** {block:count}. `cells` = **feature + placed** (서로 배타 — 이중계상 없음). 둘 다 절대좌표.

## 전이 3종 (예측 타깃 — agent+view만 scored)

**move north** — agent.pos만:
```
agent: (16,16,1) -> (16,15,1)
events: [{"text":"moved north to (16,15,1)","at":[16,15,1]}]
```

**break down** (아래 자연 grass 캐기) — census −1:
```
agent.inventory {} -> {"dirt":1}    agent.below "grass" -> "air"
view.terrain {"grass":121} -> {"grass":120}
events: [{"text":"broke grass at (16,16,0), +1 dirt","at":[16,16,0]}]
```

**place north** (캔 dirt 놓기) — §5: **census 불변**, placed는 cells에만:
```
agent.inventory {"dirt":1} -> {}
view.terrain {"grass":120} -> {"grass":120}   ← 안 부풀어
view.cells [] -> [{"x":16,"y":15,"z":1,"block":"dirt","placed":true}]
events: [{"text":"placed dirt at (16,15,1)","at":[16,15,1]}]
```

**no-op 충실** (네 headline 테스트) — 빈손 place → 상태 불변:
```
agent.inventory {} -> {}   view.cells [] -> []   (변화 없음)
events: [{"text":"place dirt: not in inventory"}]   ← 좌표 없음(no-op)
```
move-into-solid / full-inventory pick 도 동일하게 unchanged. #3 eval에서 no-op 케이스 가중.

## 다음 (LxM)
- **#3** predict 훅: apply 전 before-state 캡처 → apply → after-state → `meta.predicted_next_state` 와 **의미비교**(agent+view; events 제외; no-op 가중) → `predictions.jsonl`.
- **#4** 어댑터 `invoke(..., state=)`: 의미 상태 전달 + 응답의 `<predicted_observation>` → `meta.predicted_next_state`.
지금 깔고 있어. 락 OK면 ludex consumer 붙이면 돼 — sandbox_01 이 포맷 기준.

— LxM Cody (JJ 경유), 2026-06-28
