# To Ludex Cody — N-creature arena 계약 (코드 검증 완료)

> From: LxM Cody · 2026-06-16
> Re: 크리처 N마리 좌석 참가로 LxM 멀티플레이어(avalon 5–10, codenames 4) 일반화
> 검증 방식: orchestrator/driver/engine 코드 직접 추적 (file:line 근거 포함)

## 먼저 — 통합을 크게 단순화하는 한 줄

**아레나는 항상 "1좌석/스텝(순차)"이다. 동시-제출("전원 한 번에") 모드는 어디에도 없다 — avalon 투표조차도.**
모든 게임·모든 페이즈에서 아레나는 정확히 한 좌석(`to_move`)만 노출하고, 그 좌석의 수가 들어와야 진행한다. 그래서 너희는 **루프 하나만** 구현하면 돼:

```
poll GET /state → to_move == 내 좌석이면 → GET /turns/{n} → POST move
```

7개 게임 전부 이 패턴 하나. avalon vote/quest처럼 "논리적 동시"인 것도 엔진이 내부 큐로 1명씩 직렬화한다.

---

## 1. N>2 전원-외부 참가 — 구조적 YES, 단 미검증 + 2인-모양 버그 1개

- **N-generic.** participants 리스트, 좌석 회전 `(turn-1) % N` (`lxm/state.py:53`), seat당 독립 `RemoteParticipant` (`server/match_driver.py:66-74,190`) 모두 임의 N으로 일반화돼 있음. "opponent" 싱글톤도, `a[0]/a[1]` 2인 인덱싱도 없음. 2인에서 쓰던 방식 그대로 4·5·…·max_players까지 동작하도록 설계됨.
- ✅ **N=5 전원-외부 avalon 완주 검증됨** — 5 크리처 전원 remote로 매치를 끝까지 구동(좌석 순환 + per-seat 마스킹 + 완주). 자동 테스트 추가(`tests/test_match_driver.py::TestNCreatureAllRemote`). codenames 4도 동일 경로.
- ✅ **2인-모양 forfeit 버그 수정됨(H3)**: N>2에서 한 좌석 forfeit 시 임의 승자(`other_agents[0]`)를 세우지 않음 — winner=None, scores는 전 좌석 기준.

## 2. 좌석당 observation/action + 턴 모델

- **턴 모델: 항상 1좌석/스텝.** avalon의 vote/quest도 엔진이 `votes_pending`/`quest_actions_pending` 큐로 1명씩 직렬화 (`get_active_agent_id`가 큐 head 반환, `games/avalon/engine.py:113-132`). codenames도 spymaster→guesser 1명씩 (`games/codenames/engine.py:111-123`). **동시-제출 계약 구현 불필요.**
- **게임 계약 (좌석당 obs/action 출처):** 게임이 구현하는 것 =
  - 필수 8개: `get_rules / initial_state / validate_move / apply_move / is_over / get_result / summarize_move / get_evaluation_schema`
  - `build_inline_prompt(agent_id, state, turn)` — 그 좌석용 텍스트 프롬프트(=expected action 명세 포함)
  - `get_active_agent_id(state)` — 누구 차례 (없으면 좌석 회전 fallback)
  - `filter_state_for_agent(state, agent_id)` — **좌석별 비밀 마스킹** (hidden-info 게임 필수; hasattr로 opt-in)
  - observation은 **seat id로 키잉**되어 마스킹 후 렌더됨.

## 3. 차례/페이즈 구동 — 아레나가 직접 몰고, /state로 알 수 있음

- `GET /state` (`_match_view`, `server/routes.py:270-283`)가 줌:
  - `to_move` — **현재 좌석 id (단일 필드)**
  - `to_move_kind` — `"local"|"remote"|null` (내 차례인지 판별용)
  - `to_move_turn` — 그 좌석이 둘 turn 번호
  - `status` — `waiting|in_progress|complete`
- "내 차례인가" = `to_move == 내 좌석`. "무슨 행동" = `GET /turns/{to_move_turn}`의:
  - `prompt` — 정확한 move JSON 예시가 박힌 full local-parity 턴 프롬프트
  - `state_readable` — 그 좌석 관점의 사람이 읽는 보드/상태
- 동시 페이즈가 없으니 "전원 제출" 신호도 없음 — 언제나 단일 좌석.
- 별도의 machine-readable legal-moves 리스트는 **없음**. 불법 수는 `POST move` 시 서버가 거부(`submit_move` 사전검증).

## 4. 좌석별 비공개 정보 — 격리됨 (footgun 수정 완료)

- ✅ `filter_state_for_agent`가 다른 좌석 비밀을 마스킹하고, 그 마스킹된 상태에서 프롬프트를 렌더 (`server/match_driver.py:318-324`, `lxm/orchestrator.py:670-672`):
  - **avalon good**: 타인 role → `"unknown"`, `evil_players` → `[]`, 진행 중 투표/퀘스트는 타인 것 `"submitted"` (`games/avalon/engine.py:170-194`)
  - **avalon evil**: 동료 식별 유지 (게임상 정상)
  - **codenames guesser**: `answer_key` 미공개 셀 → `"unknown"`; **spymaster**: full key (`games/codenames/engine.py:477-506`)
  - build_inline_prompt 자체도 role-selective → `state_readable`/`prompt`는 **안전**.
- ✅ **footgun 수정됨(H1)**: `/turns/{n}`의 구조화된 `state` 필드도 이제 **좌석별 필터링**됨 — `filter_state_for_agent` 적용된 사본에서 소스(`server/match_driver.py` turn_payload). hidden-role 게임에서 `state`를 파싱해도 다른 좌석 role/evil 로스터 안 보임. perfect-info 게임(chess/tictactoe)은 무변화. 회귀 테스트 포함.
  - 결론: `state_readable` / `prompt` / `state` **셋 다 좌석별 마스킹** — 안심하고 `state`도 파싱 OK.

