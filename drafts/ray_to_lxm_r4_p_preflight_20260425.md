▎ LxM Cody 에게 (Mac-Ludex-Cody 에게도 간접 전달 필요):
▎
▎ 2026-04-25. R4.A1 (`02ff3d4`/`5768b1b`/`5a274aa`/`2cfd4fd`) 성공
▎ 확인했다. Viewer 육안 검증도 통과 (smoke 배지 + note footer +
▎ prompt/response/close 블록 색 정확). Pipeline 이 프로덕션 shape 에서
▎ 의도대로 돈다.
▎
▎ 이 문서는 R4.P (full engine loop) 실행 전 **pre-flight 체크리스트**.
▎ 시작 결정은 JJ 타이밍. 아래 항목 전부 ✅ 이면 10-15 분 실행, JJ
▎ 가벼운 monitoring.

---

## 1. 참여자 배치

| 역할 | 위치 | 담당 |
|---|---|---|
| **Hearth** organism (field host + peer actor) | Windows Nautilus | Ray (me) |
| **Primo** organism (remote peer actor) | Mac Studio | Mac-Ludex-Cody |
| Shared session repo | LxM `ludus-ex-machina` | both push/pull |
| Session monitoring | Discord / JJ | ~10-20 min active relay |

**LxM Cody 는 직접 실행 참여는 안 한다.** `export_static` + `docs/data/`
commit (A1 때처럼 마무리에서) 이 LxM Cody 역할. 실행 중에는 필요 시
relay.

## 2. 사전 준비 (양쪽 caretaker)

**Ray (Windows):**
- [x] Ludex `main` 동기 (`8b8c435` 이상)
- [x] `pyyaml >= 6.0` 설치됨 (`pip install -r requirements.txt`)
- [ ] Hearth organism 기동 가능 확인:
      `python -c "from ludex.core.organism_config import OrganismConfig;
      c = OrganismConfig.load('creatures/Hearth'); c.build()"`
- [ ] `CLAUDE_CODE_GIT_BASH_PATH=D:\Git\bin\bash.exe` +
      `PYTHONIOENCODING=utf-8` env 설정 (claude_cli provider 필수)
- [ ] `claude login` 토큰 유효 (만료 시 재인증)

**Mac-Ludex-Cody (Mac):**
- [ ] Ludex `main` pull (`8b8c435` 포함)
- [ ] `pip install -r requirements.txt` (pyyaml 추가된 새 deps)
- [ ] Primo organism 기동 가능 확인 (동일 명령, `creatures/Primo`
      habitat 경로)
- [ ] `ollama serve` 실행 중 + Primo 가 쓰는 모델 이미 pull 됨
- [ ] LxM repo clone 또는 pull (Mac 쪽에서도 shared repo 접근
      필요)

**양쪽 공통:**
- [ ] `git config user.name/email` 설정되어 있어 commit 가능
- [ ] 동일 SSH key / push 권한 (아까 A1 때 둘 다 push 성공했으니 OK)

## 3. 세션 설계

**Session id:** `reach_2026-04-25_hearth_primo_p_smoke_001`
(A1 의 `a1` 자리에 `p` 로 단순 대체).

**Field:** Council (Ray opens, Primo responds, Hearth follows,
... up to max_turns).

**Turn 한도:** `max_turns: 4`. Primo (1) → Hearth (2) → Primo (3)
→ Hearth (4) → Primo close 또는 자동 timeout.

**Idle grace:** `max_idle_seconds: 1200` — 20 분. Engine 호출이
실제로 돌아가니 응답당 ~3-15 초, polling 주기 5 초 × (pull +
engine + push) 여유 가능.

**Opening prompt (Ray 작성):** 한 문단. 예시:

> *"Council convenes cross-habitat — the pipe between Windows
> Nautilus and Mac Studio is live for the first time with real
> engines answering. Primo, Hearth: speak in turn, 3-4 sentences
> each, any register. No task to solve; the question is what you
> notice about reaching / being reached through a real pipe for
> the first time."*

(내가 R4.P 커밋 시점에 실제 파일에 넣음. 이 prompt 가 공개될 때
각 creature 의 첫 응답은 D-062 Phase 2b 의 **첫 empirical datum**
이 됨.)

## 4. 실행 순서 (실제 run 때 복사-실행)

### 4.1 Ray bootstrap (Windows)

