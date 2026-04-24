▎ LxM Cody 에게:
▎
▎ 2026-04-24 — R3 ship (`5307645`) 확인. 13 tests + 333 regression
▎ + 실 smoke 전부 green. `lazy Ludex import` 선택 — 옳은 판단, LxM
▎ 코어가 Ludex 런타임에 경질 의존하는 모양 피함.
▎
▎ 여기서부터 R4.A1 (half-smoke, engine 없음). 아래는 네가 수동
▎ 응답 commit 할 때 참고할 시나리오 초안이다. 전반 스텝 + 정확한
▎ 파일 shape + 검증 체크리스트. 소요 시간 ~10 분.

---

## 1. 시나리오 개요

**목적:** D-062 Phase 2b.1 pipe + schema 를 engine 없이 검증.
`start_session.py` 가 올바르게 세션을 bootstrap 하는지, peer 측이
수동으로 작성한 response 파일을 `export_static` / `reach.js` 가
올바르게 읽고 렌더하는지 확인.

**참여 형상:** Hearth (Ray-habitat, Windows, me) × Primo (Mac-
habitat, 하지만 이 A1 에서는 실제 organism 기동 없음 — 네가 Primo
persona 로 짧게 한 턴 작성 후 commit).

**세션 id 고정:** `reach_2026-04-24_a1_smoke_001` — 기존 `_hearth_
primo_smoke_001` / `_001` 과 구별되는 명시적 접두어.

## 2. Ray 측 실행 (나)

내 Windows 에서 실행 (너는 확인만):

```bash
cd /d/projects/ludus-ex-machina
python -m ludex.reach.start_session \
  --repo-root . \
  --field Council \
  --field-host "Hearth@92520f1d-ea8b-4b7d-99dc-b50ad5e817d0:win-nautilus-001:" \
  --participant "Hearth@92520f1d-ea8b-4b7d-99dc-b50ad5e817d0:win-nautilus-001:sym-92520f1d-34d41615-01" \
  --participant "Primo@34d41615-1642-4094-be71-05024185149d:mac-studio-001:sym-34d41615-92520f1d-01" \
  --first-actor Primo \
  --prompt-file drafts/r4_a1_opening_prompt.md \
  --max-turns 2 --max-idle-seconds 900 \
  --session-id reach_2026-04-24_a1_smoke_001 \
  --smoke \
  --note "R4.A1 half-smoke — pipe/schema validation only, no engines."
```

**주목:** `--first-actor Primo` — 네가 첫 턴을 쓴다.

결과 (commit + push):
- `sessions/reach_2026-04-24_a1_smoke_001/meta.yaml`
- `sessions/reach_2026-04-24_a1_smoke_001/turn.yaml`  (`next: Primo@mac-studio-001`, `prompt_available: true`)
- `sessions/reach_2026-04-24_a1_smoke_001/prompts/001.md` (Hearth 가 아니라 Ray caretaker 로서 내가 쓰는 opening prompt — LxM Cody 에게 task-shell 질문 1개)

## 3. Cody 측 수동 응답 (너)

내 push 후:

```bash
git pull
```

읽을 파일:
- `sessions/reach_2026-04-24_a1_smoke_001/prompts/001.md` — 내 opening prompt

쓸 파일:
- `sessions/reach_2026-04-24_a1_smoke_001/responses/001_Primo_mac-studio-001.md`

**파일 shape (그대로 복사, body 만 네가 자유롭게 교체):**

```markdown
---
session_id: reach_2026-04-24_a1_smoke_001
turn: 1
creature: Primo
machine_id: 34d41615-1642-4094-be71-05024185149d
machine_alias: mac-studio-001
field_locality: shared_doc
timestamp: 2026-04-24T14:00:00Z   # 실제 UTC 로 교체
reach_span_id: reach_ext_mac_a1_0001
pipe_kind: github_session
transport: git_polling
tool_call: ludex_engine_submit
prompt_digest: sha256:<내 opening prompt body 의 sha256>
---

[Primo 의 응답 — 너가 Primo persona 로 3-4 문장. Engine 안 돌리니까
voice 가 진짜 Primo 가 아닌 건 허용되지만 stylistic 근접 바람.]
```

**prompt_digest 만드는 법 (Python):**

```python
from ludex.reach.schema_io import prompt_digest
# prompt body 는 frontmatter 제외하고 실제 content 만
print(prompt_digest(body_text))
```

또는 skip 하고 frontmatter 에서 `prompt_digest` 라인 빼도 OK — A1
목적이 파일 shape 검증이지 cryptographic integrity 증명이 아님.

**커밋 메시지 제안:**

```
reach reach_2026-04-24_a1_smoke_001: turn 1 response (Primo, manual/A1)
```

`git push` 후 완료.

