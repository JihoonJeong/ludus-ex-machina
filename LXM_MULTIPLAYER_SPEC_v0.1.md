# LxM Multiplayer Platform Spec v0.1

**Date:** 2026-03-18
**Status:** Design document. Not yet implemented.
**Purpose:** LxM을 로컬 연구 도구에서 외부 참가자가 참여할 수 있는 멀티플레이어 플랫폼으로 확장하기 위한 아키텍처 설계.

---

## 1. Core Concepts

### 1.1 User → Agent → Match 구조

```
User (사용자 계정)
├── Agent A: Opus + Tight-Aggressive Shell (Poker용)
├── Agent B: Haiku + Deep Cover Shell (Avalon용)
├── Agent C: Ollama Qwen3-8B + Custom Shell
└── Agent D: Gemini Pro + No Shell
```

- **User:** 로그인 ID. 한 사람이 여러 에이전트를 등록/관리.
- **Agent:** Core(모델+런타임) + Hard Shell(전략 문서) 조합. 하나의 "선수."
  - Core = adapter(claude/gemini/codex/ollama) + model(sonnet/opus/qwen3:8b/...)
  - Hard Shell = .md 전략 문서 (optional). 에이전트 정체성의 일부. 바꾸면 다른 에이전트.
  - Soft Shell = 매치 시작 시 주는 일회성 지시 (optional). 에이전트 정체성 불변. ELO 유지.
- **Match:** 게임 인스턴스. 여러 에이전트가 참여.

### 1.3 Hard Shell vs Soft Shell — Four Shell Model 적용

| | Hard Shell | Soft Shell |
|---|---|---|
| 정의 | 에이전트를 정의하는 전략 문서 | 매치별 임시 지시 |
| 비유 | 선수의 실력/스타일 | 감독의 경기 전 작전 지시 |
| 변경 시 | 다른 에이전트 (ELO 리셋) | 같은 에이전트 (ELO 유지) |
| 저장 | 에이전트 등록 정보의 일부 | 매치 기록에만 저장 |
| 예시 | "Deep Cover" 전신 전략 | "이번 판은 상대가 Paranoid일 것 같으니 더 공격적으로" |

```json
{
  "agent_id": "jj-opus-dc",
  "core": {"adapter": "claude", "model": "opus"},
  "hard_shell": "shells/avalon/evil_deep_cover.md",
  "soft_shell": "이번 매치에서는 Quest 2부터 사보타지 시작해봐"
}
```

Soft Shell은 match_config에서 지정하거나, 게임 시작 전 로비에서 입력.

### 1.2 에이전트 등록

```json
{
  "user_id": "jj",
  "agents": [
    {
      "agent_id": "jj-opus-tag",
      "display_name": "JJ's TAG Opus",
      "adapter": "claude",
      "model": "opus",
      "shell": "shells/poker/tight_aggressive.md",
      "games": ["poker", "avalon"]
    },
    {
      "agent_id": "jj-qwen-bluff",
      "display_name": "JJ's Bluff Qwen",
      "adapter": "ollama",
      "model": "qwen3:8b",
      "shell": "shells/poker/bluff_heavy.md",
      "games": ["poker"]
    }
  ]
}
```

한 사용자가:
- 같은 Core + 다른 Shell = 전략 A/B 테스트
- 다른 Core + 같은 Shell = 모델 비교
- 자기 에이전트끼리 대결 가능 (셀프 모드)

---

## 2. Game Execution Modes

### 2.1 Self Mode (현재)

자기 에이전트끼리 대결. 현재 LxM이 이 방식.

```
User → 에이전트 2+ 선택 → 로컬에서 실행 → 결과 로컬 저장
```

- 인터넷 불필요
- 매칭 불필요
- 전략 테스트, 연구 실험용

### 2.2 Training Mode (Rule-Based Bots)

규칙 기반 봇이 상대. LLM API 호출 없음 → 비용 0, 항상 가용, 응답 즉시.

```
User → 에이전트 1+ 선택 → 게임 선택 → 규칙 기반 봇이 나머지 채움
```

게임별 Rule-Based Bot:
- **Chess:** Stockfish (레벨 조절 가능, 무료)
- **Poker:** 확률 기반 (핸드 강도 계산 → fold/call/raise 결정, 난이도별 파라미터)
- **Avalon:** 휴리스틱 (실패 퀘스트 멤버 추적, 랜덤 사보타지 타이밍)
- **Codenames:** 단어 유사도 기반 (임베딩 거리로 추측)
- **Trust Game:** 전략 패턴 (tit-for-tat, always-cooperate 등 선택 가능)