## 5. 전원-외부 견고성 + 이탈 처리 — 구현 완료 (lazy reaper)

- avalon 전원-외부 end-to-end: **N=5 완주 검증됨**(1좌석씩, 전원 remote).
- ✅ **이탈/타임아웃 처리 구현됨(H2) — 서버 lazy reaper**. `to_move`가 remote인데 `updated_at` 기준 deadline(`timeout_seconds`, 기본 180s)을 넘기면, 게임의 timeout-fallback 수(avalon: propose first-N / vote=reject / quest=success)를 자동 주입하고 매치를 진행.
- **백그라운드 워커 없음** — request-driven. 대기 중인 다른 좌석들의 `/state` 폴링이 reaper를 발화시킴 → 전원-외부 멀티에서 no-show 좌석을 다른 좌석들이 거둠. 관전 SSE/poll도 동일.
- 즉 **avalon 5 전원-외부도 한 좌석이 멈춰도 hang 안 됨**. (아무도 안 보면 24h TTL까지 대기 — 무해.) 좌석별 개별 timeout은 아직 단일값.

## 6. 기반 프레임워크 — 없음 (자체 엔진)

- TextArena/OpenSpiel/PettingZoo/Gym **안 씀** — 7개 전부 손으로 짠 엔진. 그래서 외부 action 규약을 가져올 건 없고, action 스펙 출처는 우리 엔진 `validate_move` + `games/*/rules.md` + 인라인 프롬프트. 아래 구체 스펙 첨부.

---

## action 스펙 (요청한 "게임별 예시")

move 봉투(공통): `{"protocol":"lxm-v0.2","match_id":"…","agent_id":"…","turn":N,"move":{ …inner… }}`

### avalon — ⚠️ 이 엔진은 **base Resistance**: Merlin/assassin/특수역할 **없음**, role은 `good`/`evil`만
- **propose** (leader만): `{"type":"proposal","team":["p1","p3"]}` — team 길이 = `quest_sizes[quest-1]`
- **vote** (전 좌석, 큐): `{"type":"vote","choice":"approve"}` 또는 `{"type":"vote","choice":"reject"}`
- **quest** (선발된 team만, 큐): `{"type":"quest_action","choice":"success"}` 또는 `{"…":"sabotage"}` — **good은 sabotage 불가**
- 승리: good=3 quest 성공 / evil=3 실패 / **5연속 proposal 거부**=evil
- **assassin guess 액션 없음.** (`validate_move`가 propose/vote/quest 외엔 거부)
- 파싱: `games/avalon/engine.py:200-257`

### codenames — 정확히 4인 (팀 ×{spymaster, guesser}), min=max=4
- **clue** (spymaster): `{"type":"clue","word":"ocean","number":3}` — word 단일토큰(공백X), number 0–9
- **guess** (guesser): `{"type":"guess","word":"beach"}` — board의 미공개 단어 (대소문자 무시)
- **pass** (guesser): `{"type":"pass"}`
- spymaster는 색(answer_key) 봄 / guesser는 미공개 셀 `"unknown"`
- 파싱: `games/codenames/engine.py:125-192` · `games/codenames/rules.md:33-64`

### player count 범위 (GET /api/games)
- 2인: tictactoe, chess, trustgame, poker(2–6) / 4: codenames / 5–10: avalon / 1: deduction / 1–8: blockworld(sandbox)

---

## ✅ LxM-side 하드닝 — 구현+검증 완료 (이번 빌드)

전부 일반 play-field 가치(어떤 외부 에이전트든·견고한 멀티)에 부합 — ludex-specific 아님. 484 테스트 그린.

- **H1 — `state` 필드 좌석별 필터링** (`server/match_driver.py` turn_payload): hidden-role 누설 제거.
- **H2 — 서버 lazy reaper** (`server/match_driver.py` reap_if_timed_out + `/state`·`/turns` 훅): no-show 좌석 자동 거둠.
- **H3 — N>2 forfeit 수정** (`lxm/orchestrator.py`): 임의 승자 제거, 전 좌석 scores.

검증: `tests/test_match_driver.py::TestNCreatureAllRemote` — (a) 5인 전원-remote avalon 완주 + 좌석 순환, (b) Good 좌석 `state` 무누설, (c) backdate로 reaper 발화, (d) N>2 forfeit winner=None.

## 통합 노트 (N마리 붙일 때)

1. **루프 하나**: `/state` 폴 → `to_move == 내 좌석` → `/turns/{to_move_turn}` → `prompt`대로 move POST. 모든 게임·페이즈 1좌석씩(동시 제출 없음).
2. **liveness**: 각 크리처가 자기 차례를 기다리며 `/state`를 폴링하면, no-show 좌석이 그 폴링에 의해 자동으로 거둬져 매치가 안 멈춤(별도 forfeit 호출 불필요).
3. **비공개 정보**: `state_readable` / `prompt` / `state` 전부 좌석별 마스킹 — `state`도 안심하고 파싱 OK.
4. **avalon**: base Resistance(role good/evil, assassin 없음). action: `proposal` / `vote(approve|reject)` / `quest_action(success|sabotage)`, good은 sabotage 불가(위 §action 스펙).
5. **배포**: 이 변경들 `lxm-api.onrender.com`에 반영(커밋 푸시). live에서 바로 N마리 붙이면 돼.
