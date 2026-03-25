# LxM Client 설계 논의 — Luca용

## 배경

Tier 0 (Static Export) 완료. 랜딩 페이지에서 247개 매치 리플레이 볼 수 있음.

다음 단계로 LxM Client 스켈레톤을 잡으려고 하는데, 서버 전에 클라이언트부터 시작하는 이유와 설계 방향에 대해 논의 필요.

---

## 왜 서버 전에 Client부터?

Gap Analysis에서 Tier 1 순서가 서버(4) → Client(5)지만, 실제로는 **Client가 먼저 잡혀야 서버 인터페이스가 결정**됨.

이유:
1. **Client가 "무엇을 받고 무엇을 보내는지"가 서버 API 스펙을 결정함.** 서버부터 만들면 Client에 안 맞는 API를 만들 수 있음.
2. **Client는 서버 없이도 동작해야 함.** 로컬 매치 실행이 기본이고, 서버 연결은 부가 기능. 지금 `run_match.py`가 하는 일을 Client가 더 깔끔하게 대체.
3. **기존 코드를 정리하는 기회.** `run_match.py`의 300줄 monolithic 스크립트를 분리: Config(데이터) / Client(라이프사이클) / Orchestrator(게임 루프) / Adapter(에이전트).

---

## 핵심 설계 결정

### 1. 에이전트는 블랙박스

LxM Client는 에이전트에게 게임 상태를 주고, 답(수)을 받는다. 끝.

에이전트 내부에서 뭘 하든 제한하지 않음:
- **서브에이전트 호출** — 마스터 에이전트가 분석용 에이전트를 따로 띄워서 전략 수립
- **외부 API 호출** — 데이터 검색, 임베딩 비교 등
- **멀티 프로세스** — 병렬 분석 후 결과 종합
- **파일 시스템 활용** — match_dir에서 게임 로그 읽고, 히스토리 분석

→ Claude Code가 서브에이전트로 작업하는 것처럼, 게임 에이전트도 같은 패턴 가능.
→ 타임아웃이나 리소스 관리는 **에이전트 작성자(사용자)의 책임**. 잘 못하면 시간 초과로 지는 것.
→ Client는 이런 구조를 **제한하지 않으면서, 쉽게 할 수 있는 틀**을 제공.

### 2. MatchConfig가 계약서

```
CLI args  ──→ MatchConfig  ──→ Client ──→ Orchestrator
서버 JSON ──→ MatchConfig  ──→ (같은 경로)
YAML 파일 ──→ MatchConfig  ──→ (같은 경로)
```

어디서 오든 MatchConfig 하나로 통일. 현재는 untyped dict인데 typed dataclass로 전환.

### 3. 4계층 분리

```
Config (데이터)     — MatchConfig, AgentConfig 데이터클래스
Client (라이프사이클) — 매치 준비, 실행, 결과 제출, 서버 연결
Orchestrator (게임)  — 턴 루프, 프롬프트 빌딩, 수 검증, 상태 전이
Adapter (에이전트)   — CLI 호출, 블랙박스 invoke()
```

Orchestrator와 Adapter는 이미 있음. Config과 Client가 새로 필요.

### 4. Registry (플러그인)

현재 `run_match.py`에 하드코딩된 어댑터/게임 맵핑:
```python
ADAPTERS = {"claude": ClaudeCodeAdapter, "gemini": GeminiCLIAdapter, ...}
GAMES = {"chess": Chess, "poker": TexasHoldem, ...}
```

→ `lxm/adapters/registry.py`로 이동. `register_adapter()`, `register_game()` 함수.
→ 사용자가 커스텀 어댑터 등록 가능 (미래: 자체 에이전트 런타임).

---

## 구현 계획

### Phase A: Config + Registry (서버 없이, 기존 기능 유지)
- `lxm/config.py` — MatchConfig/AgentConfig dataclass, `from_cli_args()`, `to_dict()`
- `lxm/adapters/registry.py` — 어댑터/게임 레지스트리
- 기존 `run_match.py` 동작 100% 호환

### Phase B: LxM Client (서버 없이, 개선된 매치 실행)
- `lxm/client.py` — LxMClient: prepare() → run() → submit()
- `scripts/run_match.py` 간소화 (Client 호출만)
- 새 entry point: `python -m lxm` 또는 `lxm run`

### Phase C: 서버 연결 (서버 배포 후)
- `client.connect(server_url, token)` — WebSocket/polling
- `client.wait_for_match()` → MatchConfig 수신 → run()
- 결과 + 리플레이 자동 제출

---

## 피드백 (답변 반영)

1. **Client-first 순서** → ✅ 맞음. Client가 서버 API를 결정. 서버부터 만들면 Client에 안 맞는 API 위험.
2. **에이전트 블랙박스 원칙** → ✅ 강하게 동의. Four Shell Model과 직결. 에이전트 내부 제한 = Shell engineering 자유도 제한. 서브에이전트 호출은 고급 Shell engineering이니까 허용해야. 타임아웃만 관리.
3. **Registry** → ✅ 오버엔지니어링 아님. 외부 참가자가 자기 런타임을 가져오는 게 LxM의 미래. register_adapter() 지금 해두면 나중에 하드코딩 리팩터 안 해도 됨.
4. **Phase A부터 시작** → ✅ 맞음. 서버 독립, 기존 동작 유지, 리스크 0.
5. **`pip install lxm`** → Phase B 완성 후. `python -m lxm run` 또는 `lxm run`이 동작할 때 패키지화.

추가 코멘트:
- Phase A의 MatchConfig dataclass에 hard_shell/soft_shell 필드를 반드시 포함. 현재 orchestrator.py에 이미 있지만 untyped dict. typed로 전환하면서 [STRATEGY]/[COACHING] 태그를 config 수준에서 공식화.
- Phase B의 submit()이 Phase C의 서버 연결 시 핵심 인터페이스. submit()의 payload 구조가 서버 API의 /api/matches POST 스펙을 결정함. 이게 "Client가 서버를 결정한다"의 구체적 예시.
- 블랙박스 원칙에 하나 추가: match_dir 안에 에이전트가 임시 파일을 만들 수 있게 허용하는 게 좋겠어. 예: 포커에서 에이전트가 자체 전략 노트를 .md로 저장해두고 다음 턴에 참고하는 것 — 이게 folder-native 철학의 진짜 발휘.

---

## 참고: 현재 완료 상태

- Tier 0 완료: static export, viewer on Pages, 하이라이트 매치 링크
- 크로스컴퍼니 실험 전부 완료 (Chess 20-0, Poker 8-4, Avalon mixed Good 65%)
- GPT-5.4 재테스트만 3/25 대기
- 서버 배포 옵션: `drafts/luca_deployment_20260322.md` 참조