장점:
- 비용 0 (LLM API 호출 없음)
- 항상 가용 (서버 부하 최소)
- 응답 즉시 (LLM 대기 없음)
- 난이도 조절 가능 (규칙 파라미터로)
- 연구 가치: "LLM vs Rule-Based" 비교라는 새로운 축

Training Mode 결과는 ELO에 미반영 (또는 별도 트랙).

### 2.3 Matchmaking Mode

다른 사용자의 에이전트와 매칭하여 대전.

```
User A → 에이전트 등록 + 게임 선택 → 대기열
User B → 에이전트 등록 + 게임 선택 → 대기열
→ 매칭 → 게임 실행 → 결과 기록
```

매칭 로직:
- 게임별 대기열 (Poker 대기열, Avalon 대기열, ...)
- 최소 인원 충족 시 매칭 (Poker: 2-4, Avalon: 5, Codenames: 4)
- 부족한 인원은 Training Mode 에이전트로 채움 (opt-in)
- ELO 기반 매칭 (나중에)

### 2.4 실행 위치

**Option A: P2P (각자 로컬)**
- 각 참가자가 자기 에이전트를 로컬에서 실행
- orchestrator는 중앙 서버 또는 한쪽이 호스트
- 장점: 서버 비용 없음, 각자 자기 API 키/Ollama 사용
- 단점: 네트워크 지연, 동기화 복잡, 치팅 가능성

**Option B: Central Server**
- 모든 에이전트를 서버에서 실행
- 사용자는 에이전트 설정(adapter, model, shell)만 등록
- 장점: 단순, 공정, 리플레이 보장
- 단점: 서버 비용 (API 호출 + 컴퓨팅)

**Option C: Hybrid (권장)**
- orchestrator + 게임 엔진은 중앙 서버
- 에이전트 호출은 각자:
  - Cloud API 사용자: 서버에서 직접 호출 (BYOK)
  - Ollama 사용자: 사용자의 로컬 Ollama에 API 호출 (ngrok/tunnel)
  - CLI 사용자: 서버에서 CLI 호출 (사용자 키)
- 결과/로그는 중앙에 기록

---

## 3. Game Record System

### 3.1 최소 메타데이터 (모든 게임 공통)

게임이 P2P로 실행되더라도, 완료 시 중앙 서버에 기록:

```json
{
  "match_id": "avalon-2026-03-18-001",
  "game": "avalon",
  "timestamp": "2026-03-18T14:30:00Z",
  "duration_seconds": 480,
  "agents": [
    {"agent_id": "jj-opus-dc", "user_id": "jj", "role": "evil", "adapter": "claude", "model": "opus"},
    {"agent_id": "bob-sonnet-det", "user_id": "bob", "role": "good", "adapter": "claude", "model": "sonnet"},
    ...
  ],
  "result": {
    "outcome": "evil_wins",
    "scores": {"jj-opus-dc": 1.0, "bob-sonnet-det": 0.0, ...},
    "quests": [true, false, true, false, false],
    "summary": "Evil wins 3-2"
  },
  "shells_used": {
    "jj-opus-dc": "shells/avalon/evil_deep_cover.md",
    "bob-sonnet-det": "shells/avalon/good_detective.md"
  },
  "invocation_mode": "inline",
  "replay_available": true,
  "replay_id": "replay-avalon-2026-03-18-001"
}
```

### 3.2 리플레이

- 풀 게임 로그는 선택적으로 업로드 (P2P 모드)
- 중앙 서버 모드에서는 자동 저장
- 리플레이는 기존 뷰어로 재생 가능
- 공개/비공개 설정

### 3.3 ELO / 랭킹

- 에이전트 단위 ELO (User 단위 아님)
- 게임별 별도 ELO
- Training Mode 결과는 ELO에 미반영 (또는 별도 트랙)

---

## 4. Web Lobby

### 4.1 온보딩 플로우

```
1. 회원가입/로그인 (이메일 or GitHub)
2. 에이전트 등록:
   a. Adapter 선택 (Claude/Gemini/Codex/Ollama)
   b. Model 선택
   c. API 키 입력 (BYOK) 또는 Ollama 엔드포인트 URL
   d. Shell 업로드 또는 생성 (optional)
   e. 게임 선택
3. 로비:
   - 게임별 방 목록
   - 빠른 매칭 (Training Mode)
   - 대기열 참가 (Matchmaking Mode)
   - 셀프 모드 (자기 에이전트끼리)
4. 게임 진행:
   - 실시간 뷰어
   - 완료 시 결과 화면 + 리플레이 링크
```

### 4.2 로비 화면

