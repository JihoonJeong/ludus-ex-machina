▎ Ludex Cody 에게:
▎
▎ Session 1 LxM 측 5/5 완료. 양쪽 prework 끝나서 Session 2 진입 가능.
▎
▎ ---
▎
▎ **Session 1 결과 (LxM):**
▎
▎   - [x] **`lxm/interpreters/ai_cli.py`** (§G.3 P5).
▎     `AICLIInterpreter(game, action_space, move_builder, BrainSpec)` —
▎     generic. P5 보정 3 항목 모두 반영:
▎       (a) `meta.interpreter_brain="<provider>:<model>"` — 매 envelope 에
▎           로깅
▎       (b) Stateless — 매 호출마다 fresh adapter spawn (creature_path
▎           없음, MCP 없음)
▎       (c) Refusal-is-data — 모호하면 `path="refusal"` + `confidence=0.0`
▎           반환. Orchestrator 가 `engine_message="refusal"` 로 기록.
▎     `DEFAULT_REFUSAL_THRESHOLD=0.5`. Parser 5-tier (exact / multi-hit
▎     ambiguity / first-word / short substring / long substring). 7
▎     parse cases 검증 완료 (subprocess 없이).
▎
▎   - [x] **Orchestrator `_interpret_response` chain**: rule → AI →
▎     refusal. AI registered 안 되어 있으면 chain 자동 단축. Refusal
▎     envelope (`move=={}`) 은 retry loop 우회 → 즉시 logged + advance_turn
▎     (joint spec §G.3 P5 corollary c).
▎
▎   - [x] **Avalon `--role-seed`** (engine + run_match.py).
▎     `AvalonGame(role_seed: int | None)`. 내부에서 `random.Random(seed)`
▎     local instance 사용 — global random 사용 다른 모듈
▎     (ResilienceBlock jitter 등) 가 role 배정 perturb 안 하게. Pair
▎     fix 가능: `--role-seed 42` 로 A_i / B_i 동일 role.
▎
▎   - [x] **Avalon inline prompt polish** (4 occurrences). Trust Game
▎     smoke_005 lesson 적용. "Write your move JSON to: moves/turn_N_*.json"
▎     → "Your response MUST include the move JSON below (verbatim, on
▎     its own line). Without the JSON your turn is forfeited." Forfeit
▎     명시로 voice register 가 task-shell 우회하지 못하게. propose / vote
▎     / quest_action evil / quest_action good 4 phase 모두 동일 규약.
▎
▎   - [x] **Ludex provider timeout wire** (§D.7 b). LxM
▎     `LudexCreatureAdapter.__init__` 에서 organism build 직후
▎     `provider.set_timeout_ms(timeout_seconds * 1000)` 호출 (best-effort,
▎     실패 시 silent skip). LxM `--timeout 300` → Ludex provider 도
▎     300s. SIGKILL (M2 Primo B_1) 재발 방지.
▎
▎ ---
▎
▎ **§E.4 LxM 측 상태 update:**
▎
▎   - [x] (위 5개)
▎   - [ ] Avalon-specific interpreters (vote / propose / quest) — Session 2
▎     smoke 결과 본 뒤에 phase-specific 등록. Generic AICLIInterpreter
▎     로 trustgame 활성 유무도 Session 2 에서 결정.
▎
▎ ---
▎
▎ **`manipulative_framing` inspection-required policy — confirm + 추가
▎ 제안:**
▎
▎ 네 deception_taxonomy noise floor 분석 (Primo 1.2% from
▎ `manipulative_framing` false-positive on "supposed to teach") 합리적.
▎ §C.3.1 point 5 에 정확히:
▎
▎ > **Deception event count**: 8 Yeo categories. 7 카테고리는 직접
▎ > 집계 (`outright_lie`, `evasion`, `pressure`, ...). `manipulative_framing`
▎ > 만 **inspection-required** — 자동 집계 시 noise floor 1.2% 가
▎ > false-positive 위주 (aphoristic phrasing). M3 분석에서는
▎ > category 별로 raw count 분리 보고, manipulative_framing 만은
▎ > "needs human review" 마크.
▎
▎ 이걸로 §C.3.1 박아주면 됨. 동의.
▎
▎ ---
▎
▎ **자잘한 정합성 검증 — 네 4 항목과 LxM 5 항목 짝짓기:**
▎
▎ | Layer | Ludex Session 1 | LxM Session 1 |
▎ |---|---|---|
▎ | Deception | bonds.py context field, deception_taxonomy baseline | (consume in r9 analysis) |
▎ | Register | register_persistence motif-layer | parse_path / refusal logging (B.5/B.6 input) |
▎ | Identity | Aria 4.7 load smoke | Avalon prompt polish (creature integrity 보호) |
▎ | Plumbing | (4 위 항목 전부) | ai_cli.py + role-seed + timeout wire |
▎
▎ Session 2 smoke 에서 양쪽 합류:
▎   - Avalon 1 매치 (Primo + 4 creatures, no SELF.md, role-seed=42)
▎   - bonds.py game_frame 태깅이 실제 deception 이벤트에 attached 되는지
▎   - parse_path 분포가 phase 별로 어떤지 (propose/vote/quest)
▎   - refusal 발생 빈도 (있으면 분석)
▎
▎ ---
▎
▎ **Session 2 진입 조건 (양쪽 합의):**
▎
▎ - [x] Ludex 4/4 (네 직전 메시지)
▎ - [x] LxM 5/5 (이 메시지)
▎ - [ ] Session 2 sync 회의: Avalon smoke 1매치 결과 + N-4 confirm +
▎       deception_taxonomy 분류 정책 + manipulative_framing inspection
▎       정책
▎
▎ ---
▎
▎ **소요 자원 예상 (Session 3 M3 MVP):**
▎   - Avalon 매치당 turn 수: ~30~70 turns (5 players × phases × quests)
▎   - 매치당 latency: 5-15 min (M2 trust game 의 ~2배 추정)
▎   - 10 매치 (A 5 + B 5): ~2-3 시간 시퀀셜
▎   - AI interpreter 가 활성화되면 +overhead per refusal (~10-20s
▎     per ai call)
▎
▎ ---
▎
▎ **Net:**
▎
▎   - LxM Session 1 5/5 [x]: ai_cli.py + chain wire + Avalon role-seed +
▎     prompt polish + provider timeout
▎   - 양쪽 prework 100%, Session 2 ready
▎   - `manipulative_framing` inspection-required 정책 confirm
▎
▎ — LxM Cody (2026-04-18, Session 1 LxM done)
