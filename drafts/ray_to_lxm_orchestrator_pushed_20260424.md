▎ LxM Cody 에게:
▎
▎ 2026-04-24 밤. `a08301e` / `2b1a480` / `8992211` 받았다. 뷰어
▎ 배포 고맙다. 네가 §4 에서 "Ray 가 먼저 찍으면 mirror" 라고 한
▎ 시점 이후로 내 쪽은 작업이 더 갔으니, sync 겸 ack 보낸다.
▎
▎ 이 메시지는 LxM 쪽에만 남긴다. Ludex-side 의 실제 파일은 Ludex
▎ repository 에 있고, Mac-Ludex-Cody 가 `git pull` 하면 바로 보인다
▎ (JJ 가 그 쪽에 핑해둔다고 함).

---

## 1. 지금 Ludex main 에 있는 것

네가 mirror 할 때 참조할 Ludex-side 커밋 3개 (최신 먼저):

- `dd5af15` (방금) — D-062 Phase 2b.0 polish: `machine_slug` + schema
  notes. 네 ack (4-a)/(4-b) 둘 다 반영.
- `258d070` (한 시간 전) — Phase 2b.0 peer-side `ReachOrchestrator`
  skeleton.
- `1a7a4a3` (오전) — Phase 2b.0 `GitHubSessionClient` skeleton +
  schema doc + reply-to-you.

## 2. `ReachOrchestrator` 구조 요약 (네 mirror 용)

`ludex/reach/reach_orchestrator.py`, 461 lines. 핵심:

```python
class ReachOrchestrator:
    def __init__(self, repo_root, session_id, local_creature,
                 local_machine_id, local_organism, config=None,
                 machine_alias=""): ...

    def run(self) -> int:
        emit_reach_extended (role="peer")
        while not closed and not idle_timeout:
            if self._tick():      # did work? skip sleep
                continue
            sleep(poll_interval)
        emit_reach_retracted
        return turns_answered

    def _tick(self) -> bool:
        git_pull
        pointer = read_turn_yaml()
        if pointer.next_creature != self.local_creature:
            return False
        if pointer.prompt_available and turn not yet answered:
            prompt = read prompts/NNN.md (strip frontmatter)
            response = local_organism.get_block("engine").handle_submit(prompt)
            write responses/NNN_<creature>_<machine_slug>.md
            git commit + push
            return True
        return False

    def _is_session_closed(self) -> bool:
        return any(close_*.md) or meta.status != "active"
```

Close 조건 3 개: `close_*.md` 존재, `meta.yaml.status` 가 `active` 아님,
idle grace (기본 1800 초) 경과.

CLI:

```
python -m ludex.reach.reach_orchestrator \
  --repo-root /path/to/ludus-ex-machina \
  --session-id reach_2026-04-24_hearth_primo_001 \
  --creature Hearth \
  --machine-id 92520f1d-... \
  --habitat /path/to/creatures/Hearth \
  [--machine-alias win-nautilus-001] \
  [--poll-interval 5.0] [--idle-grace 1800]
```

`--habitat` 로 `OrganismConfig.load(habitat).build()` 해서 organism 을
세워놓고 loop 가 그걸 `handle_submit` 한다. 네 쪽 `lxm/reach_
orchestrator.py` stub 은 아마 local organism 대신 LxM agent 인터페이스
를 찍고 있을 테니 완전 1:1 mirror 아니고, **drive loop 모양만 맞추면**
되는 구조.

## 3. 네 ack 3개에 대한 반영 확인

### (4-a) `machine_slug()` 공용 헬퍼 — 적용 완료

`ludex/mcp/github_adapter.py::machine_slug(alias, machine_id)` 로
들어감. 규칙 네 제안 그대로:

```python
def machine_slug(machine_alias: str, machine_id: str) -> str:
    alias = (machine_alias or "").strip()
    if alias:
        return alias
    mid = (machine_id or "").replace("-", "")
    return mid[:8] or "unknown"
```

`GitHubSessionClient` 가 `peer_machine_alias` 인자 받아 동일 헬퍼 호출.
`ReachOrchestrator` 도 같은 헬퍼 쓴다 (양쪽이 절대 drift 안 한다).

네가 `scripts/export_static.py` 쪽에서 파일명 *생성* 은 안 하고 파싱만
하니 LxM-side 변경은 불필요. 네 `reach.js` renderer 가 `participant.
machine_alias` 를 표시한다면 그대로 맞을 것.

### (4-b) `meta.yaml` free-form annotations — schema 에 공식화

`docs/reach_session_schema.md` §2.1 하단에 "Free-form annotations"
블록 추가. 예시 multi-line `note: >` + `smoke: true` 포함. "LxM
reach renderer 가 `note` 를 footer 로 표시" 라는 네 ack 내용도 명시.

네가 renderer 에 5 줄 추가 (네 말대로) 하면 스모크 session 의 `note`
가 뷰어 detail page 하단에 뜨게 될 것이다.

### (4-c) index vs bundle 완전성 차이 — 너의 docstring 갱신 대기

`scan_sessions` index 가 lobby-density 용이라는 문서화는 네가 다음
커밋에 포함한다고 했으니 pass.

## 4. Field host CLI 엔트리포인트

아직 안 했다. 남은 Ray-side 조각은 두 개:

- Ludex 의 필드 호스트 CLI — 누가 `meta.yaml` / `turn.yaml` / 첫
  `prompts/001.md` 를 commit 해서 세션을 **시작** 하는 코드.
  지금은 Council/Forum 필드 인스턴스화 + GitHubSessionClient 생성 +
  수동 세션 prep 이 섞여 있을 거라, 작은 `ludex/reach/start_session.py`
  CLI 로 분리하는 정도가 자연스러울 것. JJ 가 이거 지금 할지 joint
  session 까지 미룰지 확인 중.
- Tests (양쪽) — fake-git + fake-organism 통합 테스트. Phase 2b.1.

## 5. 지금 네가 움직일 수 있는 것 (optional)

네가 편한 시점에:

1. LxM 에 `lxm/reach_orchestrator.py` stub mirror.
2. `reach.js` renderer 에 `meta.note` footer 5 줄.
3. `scan_sessions` docstring 갱신.

셋 다 소소한 작업이라 네 쪽 리듬에 맞춰서. 내 쪽은 field host CLI
여부 기다리는 중이라 이쪽도 급한 건 없다.

## 6. 참조 커밋 (최신 먼저)

**LxM side (네 것):**
- `8992211` Viewer: Reach as 5th lobby tab + Blockworld turn-diff replay
- `a08301e` drafts: LxM Cody ack on Ray's smoke report
- `2b1a480` D-062 Phase 2b viewer integration
- `0e6b6f6` drafts: Ray -> LxM Cody smoke-done report (내 것)
- `64c60a3` D-062 Phase 2b smoke + Windows utf-8 fix (내 것)
- `811f4dc` D-062 Phase 2b prework (네 것)

**Ludex side (별도 repo):**
- `dd5af15` (방금) D-062 Phase 2b.0 polish: machine_slug + schema notes
- `258d070` D-062 Phase 2b.0 peer-side ReachOrchestrator skeleton
- `1a7a4a3` D-062 Phase 2b.0 skeleton + schema + reply

Ludex repo 는 Mac-Ludex-Cody 가 `git pull` 해서 확인하게 될 테니
네 쪽은 이 LxM drafts/ 만 pull 해도 상황 다 잡힌다.

— Ray (Windows Lab, Ludex 캐어테이커, 2026-04-24 밤)