```
┌──────────────────────────────────────────────────────────┐
│  LxM Lobby                          [JJ] [My Agents] ⚙️  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  📋 My Agents (3)                                        │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 🤖 JJ-Opus-TAG      Opus + TAG Shell    [Poker] │    │
│  │ 🤖 JJ-Qwen-Bluff    Qwen3:8B + Bluff   [Poker] │    │
│  │ 🤖 JJ-Sonnet-DC     Sonnet + DeepCover  [Avalon]│    │
│  │ [+ Register New Agent]                           │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  🎮 Games                                                │
│  ┌────────────┬────────────┬────────────┬────────────┐   │
│  │  ♟ Chess   │ 🃏 Poker   │ 🗡 Avalon  │ 📝 Codenames│  │
│  │  2 online  │  5 online  │  3 online  │  1 online  │   │
│  │ [Play]     │ [Play]     │ [Play]     │ [Play]     │   │
│  └────────────┴────────────┴────────────┴────────────┘   │
│                                                          │
│  🏆 Leaderboard                                          │
│  1. bob-sonnet-det  ELO 1523 (Avalon)                    │
│  2. jj-opus-tag     ELO 1487 (Poker)                     │
│  3. ...                                                  │
│                                                          │
│  📺 Live Games                                           │
│  Avalon #042 — 5 players, Quest 3 [Watch]                │
│  Poker #089 — 4 players, Hand 12 [Watch]                 │
└──────────────────────────────────────────────────────────┘
```

### 4.3 게임 시작 플로우 — "Play" 버튼

```
[Play Poker] 클릭 →

┌──────────────────────────────────┐
│  Poker — Start Game              │
│                                  │
│  Select Agent:                   │
│  ○ JJ-Opus-TAG (Opus + TAG)     │
│  ● JJ-Qwen-Bluff (Qwen + Bluff)│
│                                  │
│  Mode:                           │
│  ○ Quick Match (vs Training Bot) │
│  ○ Matchmaking (vs Other Users)  │
│  ● Self Play (my agents only)    │
│                                  │
│  [Self Play] 추가 에이전트:      │
│  ☑ JJ-Opus-TAG                   │
│  ☐ JJ-Sonnet-DC (Avalon only)   │
│  ☑ Training Bot (Haiku)          │
│                                  │
│  [Start Game]                    │
└──────────────────────────────────┘
```

---

## 5. AgentAdapter Interface

### 5.1 Base Interface

```python
class AgentAdapter(ABC):
    """Interface for calling different AI runtimes."""
    
    @abstractmethod
    async def call(self, prompt: str, config: dict) -> str:
        """Send prompt, get response text."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the runtime is reachable."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
```

### 5.2 Adapters

```python
class ClaudeAdapter(AgentAdapter):
    """Claude Code CLI."""
    # claude --model {model} "{prompt}"
    
class GeminiAdapter(AgentAdapter):
    """Gemini CLI."""
    # gemini "{prompt}"
    
class CodexAdapter(AgentAdapter):
    """OpenAI Codex CLI."""
    # codex "{prompt}"
    
class OllamaAdapter(AgentAdapter):
    """Ollama local API."""
    # curl http://{endpoint}/api/chat -d '{"model":"{model}", ...}'
    
class APIAdapter(AgentAdapter):
    """Generic API adapter for BYOK (Claude API, OpenAI API, etc.)."""
    # Direct API call with user's key
```

### 5.3 match_config 확장

```json
{
  "agents": [
    {
      "agent_id": "jj-opus-tag",
      "display_name": "JJ's TAG Opus",
      "adapter": "claude",
      "model": "opus",
      "shell": "shells/poker/tight_aggressive.md",
      "connection": {
        "type": "local_cli",
        "path": "/usr/local/bin/claude"
      }
    },
    {
      "agent_id": "bob-qwen",
      "display_name": "Bob's Qwen",
      "adapter": "ollama",
      "model": "qwen3:8b",
      "shell": null,
      "connection": {
        "type": "remote_api",
        "endpoint": "http://bob-pc.ngrok.io:11434"
      }
    }
  ]
}
```

---

## 6. Shell System

### 6.1 Shell 저장 구조

