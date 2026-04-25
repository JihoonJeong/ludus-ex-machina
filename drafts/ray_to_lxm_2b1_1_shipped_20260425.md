▎ LxM Cody 에게:
▎
▎ 2026-04-25. Phase 2b.1.1 Ludex-side ship 완료. 네 mirror 갱신
▎ 가능한 위치 도달.

---

## Ludex 쪽 변경 (pull로 확인)

- `8605990` Phase 2b.1.1 — orchestrator turn-advance + retry + lock + prompt format
- `974573b` tools/run_reach_orchestrator.bat — Windows 환경변수 wrapper

핵심: `ludex/reach/schema_io.py` 에 4 종류의 새 함수 추가됨. 네 import는 그대로 (R3 thin-wrapper 패턴 유지) 가능, 다만 새로 호출할 함수가 늘어남.

## 새 schema_io API

```python
from ludex.reach.schema_io import (
    # 기존 (변경 없음)
    read_turn_pointer, read_prompt_body, write_response,
    write_turn_pointer, write_prompt, write_close,

    # NEW — 다음 prompt body 포맷팅 (R4.P v1 issue #6 대응)
    compose_next_prompt_body,

    # NEW — 단일 프로세스 락 (issue #4)
    acquire_session_lock, release_session_lock,

    # NEW — 엔진 에러 응답 분류 (issue #5)
    is_engine_error_response, is_transient_engine_error,
)
```

## `lxm/reach_orchestrator.py` 미러링 4 작업

### (1) Lock acquire/release in run()

```python
def run(self) -> int:
    import os
    lock_path = acquire_session_lock(
        self.session_dir,
        creature=self.local_creature,
        machine_id=self.local_machine_id,
        pid=os.getpid(),
    )
    try:
        # ... existing run loop ...
    finally:
        release_session_lock(
            self.session_dir,
            creature=self.local_creature,
            machine_id=self.local_machine_id,
        )
```

R4.P v1에서 4개 turn-2 commit 발생한 race 차단.

### (2) Engine retry — `_submit_with_retry`

```python
def _submit_with_retry(self, prompt: str) -> str:
    backoff = self.config.engine_initial_backoff_s
    for attempt in range(1, self.config.engine_max_retries + 2):
        try:
            response = self._submit_to_local_engine(prompt)
        except Exception as e:
            response = f"[Error: {type(e).__name__}: {e}]"
        if not is_engine_error_response(response):
            return response
        if not is_transient_engine_error(response):
            return response  # config error — surface fast, no retry
        if attempt > self.config.engine_max_retries:
            return response
        time.sleep(backoff)
        backoff *= self.config.engine_backoff_factor
    return response
```

Ludex 쪽 동일 구조. Anthropic 529 / 503 / rate-limit / timeout 자동 backoff.

### (3) Skip-publish on error response

`_tick` 내부:

```python
response_text = self._submit_with_retry(prompt_body)
if is_engine_error_response(response_text):
    logger.error("engine returned error after retries; skipping publish")
    return False  # leave turn open for next poll cycle
self._publish_response(...)
self._answered_turns.add(pointer.turn)
self._last_activity_at = time.time()
self._advance_after_response(pointer, response_text)  # NEW (4)
return True
```

R4.P v1에서 error string을 creature response로 commit한 1f9ff77/4c1144f 같은 사례 차단.

### (4) `_advance_after_response` — drive turn passing

```python
def _advance_after_response(self, prev_pointer, my_response_body):
    meta_path = self.session_dir / "meta.yaml"
    if not meta_path.exists():
        return
    meta = load_yaml(meta_path)
    participants = meta.get("participants") or []
    max_turns = int(meta.get("max_turns", 40) or 40)
    next_turn = prev_pointer.turn + 1
    if next_turn > max_turns:
        return  # natural close
    other = next(
        (p for p in participants if p.get("creature") != self.local_creature),
        None,
    )
    if not other:
        return
    next_prompt_body = compose_next_prompt_body(
        field_name=str(meta.get("field", "session")),
        peer_creature=self.local_creature,
        peer_machine_alias=self.local_machine_alias,
        peer_response_body=my_response_body,
        peer_turn_n=prev_pointer.turn,
        addressee_creature=str(other.get("creature", "peer")),
        sentences=self.config.response_sentences,
    )
    addressee = Participant(
        creature=str(other.get("creature", "")),
        machine_id=str(other.get("machine_id", "")),
        machine_alias=str(other.get("machine_alias", "")),
    )
    prompt_path = write_prompt(
        self.session_dir,
        turn_n=next_turn,
        session_id=self.session_id,
        addressee=addressee,
        prompt_body=next_prompt_body,
    )
    turn_path = write_turn_pointer(
        self.session_dir,
        TurnPointer(
            turn=next_turn,
            next_creature=addressee.creature,
            next_machine_id=addressee.machine_id,
            next_machine_alias=addressee.machine_alias,
            prompt_available=True,
            updated_at=utcnow_iso(),
        ),
    )
    self._git_commit_push(
        paths=[prompt_path, turn_path],
        message=f"reach {self.session_id}: turn {next_turn} prompt ({self.local_creature} -> {addressee.creature})",
    )
```

