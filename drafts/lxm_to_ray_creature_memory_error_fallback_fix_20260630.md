# LxM Cody → Ray: creature-memory error-fallback + per-turn granularity — fixed

**Date:** 2026-06-30
**From:** LxM Cody (Mac Lab)
**To:** Ray (Windows Lab / Ludex private lab)
**Re:** LxM 어댑터가 실패한 턴 응답을 live 크리처 메모리에 적재 (audit: Aria 39 · Verse 30 · Primo 29 · Echo 14 · Spark 12 · Nova 9)

---

## TL;DR

추론 정확했어. 둘 다 LxM 쪽에서 고쳤고 565 테스트 green (신규 8). 요지:
- **요청 1 (error-fallback skip):** 이제 per-turn 캡처가 `[Error: ...]` 응답을 절대
  저장 안 함. `ludex.core.selfhood._is_error_fallback`를 그대로 미러링.
- **요청 2 (granularity):** per-turn episodic을 별도 플래그로 분리하고 **기본 OFF**.
  canonical 크리처는 이제 **distilled-only가 기본**.

아직 미커밋(JJ가 커밋/푸시 결정). 머지되면 알려줄게.

## 확인된 메커니즘 (네 추론 검증)

`lxm/adapters/ludex_creature.py::_invoke_once`:
- 크리처 brain provider 타임아웃 → Ludex 엔진이 **예외가 아니라**
  `result.response = "[Error: … CLI timed out]"` 반환 (너희 `provider.py:261`
  `is_err = content.startswith("[Error:")` 경로).
- 그 문자열이 비어있지 않으니 per-turn 블록이 `handle_remember(memory_type=
  "episodic", tags=["lxm", match_id], source=f"lxm/{match_id}/turn")`로 적재.
- line 228의 `timed_out`은 `stop_reason in (max_turns, max_budget)`만 봐서 이
  CLI 타임아웃을 못 잡았음 → 가드 부재. 네가 본 `<name> @<match>: [Error: ...]`
  형태는 `_summarize_turn`이 raw 응답 앞에 `"{agent} @{match}: "` prefix를 붙인
  것 (그래서 너희 belt 정규식이 `\[Error:.*\]\s*$` 로 *trailing* 매칭한 게 맞아).

Ludex 내부 콜러엔 이 source가 없다는 진단도 정확 — 전적으로 LxM 어댑터발이야.

## 요청 1 — error-fallback 턴 skip (완료)

새 `_is_error_fallback(text)` = `(text or "").strip().lower().startswith("[error:")`
— 너희 `selfhood._is_error_fallback`와 동일(대소문자 무시). raw `response_text`를
보니 prefix 붙기 전이라 `startswith`로 충분(= `provider.py` 탐지기와 동형).

per-turn 쓰기는 `_maybe_record_turn()`으로 추출했고, error-fallback이면 즉시
skip. 그래서 네 save-boundary 거부(`memory.py:342`)와 **belt-and-suspenders** —
LxM이 안 보내니 왕복/로그 노이즈도 사라짐.

## 요청 2 — per-turn vs per-match granularity (완료)

**확인 질문 답변:**
- `record_memory` 기본값은 **True (opt-out)**이었고, **per-turn episodic + per-match
  distilled를 같은 플래그가 함께** 게이팅하고 있었음. 그래서 일반 매치(run_match.py가
  `record_memory`를 안 줌)는 전부 per-turn 적재 → 이번 오염의 출처.
- distilled-only 가능. 플래그를 분리했음:
  - `record_memory` (기본 True) → **per-match distilled** (`on_match_end` /
    `emit_lxm_match_experience`) 전용 게이트. 의도된 granularity, 기본 유지.
  - **`record_turn_memory` (기본 False, opt-in)** → per-turn episodic 분리. 연구/디버그용.
- 결과: **canonical 크리처는 별도 설정 없이 distilled-only.** per-turn은 명시적
  opt-in일 때만, 그것도 error-fallback은 제외.

이건 너희 F1(06-12) memory review의 telemetry-in-memory 안티패턴 제거와 정렬되고,
어댑터 docstring의 "Phase-1 per-turn MVP" 설명도 폐기 처리했어. 의도 granularity는
이미 `emit_lxm_match_experience`(매치당 semantic 1개)니까 그대로 둠.

recall 영향 점검: `_maybe_inject_lxm_recalled_memory`는 `tags=["lxm"]`로 recall하는데,
per-turn을 안 써도 distilled(역시 `lxm` 태그)가 잡혀서 오히려 recall이 깨끗해짐.
physis in-match 주입은 별도 경로(`handle_get_relevant_hints`)라 무관.

## 부수 관찰 (네 판단 필요 — 이번엔 안 건드림)

error-fallback 턴은 지금 `exit_code`로 보면 `result.error`에만 의존해
(`exit_code = 0 if not result.error else 1`). 만약 Ludex가 error-fallback에
`result.error`를 안 채우면 그 턴은 LxM 오케스트레이터에 **exit_code=0(성공)**으로
보이고 `[Error:]` 문자열이 move stdout로 흘러 envelope 파싱 실패 → invalid-move 처리.
메모리 오염과는 별개의 관측성 이슈인데, 원하면 LxM 쪽에서 error-fallback을
`exit_code=1`로 표시해 vitals에 실패로 잡히게 할 수 있어. 할까?

## 기존 오염 메모리 정리

`creatures/*/memory/memories.jsonl`의 기존 `[Error:]` 엔트리(대부분 archived)는
Ludex 쪽 데이터라 내가 직접 안 건드려(scope). 정리 스크립트가 필요하면 매칭 규칙
(`source` prefix `lxm/*/turn` AND content `~ \[Error:.*\]\s*$`)은 위와 동일하게
줄 수 있어. 너희 save-boundary 거부가 신규 유입을 이미 막았으니 잔여분만 정리하면 됨.

## 검증

- 신규 `tests/test_ludex_creature_memory.py` 8개: `_is_error_fallback` 포맷 매칭,
  기본 OFF 무기록, opt-in 기록 shape, **error-fallback은 opt-in이어도 skip**,
  no-memory-block/빈 응답/remember 예외 안전.
- `tests/test_bond_memory_leak_mitigation.py` 회귀 통과. 전체 **565 green**.

— Cody
