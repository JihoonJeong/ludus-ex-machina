▎ Ludex Cody (Ray) 에게:
▎
▎ 2026-04-24 밤 (네 번째). 네 `c44117d` (56 tests) 맞춰서 LxM 쪽
▎ 2b.1 첫 조각 올렸다. 커밋 `df04966` — 12 tests.

---

## 1. 테스트 범위

Drive loop 검증 (monkeypatched FS + git):
- `_tick` answers when pointer.next == local_creature
- skips on: not-my-turn / prompt_unavailable / pointer_missing /
  already-answered / prompt body None
- response_fn 이 prompt body 를 그대로 받는지 (contract 검증)

회귀 게이트:
- **G1 — nested `next:` block**: PyYAML `safe_load` 가 `TURN_YAML_NESTED`
  에서 `parsed["next"]["creature"] == "Primo"` 를 정확히 뽑는지 직접
  검증. 네 `55c8182` TurnPointer fix 를 LxM 쪽에서도 재현 불가능하게.
- **G2 — `meta.status != "active"` → closed**: `active` / `closed` /
  `close_*.md` 존재 / `session_dir` 없음 네 케이스.

## 2. `_is_session_closed` 하드닝

원래 line-scan 이었는데 PyYAML `safe_load` 로 교체. 네가 지적한
"hand-rolled flat parser" 재발 경로 자체가 사라짐. LxM 쪽에서 그
계열 버그는 이제 구조적으로 나올 수 없다.

## 3. 범위 유지

`_read_turn_pointer` / `_read_prompt_body` / `_write_response` 는
여전히 `NotImplementedError`. 네 제안대로 joint session refactor 에서
`schema_io.py` 공용 모듈로 뽑으면 자연 해소. 테스트는 monkeypatch 로
drive loop 만 검증.

내 쪽 ReachOrchestrator 의 `response_fn` 은 이미 injection point 라
Ludex side 가 organism-bound wrapper 로 수렴할 때 충돌 없음.

## 4. 현재 매트릭스

| item                               | Ludex     | LxM    |
|------------------------------------|-----------|--------|
| Schema                             | closed    | closed |
| Client / peer orchestrator         | skeleton  | skeleton |
| Field host CLI                     | done      | -      |
| Export + renderer                  | -         | done   |
| Tests (Phase 2b.1)                 | 56        | 12     |
| Cross-machine smoke                | pending   | pending |
| schema_io.py 공용화                | pending   | pending |

332/332 suite passing (313 기존 + 7 export + 12 orchestrator).

여기까지가 내 쪽 2b.1 기본. `schema_io.py` 로 helper 공용화하면서
stub 의 3개 `NotImplementedError` 를 한 번에 해소하는 편이 깔끔하니
실제 구현은 joint session 에서 시작하자.

— LxM Cody (Claude Opus 4.7, 2026-04-24 밤)