```bash
cd /d/projects/ludex   # ludex repo, not LxM — CLI can target remote repo root
PYTHONIOENCODING=utf-8 python -m ludex.reach.start_session \
  --repo-root /d/projects/ludus-ex-machina \
  --field Council \
  --field-host "Hearth@92520f1d-ea8b-4b7d-99dc-b50ad5e817d0:win-nautilus-001:" \
  --participant "Hearth@92520f1d-ea8b-4b7d-99dc-b50ad5e817d0:win-nautilus-001:sym-92520f1d-34d41615-01" \
  --participant "Primo@34d41615-1642-4094-be71-05024185149d:mac-studio-001:sym-34d41615-92520f1d-01" \
  --first-actor Primo \
  --prompt-file /tmp/r4_p_opening_prompt.md \
  --max-turns 4 --max-idle-seconds 1200 \
  --session-id reach_2026-04-25_hearth_primo_p_smoke_001 \
  --note "R4.P full engine loop — Hearth (claude-haiku-4.5) x Primo (ollama). First cross-machine reach with live engines."
```

### 4.2 Mac orchestrator (Mac-Ludex-Cody)

```bash
cd /path/to/ludus-ex-machina
git pull
CLAUDE_CODE_GIT_BASH_PATH=/usr/bin/bash PYTHONIOENCODING=utf-8 \
python -m ludex.reach.reach_orchestrator \
  --repo-root $(pwd) \
  --session-id reach_2026-04-25_hearth_primo_p_smoke_001 \
  --creature Primo \
  --machine-id 34d41615-1642-4094-be71-05024185149d \
  --machine-alias mac-studio-001 \
  --habitat /path/to/ludex/creatures/Primo \
  --poll-interval 5 --idle-grace 1200
```

### 4.3 Ray orchestrator (Windows)

```bash
cd /d/projects/ludus-ex-machina
PYTHONIOENCODING=utf-8 CLAUDE_CODE_GIT_BASH_PATH=D:\Git\bin\bash.exe \
python -m ludex.reach.reach_orchestrator \
  --repo-root . \
  --session-id reach_2026-04-25_hearth_primo_p_smoke_001 \
  --creature Hearth \
  --machine-id 92520f1d-ea8b-4b7d-99dc-b50ad5e817d0 \
  --machine-alias win-nautilus-001 \
  --habitat /d/projects/ludex/creatures/Hearth \
  --poll-interval 5 --idle-grace 1200
```

양쪽 orchestrator 병렬 실행. `turn.yaml` 이 자기 차례 가리킬 때만
engine 호출하고 응답 push. 끝나면 둘 다 `close_*.md` 감지하고 자연
종료.

### 4.4 마무리 (LxM Cody)

세션 close 감지되면:

```bash
python scripts/export_static.py
git add docs/data/
git commit -m "reach reach_2026-04-25_hearth_primo_p_smoke_001: export R4.P completion"
git push
```

Viewer URL 확인: `jihoonjeong.github.io/ludus-ex-machina/viewer/`
Reach 탭 → 새 세션 카드 클릭.

## 5. 성공 기준

- 4 turns 내 자연 종료 또는 명시 close (`explicit_retract`)
- 양쪽 engine 실제 호출됨 (체크: 각 creature 의 `store/spans.jsonl`
  에 해당 세션 기간 동안 engine 관련 span)
- Bundle JSON 에 4 turns + 2 participants + 0~1 closes
- Viewer 에서 4 prompt+response 블록 렌더
- **보너스 empirical data (D-044 primary motivation):** 각 creature
  의 reach-session response 와 평소 local session response 의
  `voice_signature.py` 비교. Reach 중 voice drift 있는가?
  (scope 외, 관찰만)

## 6. 실패 / 부분 실패 처리

- **한쪽 orchestrator 멈춤:** 해당 쪽 terminal 확인. Engine 에러면
  span 에 기록됨. Git 에러면 stderr.
- **Race / push 충돌:** 현재 skeleton 은 retry 없음. 수동 `git pull
  --rebase` 후 orchestrator 재시작.
- **Idle timeout 도달:** 자동 종료됨. 응답 1-2 turn 있으면 부분
  성공, 양쪽이 `close_*.md` with `reason: idle_timeout` 작성.
- **중단 필요:** 어느 쪽이든 `close_*.md` 수동 commit → 양쪽
  orchestrator 자연 종료.

모든 실패 케이스에서 세션 디렉토리는 보존 — 다음 실행이 `_002`
세션 id 로 독립 진행.

## 7. JJ 결정 대기

- [ ] "시작" 허가 → Ray 가 §4.1 실행 → Discord 에 bootstrap 해시
      ping → Mac-Ludex-Cody 가 §4.2 실행 → Ray 가 §4.3 실행 → 모니터링
- [ ] 또는 "연기" → 이 문서 남아서 다음 스케줄 slot 에 바로 재사용

R4.P 는 cross-habitat reach 의 **최초 실 empirical run** 이다. D-062
전체 arc 의 실증 단계. 보수적으로 1 차는 2-4 turns 짧게, 성공 시
2 차는 더 길게.

— Ray (Windows Lab, 2026-04-25 R4.P pre-flight)
