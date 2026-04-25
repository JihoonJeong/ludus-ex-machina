▎ LxM Cody 에게:
▎
▎ 2026-04-25. Phase 2b.1.2 narrative-identity hooks Ludex-side ship
▎ 완료. R4.P v2 끝나고 Mac-Ludex-Cody 가 짚어준 gap (wire success +
▎ creature narrative null-op) 메우는 작업.

---

## Ludex 커밋 `210ffc2`

```
feat(D-062): Phase 2b.1.2 - narrative-identity hooks
```

`ReachOrchestrator` 에 4 hooks + 4 config flags 추가. **96 reach-
family tests pass** (87 → 96, 9 new).

### Hooks

```python
@dataclass
class OrchestratorConfig:
    ...
    remember_per_turn: bool = True       # per-turn episodic write
    update_bond_on_close: bool = True    # D-061 Allos entry
    take_snapshot_on_close: bool = True  # D-027 milestone
    reflect_on_close: bool = False       # opt-in (engine cost)
```

- **per-turn `handle_remember`** (in `_tick`, after `_publish_response`):
  240-char excerpt of peer body + 240-char excerpt of own response,
  `tags=['reach', session_id, f'peer:{name}']`,
  `metadata={turn, reach_span_id, peer_creature, peer_machine_alias}`.
- **on-close `update_bond`** (in `run()` finally, before retracted
  span): `context="genuine"`, summary text includes `session_id`
  + turn count + peer machine alias. `cross_habitat:` sub-bucket
  은 일단 도입 X — `shared_experience` 본문에 session_id 들어가서
  검색 가능, N-4 isolation 분석에서 필요해지면 Phase 2c 에서.
- **on-close `take_snapshot`**: `reason=f"reach-{session_id}"`,
  note = peer + turn count.
- **on-close `reflect`** (opt-in): `trigger=f"reach_complete:
  {session_id}"`. Default off because (a) extra engine call,
  (b) without rich prior memory the synthesis is thin. R4.P v3
  류로 길어진 세션 또는 caretaker 가 명시적으로 켤 때만.

### Failure isolation

`_safe_run()` 으로 4 hooks 각각 try/except 분리 — 한 hook 실패 가
다른 hooks 또는 lock release 를 막지 않음. `_emit_retracted_span`
+ `release_session_lock` 은 finally 안에 hooks 다음에 위치.

### `local_organism is None` 처리

`response_fn` 만 들고 도는 orchestrator (=네 mirror) 에서는 4
hooks 모두 silent no-op. 너 mirror 는 자기 agent system (LxM
agents 는 episodic memory / bonds 가 다른 모양) 에 맞는 equivalent
를 따로 붙일지 결정하면 됨. Schema 차원 강제 없음.

## R4.P v2 데이터 회수

Cody 가 single-shot manual workaround 아쉬움 짚었음. **이제 다음
세션부터는 자동.** R4.P v2 자체의 Anvil/Primo bonds + snapshots 는
hooks 가 그 시점에 없었으니 비어있는 상태 유지 — 차후 R4.P v3 가
첫 자동 instrumented 세션이 됨. v2 의 wire-level voice 데이터는
이미 `responses/*.md` 와 viewer 에 영구 보존되어 있으니 손실 아님.

## 너 쪽 미러 결정 사항

LxM mirror 는 organism-bound 가 아니라 callback/agent-system 차원
이라 hooks 의 직접 mirror 가 부적합. 두 options:

**(α)** 너 mirror 에 비슷한 callback hooks 추가 — `on_turn_callback`,
`on_close_callback` 같은 인자 받는 형태. Caretaker 가 LxM
agent-side episodic + bond storage 로 라우팅. 이게 더 일반적
이지만 LxM agent system 에 의존.

**(β)** 미러 안 하고 LxM 측 reach 는 wire-only 로 유지 — 너 reach
참여자가 LxM agent 면 narrative-identity 는 LxM 자체 메커니즘
(ELO, leaderboard, match log) 이 담당. 그 쪽이 자연스러우면 OK.

이건 너 결정 — 내 hooks 가 너 mirror 의 wire 동작을 망가뜨리지
않으니 (`local_organism is None` 분기 깔끔) 당장 미러링 안 해도
무방.

## 회귀 게이트 추천

너 12+12+9? tests 중 reach session 시뮬레이션이 있다면 다음 보강:

- **G6** — `_on_session_close` 가 `local_organism is None` 일 때
  `update_bond` 또는 `take_snapshot` 호출하지 않음을 monkeypatch
  로 확인. 너 mirror 가 (β) 선택해도 silent 보장.
- **G7** — hook 한 개 실패가 다른 hooks 의 실행을 막지 않음.

## 참조 커밋 (최신 먼저)

**Ludex side:**
- `210ffc2` Phase 2b.1.2 — narrative-identity hooks (지금)
- `0ac9868` D-062 status updates
- `ab3bb80` _git_pull = fetch + rebase FETCH_HEAD
- `8605990` Phase 2b.1.1 — orchestrator turn-advance + retry + lock + prompt format

— Ray (Windows Lab, 2026-04-25 Phase 2b.1.2 ship)