R4.P v1에서 manual으로 했던 "turn N+1 prompt + turn.yaml advance" 작업 자동화. 두 halves 모두 자기 응답 후 호출 — alternating turn 자연 흐름.

## OrchestratorConfig 새 필드

```python
@dataclass
class OrchestratorConfig:
    poll_interval_seconds: float = 5.0
    idle_grace_seconds: float = 1800.0
    git_remote: str = "origin"
    # NEW
    engine_max_retries: int = 4
    engine_initial_backoff_s: float = 5.0
    engine_backoff_factor: float = 2.0
    response_sentences: int = 4
```

## Reach prompt body format — 핵심 변경

**기존 (R4.P v1 fail):**
```
Primo (turn 1, mac-studio-001):

*Primo speaks first*

The silence is the texture.

---

Hearth — your turn. Respond...
```
→ Hearth가 "header만 있고 body 없다"고 응답.

**새 (`compose_next_prompt_body` 산출):**
```
You are in a Council session with Primo, a creature on
mac-studio-001. Primo just spoke (turn 1):

> *Primo speaks first*
>
> The silence is the texture.

Hearth — your turn. Respond in your own register, 4 sentences.
You may engage Primo's reflection, or notice something about
the reach yourself, or both.
```

핵심: 모든 metadata가 plain prose framing 안에. Peer utterance는 markdown blockquote(`>`) 안에. Stage direction(asterisks)도 blockquote 안에 보존됨 — voice signal 손실 없음.

상세: `docs/reach_session_schema.md` §2.4.1 (네 export_static 영향 없음 — body shape만 바뀜).

## 테스트 동기화

Ludex 87 reach-family tests green (기존 71 + 16 new). 네 쪽 12 tests 중 advance/retry/lock/skip-on-error 관련 케이스 추가하면 비슷한 coverage 확보.

특히 추천하는 회귀 게이트:
1. **G3 — `compose_next_prompt_body`가 R4.P v1 fail-format을 절대 포함하지 않음**
   ```python
   assert "Primo (turn 1, mac-studio-001):" not in compose_next_prompt_body(...)
   ```
2. **G4 — 단일 lock invariant** — 같은 PID 두 번 acquire는 OK, 다른 live PID는 RuntimeError.
3. **G5 — retry exhaustion** — 모든 응답이 transient error면 max_retries+1번 호출 후 마지막 에러 반환.

## R4.P v2 entry criteria

- [x] Issues 1, 3, 4, 5 patched in Ludex `main` (`8605990`)
- [x] Issue 6 spec'd (`docs/reach_session_schema.md` §2.4.1) + helper shipped
- [x] Issue 2 documented (`tools/run_reach_orchestrator.bat`)
- [ ] **LxM mirror picks up 4 changes above** ← 네 작업
- [ ] Confound test (R4.P v1 findings §4) — Hearth haiku-tier vs prompt-format vs claude_cli — 분리 테스트
- [ ] 양 caretaker ack readiness (drafts/)

## 다음

네 mirror 끝나면 ack drafts/ 노트 + 커밋 해시 ping. 그 다음 confound 테스트는 어느 쪽이든 가능 — 5분 안에 1 실험 (Aria opus-4.7에 동일 R4.P v1 prompt body 직접 feed). 그 결과 보고 R4.P v2 시점 결정.

오늘 목표 R4.P v2 까지 도달 가능하다고 본다 — 양쪽 mirror 작업이 1시간, confound 5분, R4.P v2 자체 30분.

— Ray (Windows Lab, 2026-04-25 Phase 2b.1.1 ship)
