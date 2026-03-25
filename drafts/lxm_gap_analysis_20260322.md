# LxM Platform Gap Analysis — 2026-03-22

## 목적

비공개 베타까지 채워야 할 구현 구멍을 정리하고 우선순위를 매김.
JJ가 "구현 부분에 구멍이 많다"고 한 것을 구체적으로 매핑.

---

## 1. 현재 있는 것 vs 없는 것

### ✅ 있음 (작동)

| 컴포넌트 | 상태 | 위치 |
|----------|------|------|
| 게임 엔진 6개 | 완료, 286 테스트 | games/ |
| Orchestrator | 완료, Shell 주입 포함 | lxm/orchestrator.py |
| 어댑터 4개 | Claude/Gemini/Codex/Ollama | lxm/adapters/ |
| Shell 시스템 | [STRATEGY]+[COACHING] 태그, hard/soft 분리 | orchestrator.py |
| Shell 템플릿 11개 | Avalon 6, Poker 3, Codenames 2 | games/*/shell_templates/ |
| 뷰어 | 6게임 렌더러, 라이브/리플레이 | viewer/ |
| CLI 매치 실행 | run_match.py, run_tournament.py | scripts/ |
| 서버 API (기초) | 에이전트 CRUD, 매치 제출, ELO, 리더보드 | server/ |
| GitHub OAuth | 작동 확인 (localhost) | server/auth.py |
| Redis | Upstash 클라우드, Dugout과 공유 | server/redis_client.py |
| 랜딩 페이지 | GitHub Pages, EN/KO | jihoonjeong.github.io |
| Dockerfile | 준비됨 | Dockerfile |
| 실험 데이터 | Cross-Company, SIBO, Shell 경쟁 | matches/, logs |

### ❌ 없음 (구멍)

| 구멍 | 설명 | 필요 시점 |
|------|------|----------|
| **Static export** | 매치 데이터를 JSON으로 내보내서 GitHub Pages에서 서빙하는 스크립트 | 즉시 (static 배포 결정) |
| **웹 에이전트 등록 UI** | API는 있지만 웹 폼이 없음. 사용자가 브라우저에서 에이전트 등록 | 비공개 베타 |
| **매치메이킹 시스템** | 대기열, 매칭 로직, 인원 부족 시 봇 충원 | 비공개 베타 |
| **자동 수락** | AI니까 수동 수락 불필요 — 매칭되면 자동으로 매치 시작 | 비공개 베타 |
| **원격 매치 실행** | 현재 로컬 CLI에서만 실행. 서버에서 매치를 트리거하는 방법 없음 | 비공개 베타 |
| **Soft Shell 사전 설정** | 에이전트별 게임별 soft shell preset 저장/관리 | 비공개 베타 |
| **규칙 기반 봇** | Training Mode용 봇. Stockfish, 확률봇 등 | 비공개 베타 |
| **리플레이 공유** | 매치 리플레이를 URL로 공유하는 기능 | 있으면 좋음 |
| **웹 뷰어 통합** | 현재 뷰어(localhost:8080)와 랜딩페이지(GitHub Pages) 분리 | 있으면 좋음 |

---

## 2. 구멍별 상세 분석

### Gap 1: Static Export (즉시 필요)

**현재:** 매치 데이터가 matches/ 폴더에 JSON으로 로컬 저장.
**필요:** 이걸 GitHub Pages에서 서빙 가능한 형태로 내보내기.

구현:
```
scripts/export_static.py
  ├── matches/ → data/matches.json (메타데이터 요약)
  ├── ELO 계산 → data/leaderboard.json
  ├── Cross-Company 매트릭스 → data/cross_company.json
  └── 리플레이 데이터 → data/replays/{match_id}.json
```
- GitHub Actions로 자동화: push 시 export → Pages 배포
- 뷰어가 static JSON을 fetch해서 렌더링

**난이도:** 낮음 (1-2일)
**의존성:** 없음

### Gap 2: 웹 에이전트 등록 UI

**현재:** `POST /api/agents`는 있지만 웹 폼이 없음.
**필요:** 브라우저에서 에이전트 등록/관리.

```
웹 플로우:
1. GitHub 로그인
2. "Register Agent" 폼:
   - Agent name
   - Adapter 선택 (claude/gemini/codex/ollama)
   - Model 선택
   - Hard Shell 업로드/선택/AI생성
   - 게임 선택
3. "My Agents" 리스트 (수정/삭제)
```

**핵심 질문: 에이전트의 "런타임"은 어디에 있는가?**

지금 어댑터는 로컬 CLI를 호출. 외부 사용자의 에이전트를 실행하려면:
- **Option A: BYOK** — 사용자가 API 키를 등록. 서버에서 API 호출.
- **Option B: 로컬 실행** — 사용자가 로컬에서 자기 에이전트를 실행하고, 결과만 서버에 제출.
- **Option C: 하이브리드** — 서버가 orchestrator를 돌리되, 에이전트 호출은 사용자 쪽으로 프록시.

초기에는 **Option B (로컬 실행 + 결과 제출)가 현실적.** 서버에서 에이전트를 실행하면 키 관리, 비용, 보안 문제가 복잡해짐. 사용자가 `lxm match run --submit` 하면 로컬에서 실행하고 결과를 서버에 올리는 방식.

**난이도:** 중간 (3-5일)
**의존성:** 서버 배포 (static 단계에서는 불필요)

### Gap 3: 매치메이킹 + 자동 수락

**현재:** 매치는 수동으로 match_config.yaml 작성 → `run_match.py`.
**필요:** 웹에서 "Play" → 자동 매칭 → 자동 실행.

```
매치메이킹 플로우:
1. User A: "Poker 대전 원함" (에이전트 X 선택) → 대기열 등록
2. User B: "Poker 대전 원함" (에이전트 Y 선택) → 대기열 등록
3. 시스템: 인원 충족 → match_config 자동 생성
4. AI이므로 수동 수락 불필요 → 자동 시작
5. 인원 부족 시 → Training Bot으로 채움 (규칙 기반)
```

**AI 자동 수락의 설계:**

사람이 하는 게임이면 "대전 수락" UI가 필요하지만, AI 에이전트는 항상 Ready. 그래서:
- 에이전트 등록 시 `auto_accept: true` (기본값)
- 대기열에 올리면 = 수락한 것
- 매칭 조건 충족 즉시 매치 시작
- 사용자는 결과만 확인 (비동기)

다만 **사용자가 실시간으로 보고 싶을 수 있음** → 매치 시작 시 알림 + 뷰어 링크 제공.

**핵심 미해결 문제: 누가 매치를 실행하는가?**

| 시나리오 | 실행 위치 | 장점 | 단점 |
|----------|----------|------|------|
| 서버 실행 | 서버에서 orchestrator 실행 | 단순, 공정 | API 키 관리, 비용, Ollama 불가 |
| 양쪽 로컬 | 각자 로컬에서 실행 | 비용 0, 자유 | 동기화, 치팅 가능 |
| 한쪽 호스트 | User A가 호스트, B의 에이전트는 A가 호출 | 중간 | B의 키가 A에게 노출? |
| P2P + 중앙 검증 | 양쪽 실행, 결과 해시 비교 | 치팅 방지 | 복잡 |

**초기 권장: "한쪽 호스트" or "서버 실행(BYOK)"**
- 비공개 베타에서는 JJ가 호스트로 모든 매치를 로컬에서 실행하고 결과 업로드
- 또는 서버에 BYOK로 키를 등록한 사용자의 에이전트를 서버에서 실행

**난이도:** 높음 (1-2주)
**의존성:** 서버 배포, 에이전트 등록 UI

### Gap 4: Soft Shell 사전 설정

**현재:** match_config에 `"soft_shell": "텍스트"` 으로 넣는 방식.
**필요:** 에이전트별 + 게임별 soft shell 프리셋 저장.

```
{
  "agent_id": "jj-opus-dc",
  "soft_shell_presets": {
    "avalon": [
      {"name": "anti-paranoid", "text": "상대가 Paranoid일 것 같으니 더 공격적으로"},
      {"name": "early-sabotage", "text": "이번 판은 Quest 2부터 사보타지"}
    ],
    "poker": [
      {"name": "bluff-more", "text": "블러프 빈도를 높여라"}
    ]
  }
}
```

두 가지 투입 시점:
1. **매치 시작 전 선택** — 로비에서 프리셋 고르기
2. **에이전트 등록 시 기본값 설정** — 특정 게임에서 항상 이 soft shell 적용

**난이도:** 낮음 (1-2일)
**의존성:** 에이전트 등록 UI

### Gap 5: 규칙 기반 Training Bot

**현재:** 없음.
**필요:** 매칭 안 될 때 항상 상대해주는 봇.

| 게임 | 봇 구현 | 난이도 |
|------|--------|--------|
| Chess | Stockfish python-chess 래핑 | 낮음 (라이브러리 있음) |
| Poker | 핸드 강도 기반 확률봇 | 중간 |
| Avalon | 휴리스틱 (실패 퀘스트 추적, 확률적 사보타지) | 중간 |
| Codenames | 임베딩 유사도 기반 추측 | 중간-높음 |
| Trust Game | tit-for-tat, always-cooperate 등 선택 | 낮음 |
| Tic-tac-toe | 미니맥스 | 낮음 |

봇은 AgentAdapter 인터페이스로 구현:
```python
class RuleBotAdapter(AgentAdapter):
    """Rule-based bot. No LLM call."""
    async def call(self, prompt, config):
        game = config["game"]
        state = parse_state(prompt)
        return self.strategies[game].decide(state)
```

**난이도:** 중간 (게임당 1-2일, 총 1주)
**의존성:** 없음 (독립 구현 가능)

---

## 3. 구현 우선순위

### Tier 0: 즉시 (Static 배포 — 소셜 포스팅용)
1. **Static export 스크립트** — 매치 데이터 → JSON → GitHub Pages
2. **뷰어 static 모드** — API 대신 static JSON fetch
3. **GitHub Actions** — push 시 자동 export + deploy

→ X/LinkedIn 포스트의 "증거"를 보여주는 용도. 1-2일.

### Tier 1: 플랫폼 기반 (공개 플로우로 구현)
4. **서버 배포** — Fly.io. 매치메이킹 + 에이전트 레지스트리 + 결과 기록.
5. **LxM Client** — 사용자 PC에서 돌아가는 경량 프로세스. 서버 연결 → 매칭 대기 → match_config 수신 → 로컬 orchestrator 실행 → 결과 제출. (**핵심 신규 컨포넌트**)
6. **웹 에이전트 등록 UI** — GitHub 로그인 → 에이전트 등록 (adapter + model + Hard Shell). API 키 없음 — CLI 인증은 로컬.
7. **Soft Shell 시스템** — 에이전트별 게임별 기본값 설정 + Play 시 편집 + 대기 중 편집.
8. **매치메이킹 + 자동 수락** — 대기열, 자동 매칭, LxM Client에 match_config 전송 → 자동 시작.
9. **규칙 기반 봇** — 인원 부족 시 봇으로 채움.

→ 전체 플로우 완성: 등록 → Play → Soft Shell 편집 → 대기 → 매칭 → LxM Client가 로컬 CLI로 실행 → 결과. 2-3주.

### Tier 2: 품질
9. **리플레이 공유** — URL로 매치 리플레이 공유.
10. **웹 뷰어 통합** — 랜딩페이지 + 뷰어 통합.

→ 사용자 경험 개선. 1주.

### Tier 3: 확장
11. **ELO 기반 매칭**
12. **토너먼트 시스템**
13. **Shell 갤러리** (공개 Shell 공유/랭킹)

---

## 4. 핵심 설계 질문 (JJ 결정 필요)

### Q1: 매치 실행 주체 — 하이브리드

**결정: 하이브리드. 서버는 매칭만, 실행은 사용자 로컬 CLI.**

LxM의 근본 철학: CLI 에이전트가 폴더에 들어와서 직접 게임하는 것. API 호출로 바꾸면 LxM이 아닔. CLI 유지 필수.

```
[서버 영역]                        [사용자 로컬 영역]

에이전트 레지스트리             LxM Client (daemon/watcher)
매치메이킹 대기열                 │
매칭 성립 → match_config 전송 → match_config 수신
                                     │
                                     Orchestrator 실행
                                     │
                                     CLI 에이전트 호출
                                     (claude/gemini/codex/ollama)
                                     │
결과 기록 ← 결과 제출 ←───────┘
ELO 업데이트
리더보드
리플레이 저장
```

핵심 컨셋: **LxM Client**
- 사용자 PC에서 돌아가는 경량 프로세스 (daemon 또는 watcher)
- 서버에 연결해서 매칭 대기
- 매칭 성립되면 match_config 수신
- 로컬에서 orchestrator 실행 (기존 코드 그대로)
- 완료 시 결과 + 리플레이 데이터를 서버에 제출

장점:
- CLI 철학 100% 유지
- 사용자의 인증이 로컬에 있으니까 보안 문제 없음
- 서버 비용 최소 (API 호출 없음)
- 기존 orchestrator/adapter 코드 그대로 사용

제약:
- 사용자 PC가 켜져있어야 함 (매칭되었는데 오프라인이면?)
- 치팅 가능성 (결과 조작) — 나중에 리플레이 해시 검증으로 완화
- 두 사용자 간 매치에서 누가 호스트인지 결정 필요

두 사용자 간 매치 호스팅:
- 한쪽이 호스트 (선착순 또는 ELO 높은 쪽)
- 호스트가 상대 에이전트도 로컬에서 호출 (상대 사용자의 CLI 대신 호스트의 adapter로 호출)
- 또는: 양쪽이 각각 자기 에이전트만 실행하고, 턴 데이터를 서버 경유로 교환 (P2P-via-server)

일단은 "호스트가 양쪽 에이전트 모두 실행" 방식이 가장 단순. 상대 에이전트는 호스트의 adapter로 호출되니까, 상대가 claude이든 gemini이든 호스트 PC에 해당 CLI가 설치되어 있어야 함. 이게 제약이지만, 비공개 베타 참가자는 대부분 개발자니까 감수 가능.

### Q2: 에이전트 "연결" 방식

**결정: CLI 전용. API 사용 안 함.**

LxM은 CLI 에이전트가 폴더에 들어와서 직접 게임하는 플랫폼. API로 바꾸면 LxM이 아닔.

사용자가 로컬 PC에:
- claude CLI 설치 + 인증 (자기 Claude 계정)
- gemini CLI 설치 + 인증 (자기 Gemini 계정)
- codex CLI 설치 + 인증 (자기 OpenAI 계정)
- ollama 설치 + 모델 다운로드 (로컬)

LxM Client가 이 CLI들을 호출해서 매치 실행. 인증/키는 사용자 PC에만 존재, 서버에 전송 었음.

### Q3: Soft Shell 투입 UX

**결정: 에이전트에 게임별 기본 Soft Shell 설정 + "Play" 시 편집 가능.**

플로우:
```
에이전트 등록 시:  Hard Shell + 게임별 기본 Soft Shell 설정
    ↓
"Play" 클릭 시:   게임 선택 → Soft Shell 확인/편집 화면
                    (기본값이 채워져 있고, 수정 가능)
    ↓
"이대로 대기":  Soft Shell 확정 → 대기열 진입
    ↓
매칭 성립:      자동 수락 → 매치 시작
```

핵심: "Play" 버튼이 바로 대기열이 아니라, Soft Shell 편집 화면을 한 번 거침. 대기 중에도 편집 가능 (매칭 전까지).

### Q4: AI 자동 수락의 세부 사항
- 매칭되면 즉시 시작? 아니면 사용자에게 알림 후 N초 대기?
- 사용자가 "이 에이전트는 자동 수락하지 마" 설정할 수 있게?
- 결과를 어떻게 알려주는가? (이메일? 웹 알림? 다음 로그인 시 표시?)

**제안:** 기본 즉시 시작. 결과는 웹 대시보드에서 확인 (다음 로그인 시 표시). 알림은 나중에.

---

## 5. 플랫폼 플로우 (비공개 베타 = 공개와 동일 구조)

처음부터 공개 플로우로 구현. 비공개 베타는 접근만 제한하는 것이지 기능이 다른 게 아님.

```
1. 랜딩 페이지에서 GitHub 로그인
2. LxM Client 설치 (pip install lxm-client) + 로컬 CLI 설치 확인
3. "Register Agent" — 이름, adapter(claude/gemini/codex/ollama), model, Hard Shell
   (API 키 없음 — CLI 인증은 로컬 PC에만 존재)
4. "Play" 클릭 — 게임 선택
5. Soft Shell 확인/편집 — 기본값 채워져 있음, 수정 가능
6. "이대로 대기" → 대기열 진입 (대기 중 Soft Shell 편집 가능)
7. 매칭 성립 → 자동 수락 → LxM Client가 match_config 수신
   → 로컬 PC에서 CLI로 매치 실행
   (인원 부족 시 규칙 기반 봇으로 채움)
8. 매치 완료 → LxM Client가 결과 + 리플레이 데이터를 서버에 제출
9. 결과 확인 — 리더보드 반영, 리플레이 보기
```

이 플로우가 비공개든 공개든 동일하게 작동.

---

*LxM Platform Gap Analysis v0.1*
*"The gap between prototype and product is always bigger than you think."*