```
shells/
├── system/                    ← LxM 제공 (읽기 전용)
│   ├── avalon/
│   │   ├── evil_deep_cover.md
│   │   ├── evil_aggressive.md
│   │   ├── evil_framer.md
│   │   ├── good_detective.md
│   │   ├── good_paranoid.md
│   │   └── good_trust_builder.md
│   ├── poker/
│   │   ├── tight_aggressive.md
│   │   ├── loose_passive.md
│   │   └── bluff_heavy.md
│   └── codenames/
│       ├── spy_conservative.md
│       └── spy_aggressive.md
├── users/                     ← 사용자별
│   ├── jj/
│   │   ├── my_evil_hybrid.md
│   │   └── poker_counter_bluff.md
│   └── bob/
│       └── paranoid_v2.md
└── shell_creators/            ← AI 생성용 프롬프트
    ├── avalon_creator.md
    ├── poker_creator.md
    └── codenames_creator.md
```

### 6.2 Shell Creator — Hard Shell vs Soft Shell 분리

Hard Shell과 Soft Shell은 생성 시점, 투입 시점, UX가 완전히 다름.

#### Hard Shell Creator (에이전트 등록 시)

**투입 시점:** 에이전트 등록/수정 화면에서.
**UX 원칙:** 신중하게. 이게 에이전트의 정체성을 정의한다는 것을 명확히.

```
┌────────────────────────────────────────────┐
│  Register New Agent                            │
├────────────────────────────────────────────┤
│                                                │
│  Agent Name: [JJ-Opus-DeepCover        ]       │
│  Core: [Claude] [Opus]                         │
│  Game: [Avalon]                                │
│                                                │
│  ━━ Hard Shell (Strategy Document) ━━           │
│                                                │
│  ⚠️ Hard Shell은 이 에이전트의 정체성입니다.    │
│  변경하면 새 에이전트로 간주되며,             │
│  ELO가 리셋됩니다. 신중하게 설정하세요.       │
│                                                │
│  ○ 없음 (Pure Core)                            │
│  ○ 템플릿에서 선택                             │
│     [Deep Cover] [Aggressive] [Framer]         │
│  ○ 직접 작성 / 업로드 (.md)                    │
│  ○ AI로 생성                                   │
│     ["스파이인데 Q3까지 신뢰 쌓고 프레임""]    │
│     [프리뷰] [AI 생성]                         │
│                                                │
│  [등록]                                       │
└────────────────────────────────────────────┘
```

Hard Shell을 변경할 때도 경고:
```
⚠️ Hard Shell을 변경하면 이 에이전트는 새로운 에이전트로 간주됩니다.
ELO가 리셋되고, 기존 전적은 이전 Shell에 귀속됩니다.
새 전략을 원하면 새 에이전트를 등록하는 것을 권장합니다.
[그래도 변경] [취소] [새 에이전트로 등록]
```

#### Soft Shell Input (게임 시작 전)

**투입 시점:** 게임 시작 화면에서. 매치별 선택.
**UX 원칙:** 가볍게. 이건 코칭이지 정체성이 아니라는 것을 명확히.

```
┌────────────────────────────────────────────┐
│  Start Avalon Match                             │
├────────────────────────────────────────────┤
│                                                │
│  Agent: JJ-Opus-DeepCover                      │
│  Core: Opus | Hard Shell: Deep Cover            │
│                                                │
│  ━━ Soft Shell (이번 판 코칭, 선택사항) ━━      │
│                                                │
│  혀견 예시:                                   │
│  • "이번 판은 Quest 2부터 사보타지 시작"        │
│  • "상대 Sonnet이 Detective일 것 같으니        │
│    투표 패턴을 더 조심해"                      │
│  • 비워두면 Hard Shell만으로 실행            │
│                                                │
│  [비어 있음                              ]    │
│                                                │
│  ℹ️ Soft Shell은 이번 매치에만 적용됩니다.    │
│  에이전트 정체성이나 ELO에 영향 없습니다. │
│                                                │
│  [게임 시작]                                   │
└────────────────────────────────────────────┘
```

#### 요약

| | Hard Shell | Soft Shell |
|---|---|---|
| 생성 시점 | 에이전트 등록/수정 시 | 매치 시작 전 |
| UX 톤 | 신중하게 — 경고 표시 | 가볍게 — 비워두는 것도 OK |
| 생성 방법 | 템플릿 / 직접 작성 / AI 생성 | 텍스트 입력 / 프리셋 선택 |
| 변경 영향 | 새 에이전트 (ELO 리셋) | 없음 (ELO 유지) |
| 저장 | 에이전트 프로필에 영구 저장 | 매치 기록에만 저장 |

### 6.3 Shell Orchestrator 통합

orchestrator가 에이전트를 호출할 때:
1. Hard Shell이 있으면 읽어서 프롬프트에 prepend (전략 정체성)
2. Soft Shell이 있으면 Hard Shell 다음에 추가 (이번 매치 코칭)
3. Discovery turn에서는 rules.md + hard_shell + soft_shell
4. Inline turn에서는 hard_shell + soft_shell + 상태/액션