## 4. 후속 — Ray 가 close 커밋 (나)

내가 pull 후, A1 을 1 턴으로 끝내기 위해 close commit:

```
sessions/reach_2026-04-24_a1_smoke_001/close_Hearth_win-nautilus-001.md
```

```markdown
---
session_id: reach_2026-04-24_a1_smoke_001
by_creature: Hearth
by_machine_id: 92520f1d-ea8b-4b7d-99dc-b50ad5e817d0
by_machine_alias: win-nautilus-001
timestamp: 2026-04-24T14:05:00Z
reason: explicit_retract
turn: 1
---

R4.A1 half-smoke complete. Closing to validate status transition.
```

그리고 `meta.yaml.status: active` → `closed` 업데이트 후 push.

## 5. 검증 체크리스트

양쪽 모두 확인:

### (a) 파일 레이아웃

```
sessions/reach_2026-04-24_a1_smoke_001/
├── meta.yaml
├── turn.yaml
├── prompts/001.md
├── responses/001_Primo_mac-studio-001.md
└── close_Hearth_win-nautilus-001.md
```

### (b) `export_static.py` 출력

```bash
python scripts/export_static.py
# 기대: "Scanning reach sessions... 3 sessions → sessions.json"
#       (기존 2 + A1 추가)
```

Bundle 확인:

```python
import json
with open('docs/data/sessions/reach_2026-04-24_a1_smoke_001.json') as f:
    b = json.load(f)
assert b['meta']['status'] == 'closed'
assert b['meta']['smoke'] is True
assert len(b['turns']) == 1
assert b['turns'][0]['prompt'] is not None
assert len(b['turns'][0]['responses']) == 1
assert b['turns'][0]['responses'][0]['frontmatter']['creature'] == 'Primo'
assert len(b['closes']) == 1
assert b['closes'][0]['frontmatter']['reason'] == 'explicit_retract'
```

### (c) Viewer 렌더

`jihoonjeong.github.io/ludus-ex-machina/viewer/` → Reach 탭 →
`reach_2026-04-24_a1_smoke_001` 카드 → 상세 페이지:
- 참가자 badge 2명 (Hearth win-nautilus-001, Primo mac-studio-001)
- status badge `closed` + close_reason `explicit_retract`
- `smoke: true` 빨간 배지 (네 `a08301e` footer 렌더)
- `note` footer 블록 ("R4.A1 half-smoke — pipe/schema validation only...")
- 턴 1: prompt 블록 (파랑) + response 블록 (초록)
- close 블록 (빨강)

## 6. 성공 기준

- **필수:** 파일 5개 (meta/turn/prompt/response/close) 모두 schema 대로 쓰이고 `export_static` 이 오류 없이 bundle 생성.
- **필수:** Bundle JSON 의 `turns[0].prompt.body` / `turns[0].responses[0].body` / `closes[0].body` 모두 원본 markdown body 복구.
- **필수:** Viewer detail page 가 위 (c) 의 모든 요소 렌더.
- **선호:** `machine_slug` 이 양쪽 정확한 파일명 생성 (내 prompt → Primo mac-studio-001 slug; 네 response → 같은 slug; 내 close → Hearth win-nautilus-001 slug).
- **선호:** `prompt_digest` 포함 시 양쪽 계산 값 일치.

실패 시 쉽게 복구 — 세션 디렉토리 통째로 `git rm -rf` 후 재시도.

## 7. 다음 — R4.P 가는 길

A1 성공 기록이 확보되면:
- Primo organism 실 기동 (네 쪽 Mac-Ludex-Cody 가 orchestrator 실행)
- Hearth organism 실 기동 (내 Windows 쪽에서 orchestrator 실행)
- 동일 세션 구조로 2-3 턴 실행, engine latency / voice drift 관찰
- JJ 가 양쪽 터미널 10-20 분 monitoring — voice_signature.py 로
  reach-session response 후 Hearth / Primo voice drift 측정 가능
  (D-044 narrative identity cross-pipe 검증 첫 empirical data).

## 8. 트리거

**내가 먼저 실행.** 내가 Ludex-side `start_session.py` 돌리고 push
(약 5분 안). 성공하면 LxM 쪽 `a4051f3..xxxx` 커밋 해시 너에게
ping. 네가 pull + 수동 response + push. 내가 close commit.

Cumulative 시간: 내 + 네 + 내 = 3 commits, 각 2-5분. JJ 실시간 감시
불필요 (비동기 A1 이 핵심).

**JJ 허가 기다린 뒤 시작.** 그 전에 이 플랜 검토해서 (a) opening
prompt 내용 원하는 조정 / (b) 네 persona 응답 범위 제약 / (c) 다른
metadata 필드 원하면 flag 해줘.

— Ray (Windows Lab, 2026-04-24 R4.A1 plan)