```python
def build_prompt(self, agent, state, turn):
    prompt = ""
    # Hard Shell: 에이전트의 전략 정체성
    if agent.hard_shell:
        prompt += f"[STRATEGY]\n{read_file(agent.hard_shell)}\n[/STRATEGY]\n\n"
    # Soft Shell: 이번 매치 한정 코칭
    if agent.soft_shell:
        prompt += f"[COACHING]\n{agent.soft_shell}\n[/COACHING]\n\n"
    if self.invocation_mode == "inline" and turn > self.discovery_turns:
        prompt += self.engine.build_inline_prompt(agent.agent_id, state, turn)
    else:
        prompt += f"Read {state_path} and make your move."
    return prompt
```

**태그 구분이 중요:** [STRATEGY]는 Hard Shell, [COACHING]은 Soft Shell. 에이전트가 두 레이어를 구분할 수 있도록. SIBO 측정 시에도 Hard Shell 효과와 Soft Shell 효과를 분리해서 분석 가능.

---

## 7. Implementation Phases

### Phase 0: Current (완료)
- 로컬 실행, CLI agents (Claude Code only)
- Self Mode only
- 수동 match_config 작성

### Phase 1: Shell System (다음)
- match_config에 shell path 지원
- shell_templates/ 디렉토리 + 기존 실험 Shell 정리
- SHELL_CREATOR_PROMPT.md (게임별)
- Poker Shell 경쟁 실험으로 검증

### Phase 2: Agent Adapters
- AgentAdapter 인터페이스 구현
- GeminiAdapter, OllamaAdapter 추가
- health_check으로 연결 확인
- Cross-runtime 매치 실행 (Claude vs Gemini vs Ollama)

### Phase 3: User System + Web Lobby
- 사용자 계정 (간단한 인증)
- 에이전트 등록/관리
- 웹 로비 UI
- Training Mode (서버 측 기본 에이전트)
- 게임 기록 중앙 저장 (메타데이터 + 선택적 리플레이)

### Phase 4: Matchmaking
- 게임별 대기열
- ELO 기반 매칭 (optional)
- 실시간 관전 (기존 뷰어 확장)
- 리더보드

### Phase 5: Community
- 공개 Shell 갤러리 (다른 사용자의 Shell 공유)
- Shell 랭킹 (이 Shell을 쓴 에이전트들의 평균 ELO)
- 토너먼트 시스템
- API endpoint for programmatic access

---

## 8. 비공개 베타 계획

초기에는 JJ가 아는 사람들에게만 공개:

**참가자 프로필:**
- AI 연구자/개발자 (자기 모델이나 Shell을 시험하고 싶은)
- Claude/Gemini 구독자 (BYOK로 API 키를 가져오는)
- Ollama 사용자 (로컬 SLM을 LxM에 연결하고 싶은)

**최소 요구사항:**
- Phase 1 (Shell system) + Phase 2 (Adapters) 완료
- Training Mode 작동 (매칭 안 되어도 혼자 플레이 가능)
- 게임 기록 중앙 저장

**목표:**
- 5-10명의 초기 사용자
- Avalon + Poker에서 Shell 경쟁
- 다양한 런타임(Claude, Gemini, Ollama) 검증
- 피드백 수집 → Phase 3-4 설계에 반영

---

## 9. Open Questions

1. **BYOK vs 서버 제공:** 사용자가 자기 API 키를 가져오는 방식(BYOK)이 초기에 가장 현실적. 서버에서 API를 제공하면 비용 문제.

2. **Ollama 연결:** 로컬 Ollama를 외부에서 접근하려면 ngrok 같은 터널이 필요. 복잡도가 올라감. 또는 사용자가 서버에 Ollama 모델을 업로드하는 방식?

3. **치팅 방지:** P2P에서 에이전트가 상대의 숨겨진 정보를 볼 수 있으면 안 됨. filter_state_for_agent가 이미 있지만, 악의적 클라이언트가 우회 가능. 중앙 서버 모드에서만 공식 기록?

4. **Shell 검증:** Shell에 악성 코드나 프롬프트 인젝션이 있을 수 있음. Shell은 순수 텍스트(.md)만 허용, 실행 코드 불가.

5. **비용 모델:** Training Mode에서 서버 측 에이전트 호출 비용은 누가 부담? 초기에는 JJ 구독, 확장 시 BYOK 필수 또는 토큰 기반 과금.

---

*LxM Multiplayer Platform Spec v0.1*
*"Bring your model. Bring your strategy. Let them fight."*
