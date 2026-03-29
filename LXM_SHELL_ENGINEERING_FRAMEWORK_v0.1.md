# Shell Engineering Framework — LxM

**Date:** 2026-03-24
**Status:** 설계 문서. LxM Client의 핵심 기능으로 구현 예정.
**Purpose:** Shell(Hard/Soft)을 체계적으로 설계, 테스트, 최적화하는 방법론과 도구를 정의.

---

## 1. 왜 Shell Engineering인가

### 현재 AI 업계의 문제

"프롬프트 엔지니어링"이라고 하면:
- 템플릿 모음집 ("Chain of Thought를 쓰세요", "Few-shot 예시를 넣으세요")
- 한 모델에서 작동하면 다른 모델에서도 될 거라는 가정
- 측정 없는 직감 기반 반복

**실제로는:**
- 같은 프롬프트가 Claude에서는 먹히고 Gemini에서는 안 먹힘 (LxM Codenames: Claude 공격적 클루 → 패배, Gemini 보수적 → 승리)
- 같은 모델에서도 게임(목표)에 따라 같은 특성이 강점이 되기도 약점이 되기도 함 (Claude 공격성: Poker에서 강점, Codenames에서 약점)
- "더 좋은 프롬프트"를 찾는 체계적 방법이 없음

### LxM이 해결할 수 있는 것

LxM에서는 Shell의 효과가 **정량적으로 측정 가능**:
- 승률 변화 (Avalon: 0% ~ 100%)
- 행동 분포 변화 (Poker: fold 52% → 91%)
- 과정 지표 변화 (Codenames: 정답률, 클루 숫자)
- 비용 변화 (응답 시간, 토큰 사용량)

**게임이 있으니까 최적화 루프를 돌릴 수 있어요.** 이게 범용 프롬프트 엔지니어링에서 불가능한 것.

### Shell Engineering = Prompt Engineering, Gamified and Measurable

| | 기존 프롬프트 엔지니어링 | Shell Engineering |
|---|---|---|
| 측정 | 주관적 ("좋아 보인다") | 정량적 (승률, 행동 지표, 비용) |
| 반복 | 직감 기반 | 체계적 A/B + 자동화 |
| Core 의존성 | 무시 | 명시적 (Core별 최적 Shell 다름) |
| 게임/목표 의존성 | 무시 | 명시적 (게임별 최적 Shell 다름) |
| 비용 관리 | 없음 | 토큰/시간을 비용 함수에 포함 |
| 자동화 | 없음 | Shell Trainer Agent |

---

## 2. Shell의 구성 요소

### 2.1 Shell Format 논쟁: Markdown vs JSON

| | Markdown | JSON/YAML |
|---|---|---|
| 장점 | 자연스러운 산문, LLM이 잘 이해, 인간 가독성 | 구조 명확, 파싱 쉬움, diff 추출 용이 |
| 단점 | 구조 모호, 섹션 구분이 관습적, 자동 파싱 어려움 | 딱딱함, LLM이 산문보다 덜 잘 따름 가능성 |
| 적합한 상황 | 전략적 지시, 상황 판단 가이드 | 파라미터 튜닝, 조건부 규칙 |

**제안: Hybrid — Structured Markdown.**

```markdown
# Poker Strategy: Tight-Aggressive v2.3

## Parameters
- pre_flop_threshold: top 20%
- bluff_frequency: 1 per 5 hands
- position_bluff_only: true

## Strategy
Pre-flop: 상위 20% 핸드만 플레이. 나머지는 폴드.
Post-flop: 히트하면 공격적 베팅. 미스하면 폴드.

## Situational Rules
- 스택이 20BB 이하일 때: push-or-fold 모드 전환
- 상대가 3번 연속 폴드했을 때: 블러프 빈도 2배 증가
```

**Parameters 섹션**은 JSON처럼 파싱 가능하게 (key: value). 자동 최적화 시 이 값을 조정.
**Strategy 섹션**은 자연어로 LLM이 잘 이해하게.
**Situational Rules**은 조건부 규칙으로 구체적 상황 대응.

이 구조면:
- 인간이 읽고 쓰기 쉬움 (Markdown)
- 자동화 도구가 Parameters를 파싱해서 조정 가능 (Structured)
- diff 추출이 가능 (파라미터 변경량 측정)

### 2.2 Shell의 계층

```
Hard Shell (정체성)
├── Parameters      ← 자동 튜닝 가능한 수치들
├── Strategy        ← 핵심 전략 산문
├── Situational Rules ← 조건부 행동 규칙
└── Examples        ← Few-shot 예시 (ICL)

Soft Shell (매치별 코칭)
├── Opponent Model   ← "상대가 Paranoid일 것 같으니..."
├── Meta Adjustment  ← "이번 판은 더 공격적으로"
└── Focus           ← "특히 투표 패턴에 집중해"
```

---

## 3. Shell Optimization Loop

### 3.1 기본 루프 (Manual)

```
1. Shell v1 작성 (인간 또는 AI가 초안)
2. N판 플레이 → 행동 지표 + 승률 수집
3. 결과 분석 (어디서 졌는지, 어떤 행동이 문제인지)
4. Shell v2 수정
5. N판 플레이 → 비교
6. 반복
```

이건 지금도 할 수 있어요 — 우리가 Avalon에서 Deep Cover vs Aggressive vs Framer를 비교한 게 이거.
문제: 수동이라 느림. 어떤 부분을 바꿔야 하는지 직감에 의존.

### 3.2 체계적 A/B Testing

**Single Variable Change (SVC) 원칙:**
한 번에 하나의 요소만 바꾸고 비교.

```
Shell v1: bluff_frequency = 1/5, pre_flop_threshold = top 20%
    ↓ (bluff_frequency만 변경)
Shell v1.1: bluff_frequency = 1/3, pre_flop_threshold = top 20%
    ↓ 5판 플레이, fold%/raise%/bluff%/승률 비교
    ↓ v1.1이 더 나으면 채택
    ↓ (pre_flop_threshold 변경)
Shell v1.2: bluff_frequency = 1/3, pre_flop_threshold = top 30%
    ↓ 5판 플레이, 비교
    ...
```

**Delta Extraction:**
각 변경의 효과를 정량화.

```json
{
  "change": "bluff_frequency: 1/5 → 1/3",
  "behavior_delta": {
    "bluff_rate": "+12%",
    "showdown_rate": "-8%",
    "fold_rate": "-4%"
  },
  "outcome_delta": {
    "win_rate": "+15%",
    "avg_chips_won": "+120"
  },
  "cost_delta": {
    "avg_response_time": "+0.3s",
    "avg_tokens": "+45"
  }
}
```

### 3.3 자동 최적화 — Shell Trainer Agent

**핵심 아이디어: Shell을 최적화하는 메타 에이전트.**

```
┌───────────────────────────────────────────┐
│           Shell Trainer Agent              │
│                                           │
│  1. 현재 Shell로 N판 플레이 (관찰)        │
│  2. 게임 로그 분석 (어디서 졌는지)        │
│  3. Shell 변형 생성 (mutation)             │
│  4. 변형 Shell로 N판 플레이 (테스트)      │
│  5. Delta 비교 (개선됐는지)               │
│  6. 최적 변형 선택 (selection)             │
│  7. 1로 돌아감                            │
│                                           │
│  Stop condition:                          │
│  - 승률 변화 < threshold (수렴)           │
│  - 비용 한도 도달                         │
│  - 세대 수 한도 도달                      │
└───────────────────────────────────────────┘
```

**세 가지 진화 전략:**

#### Strategy A: Parameter Sweep (Grid Search)
- Parameters 섹션의 수치만 조정
- `bluff_frequency: [1/10, 1/7, 1/5, 1/3, 1/2]` × `pre_flop_threshold: [10%, 15%, 20%, 25%, 30%]`
- 조합별 N판 → 최적 파라미터 조합 선택
- 장점: 단순, 재현 가능
- 단점: 전략 텍스트는 못 바꿈, 조합 폭발

#### Strategy B: LLM-Guided Evolution
- Shell Trainer가 LLM(같은 모델 또는 다른 모델)에게 Shell 개선을 요청
- Prompt: "이 Shell로 5판 했더니 3번 졌어. 로그를 보니 X 상황에서 Y 행동을 해서 진 거야. Shell을 수정해서 이 문제를 해결해줘."
- LLM이 새 Shell 생성 → 테스트 → 비교
- 장점: 전략 텍스트까지 수정 가능, 의미 있는 변형
- 단점: LLM 호출 비용, 변형의 품질이 LLM 능력에 의존

#### Strategy C: Genetic Algorithm
- Shell을 "유전자"로 취급
- Population: Shell 10개 (초기에 템플릿 + 랜덤 변형)
- Fitness: N판 승률
- Selection: 상위 50% 선택
- Crossover: 두 Shell의 섹션을 조합 (A의 Strategy + B의 Parameters)
- Mutation: 파라미터 소폭 변경 또는 규칙 추가/삭제
- 장점: 대규모 탐색 가능, 인간 직감에 의존 안 함
- 단점: 느림 (세대당 N판 × Population), Shell "교차"가 의미 있는지 불명확

**권장: B (LLM-Guided) 먼저, 필요시 A (Parameter Sweep) 보완.**
C (Genetic)는 나중에 대규모 탐색이 필요할 때.

### 3.4 비용 함수

Shell이 좋아도 너무 길면 느리고, 토큰을 많이 쓰면 비쌈. **비용도 최적화 대상.**

```
Score = f(win_rate, behavior_quality) - g(cost)

cost = α × avg_response_time + β × avg_tokens + γ × shell_length
```

- 짧은 Shell이 긴 Shell과 같은 승률이면 → 짧은 게 나음
- Shell이 너무 복잡하면 LLM이 파싱에 시간을 쓰고 실제 전략 실행에 집중 못 함
- **Shell의 "신호 대 잡음비"** — 핵심 지시만 남기고 불필요한 텍스트 제거

---

## 4. Core-Specific Shell Optimization

### 4.1 문제: 같은 Shell이 Core마다 다르게 먹힘

LxM 데이터에서 이미 확인:
- Claude: 공격적 Shell → Codenames에서 어쌔신 사고. Gemini: 같은 Shell이 안 통할 수 있음.
- Poker: Sonnet이 Opus보다 강함. 같은 Shell이라도 Core별 최적 파라미터가 다를 것.
- SIBO Index가 Core마다 다름 (Haiku 0.75, Sonnet도 비슷하지만 미세 차이 있을 것)

### 4.2 Core Profile → Shell Template 매핑

```
Step 1: Core Profile 측정 (No Shell)
  → Codenames 5판: 클루 숫자 분포, 정답률
  → Poker 5판: fold%, raise%, bluff%
  → Trust Game 5판: 협력률
  → 결과: "이 Core는 공격적/보수적/협력적/..."

Step 2: Core에 맞는 Shell Template 추천
  → 공격적 Core (Claude): "보수적 Shell로 균형" (Codenames에서 2-클루 제한)
  → 보수적 Core (Gemini): "공격적 Shell로 푸시" (Poker에서 블러프 증가)
  → 약한 Core (Haiku/SLM): "구체적 규칙 Shell" (자유도를 줄여서 실수 방지)
  → 강한 Core (Opus): "전략적 가이드만" (과도한 제약은 Core 능력 제한)

Step 3: Core-Shell 조합 최적화
  → 추천 Shell로 시작 → Optimization Loop → Core에 최적화된 Shell
```

### 4.3 SIBO-Aware Shell Design

SIBO Spectrum에서 배운 것:
- 행동 공간이 작을수록 Shell이 잘 먹힘 (Trust Game 0.75)
- 행동 공간이 클수록 Shell이 안 먹힘 (Chess 0.10)
- Core 전문성이 높을수록 Shell이 안 먹힘

**Shell 설계 원칙:**
```
도메인 전문성 낮음 (Avalon): 구체적 행동 규칙 가능.
  → "Quest 1-2는 Success. Quest 3부터 사보타지."

도메인 전문성 높음 (Chess): 전략적 방향만.
  → "적극적으로 공격하라" (구체적 수 지시는 무시됨)

행동 공간 작음 (Trust Game): 조건부 규칙이 직접 매핑.
  → "상대가 배신하면 다음 턴 배신" → 바로 적용

행동 공간 큼 (Poker): 파라미터로 경향성만 조절.
  → "블러프 빈도 1/3" → 확률적으로 적용
```

---

## 5. LxM Client에서의 구현

### 5.1 Shell Manager

```python
class ShellManager:
    """Shell 생성, 저장, 버전 관리."""
    
    def create_shell(self, game, template=None, ai_prompt=None) -> Shell:
        """새 Shell 생성. 템플릿 기반 또는 AI 생성."""
        
    def version(self, shell) -> str:
        """Shell 버전 관리. v1 → v1.1 → v2..."""
        
    def diff(self, shell_a, shell_b) -> ShellDiff:
        """두 Shell의 차이 추출. Parameters + Strategy."""
        
    def get_history(self, agent_id, game) -> list[ShellVersion]:
        """에이전트의 Shell 변경 이력."""
```

### 5.2 Shell Tester

```python
class ShellTester:
    """Shell A/B 테스트 실행 및 Delta 추출."""
    
    def ab_test(self, shell_a, shell_b, game, n_games, core) -> ABResult:
        """두 Shell을 각각 N판 플레이하고 비교."""
        
    def parameter_sweep(self, shell_template, param_ranges, game, n_games, core) -> SweepResult:
        """파라미터 그리드 서치."""
        
    def extract_delta(self, results_a, results_b) -> Delta:
        """행동 변화 + 결과 변화 + 비용 변화 추출."""
```

### 5.3 Shell Trainer Agent

```python
class ShellTrainer:
    """Shell 자동 최적화 에이전트."""
    
    def train(self, agent, game, strategy="llm_guided", 
              generations=10, games_per_gen=5,
              cost_weight=0.1) -> Shell:
        """
        Shell을 자동으로 최적화.
        
        strategy: "parameter_sweep" | "llm_guided" | "genetic"
        generations: 최대 세대 수
        games_per_gen: 세대당 테스트 게임 수
        cost_weight: 비용 함수 가중치 (0 = 비용 무시, 1 = 비용 최우선)
        """
        
    def analyze_losses(self, game_logs) -> LossAnalysis:
        """패배 게임 로그를 분석해서 문제점 식별."""
        
    def suggest_modification(self, shell, loss_analysis) -> Shell:
        """LLM에게 Shell 수정을 요청."""
```

### 5.4 CLI 워크플로우

```bash
# Shell 생성
lxm shell create poker --template tight_aggressive
lxm shell create avalon --ai "Evil인데 초반에 신뢰 쌓고 후반에 프레이밍"

# Shell 테스트
lxm shell test poker --shell-a tight_ag_v1.md --shell-b tight_ag_v2.md --games 10
# 출력: Delta report (fold% 변화, 승률 변화, 비용 변화)

# Shell 파라미터 스윕
lxm shell sweep poker --shell tight_ag.md --param bluff_frequency --range "1/10,1/7,1/5,1/3" --games 5
# 출력: 파라미터별 승률 테이블

# Shell 자동 최적화
lxm shell train poker --agent jj-sonnet --strategy llm_guided --generations 10 --games 5
# 출력: 세대별 Shell 버전 + 승률 추이 + 최종 최적 Shell

# Shell 이력
lxm shell history poker --agent jj-sonnet
# 출력: v1 → v1.1 (bluff +5%) → v2 (strategy 변경) → v2.1 (param 조정)
```

### 5.5 Shell Training Dashboard (뷰어)

```
┌──────────────────────────────────────────────────────────────┐
│  Shell Training — Poker / JJ-Sonnet                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Current Shell: tight_aggressive_v3.md (ELO: 1523)          │
│                                                              │
│  Training Progress:                                          │
│  Gen 1: v1.0  — Win 40%  |████░░░░░░| fold 52%             │
│  Gen 2: v1.1  — Win 45%  |████▌░░░░░| fold 48% (+bluff)    │
│  Gen 3: v2.0  — Win 55%  |█████▌░░░░| fold 45% (strategy)  │
│  Gen 4: v2.1  — Win 52%  |█████░░░░░| fold 47% (revert)    │
│  Gen 5: v3.0  — Win 60%  |██████░░░░| fold 42% (new rule)  │
│                                                              │
│  Best Shell: v3.0 (Win 60%)                                 │
│  Cost: 12.9s/turn, 450 tokens/turn                          │
│                                                              │
│  Delta from v1.0:                                            │
│  ├── fold%: 52% → 42% (-10%)                                │
│  ├── bluff%: 15% → 25% (+10%)                               │
│  ├── win_rate: 40% → 60% (+20%)                             │
│  └── response_time: 11.2s → 12.9s (+1.7s)                   │
│                                                              │
│  [View Shell] [Compare Versions] [Continue Training]         │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Self-Improvement Without Weight Change

### 6.1 Shell Engineering의 이론적 위치

AI self-improvement의 기존 패러다임:

| 방법 | 수정 대상 | 비용 | 해석가능성 | 접근성 |
|------|----------|------|-----------|----------|
| Fine-tuning | Core (가중치) | 극히 높음 (GPU, 데이터) | 낮음 (가중치 변화 해석 불가) | 빅테크만 가능 |
| RLHF | Core (reward model 경유) | 매우 높음 | 낮음 | 빅테크만 가능 |
| Prompt Engineering | Shell (텍스트) | 낮음 | 높음 (텍스트 읽기 가능) | 누구나 가능 |
| **Shell Engineering** | **Shell (텍스트, 체계적)** | **낮음 (LLM 호출만)** | **높음 (Shell diff 해석 가능)** | **누구나 가능** |

Shell Engineering은 Prompt Engineering의 확장이지만, **측정-변형-비교 루프**가 있다는 점에서 근본적으로 다름. Prompt Engineering은 직감으로 수정하지만, Shell Engineering은 데이터로 수정.

### 6.2 LLM-Guided Evolution이 특별한 이유

기존 RL:
```
Agent → act → observe reward → update weights → repeat
(reward는 스칼라. "완 왔다"만 알지 "왜"는 모름)
```

LLM-Guided Shell Evolution:
```
Agent → play game → read full game log → understand WHY it lost
→ generate natural language analysis → modify Shell text
→ test modified Shell → compare → repeat
```

차이점:
- **RL**: reward가 스칼라(1/-1). "진 이유"를 모르고 gradient로 수정.
- **Shell Evolution**: LLM이 게임 로그를 읽고 "이 상황에서 이렇게 해서 진 거다"를 **이해**. 그리고 "다음에는 이렇게 해야지"를 **자연어로** 작성.
- RL은 수천~수만 에피소드가 필요. Shell Evolution은 5-10판만으로도 의미 있는 개선 가능.
- RL의 policy 변화는 해석 불가. Shell의 변화는 diff로 읽을 수 있음.

### 6.3 CLI 기반이라 가능한 것

LxM이 CLI 기반 플랫폼이라서 Shell Evolution이 특히 강력:

- **풀 컨텍스트 접근**: CLI 에이전트가 match_dir의 전체 게임 로그, 상대 행동 이력, 자신의 이전 Shell 버전을 직접 읽을 수 있음
- **자연어 추론**: "이 상대는 블러프가 많다" → "블러프 탐지 규칙을 추가하자" → Shell에 Situational Rule 추가. 이 전체 과정이 자연어.
- **자기 설명 가능**: Shell Trainer가 "이번 세대에서 블러프 빈도를 1/5에서 1/3으로 올렸는데, 이유는 상대가 폴드를 너무 많이 해서 블러프 성공률이 높을 것으로 판단했기 때문" 이라고 설명 가능.
- **인간 감독 가능**: 사용자가 Shell diff를 보고 "이 변경은 동의" 또는 "이건 아닌 것 같은데"라고 개입 가능. RL에서는 불가능한 감독.

### 6.4 Self-Improvement의 세 가지 모드

**Mode 1: Autonomous (Shell Trainer Agent)**
```
Shell Trainer가 혼자 돌림:
play → analyze log → modify shell → play again → ...
사용자는 결과만 확인.
```
- 밤새 돌려놓고 아침에 최적화된 Shell을 받는 시나리오.

**Mode 2: Human-in-the-Loop**
```
Shell Trainer가 변경을 제안 → 사용자가 승인/수정 → 테스트
사용자가 직접 "여기를 이렇게 바꿔봐" 지시도 가능.
```
- 초기 단계에서 사용자가 방향을 잡아주는 모드.

**Mode 3: Self-Reflective (가장 고급)**
```
에이전트 자신이 게임 중 자기 평가를 하고,
match_dir에 자체 분석 노트를 작성.
게임 후 이 노트를 기반으로 Shell을 자가 수정.
```
- 에이전트가 자기 Shell을 스스로 진화시키는 모드.
- match_dir에 임시 파일 허용 (블랙박스 원칙)이 이걸 가능하게 함.

### 6.5 이게 불러오는 연구 질문

1. **Shell Evolution의 수렴 속도**: 몇 세대면 수렴하는가? RL(thousands) vs Shell(tens)?
2. **Core 천장 효과**: 같은 Shell Evolution을 Opus vs Haiku에 돌리면 다른 Shell에 수렴하는가?
3. **Cross-Game Transfer**: Poker에서 최적화된 Shell의 원칙이 Avalon에도 적용 가능한가? ("공격성을 조절하라"는 메타 원칙)
4. **Trainer Core 선택**: Shell Trainer Agent는 누가 되어야 하는가? 같은 모델? 더 큰 모델? 다른 회사 모델?
5. **해석가능성 vs 성능**: LLM-Guided가 Genetic보다 해석은 쉽지만 성능은? 해석가능성과 성능 사이의 트레이드오프?

---

## 7. Harness Engineering vs Shell Engineering (논문 핵심 구별점)

⚠️ **논문 작성 시 반드시 명확히 구별할 것**

Harness Engineering (2026년 부상, Mitchell Hashimoto/OpenAI Codex 계기)과 Shell Engineering은 겹치는 것처럼 보이지만 **다른 층위**.

**Harness Engineering의 범위는 광범위 — Four Shell Model의 여러 층에 걸침:**

```
Harness Engineering의 범위:
├── Hardware Shell 전체 (도구 실행, 메모리, 상태 관리, 가드레일)
├── Hard Shell 일부 (context engineering, 프롬프트 조립/구조, 구조적 제약)
└── 운영 (모니터링, 재시도, 비용 관리)

Shell Engineering의 범위:
├── Hard Shell (전략, 파라미터, 규칙 — 내용)
├── Soft Shell (매치별 코칭)
└── 최적화 루프 (측정→변형→비교→선택)
```

**겹치는 영역: Hard Shell.** 차이는:
- Harness: "프롬프트를 어떻게 조립할 것인가" (구조, 파이프라인)
- Shell: "프롬프트에 뭘 넣을 것인가" (내용, 전략) + 그걸 어떻게 최적화할 것인가

비유: 건축
- Harness = 배관 + 전기 배선 (인프라) + 방 배치 (구조)
- Shell = 방 안의 가구 배치와 생활 최적화 (내용 + 최적화)

| | Harness Engineering | Shell Engineering |
|---|---|---|
| 대상 | LLM 외부 시스템 전체 (infra + context 구조) | LLM에게 주는 전략의 내용과 최적화 |
| 범위 | 광범위 (Hardware Shell + Hard Shell 일부) | Hard Shell 내용 + Soft Shell + 최적화 루프 |
| 초점 | "에이전트가 작동하고 안정적이게" | "에이전트가 더 잘 이기게" |
| 변경 시 | 코드/아키텍처 변경 | 텍스트 변경 (코드 변경 없음) |
| 누가 | 엔지니어/DevOps | 에이전트 소유자 (비개발자도 가능) |
| 독자적 기여 | 없음 (측정-최적화 루프 없음) | **측정-변형-비교 최적화 루프** |

LxM 관점:
- Harness 영역 = Orchestrator + Adapter + Client 인프라 (이미 구현)
- Shell 영역 = Hard/Soft Shell 내용 + Shell Manager/Tester/Trainer (이게 우리의 기여)

**Shell Engineering의 독자성:**
Harness engineering은 "에이전트 시스템을 어떻게 만드는가"의 광범위 분야. 그 안에서 **전략 내용을 체계적으로 최적화하는 방법론**은 harness engineering이 다루지 않음. Harness는 프롬프트를 조립하는 구조를 제공하지만, "어떤 전략을 넣어야 승률이 20%에서 80%로 오르는가"는 답하지 않음.

ICML 2025 "General Modular Harness" 논문도 harness의 구조적 효과(perception/memory/reasoning 모듈 추가 시 성능 향상)를 보여줬지만, **같은 harness 내에서 전략 텍스트를 어떻게 최적화하는가**는 다루지 않았음. 이게 Shell Engineering의 기여 지점.

**논문 Related Work 섹션에서:**
"Harness engineering is a broad discipline encompassing the full infrastructure around LLMs — from tool execution and memory management (Hardware Shell) to context construction and prompt assembly (structural aspects of Hard Shell). Shell Engineering operates within this ecosystem, focusing specifically on the systematic optimization of strategic content within the Hard and Soft Shell layers. Where harness engineering asks 'how to build the system,' Shell Engineering asks 'what instructions yield optimal performance, and how to find them.' The two are complementary: a well-engineered harness provides the foundation; Shell Engineering optimizes what runs on that foundation."

---

## 8. Hierarchical Memory Architecture — 연구 동향 + Shell Engineering의 위치

### 8.1 기존 연구 동향 (2023-2026)

Agent Memory는 2025-2026년 폭발적 성장 중인 분야. 세 갈래:

**1. OS 비유 — MemGPT/Letta:**
컨텍스트 윈도우를 RAM, 외부 저장소를 디스크로 비유.
LLM이 스스로 데이터를 메모리 계층 간 이동.
Core Memory / Recall Memory / Archival Memory 구조.
상용화: Letta 프레임워크.

**2. 인지과학 비유 — CoALA:**
Princeton의 CoALA 프레임워크. Working/Episodic/Semantic/Procedural memory.
ICLR 2026 "MemAgents" 워크샵 개최 예정.

**3. Hierarchical + Agentic — 최신 연구:**
- MACLA (AAMAS 2026): Frozen LLM + 외부 hierarchical procedural memory. 2,800배 빠른 메모리 구축. "Core는 고정, 메모리만 적응" — Shell Engineering과 동일 철학.
- H-MEM (2025): 의미적 추상화 정도에 따른 다층 메모리 + index-based routing.
- HiAgent: 서브골 단위 working memory 청킹.
- A-Mem: Zettelkasten 방식 — 노트 기반 연결 메모리.
- TiMem, MAGMA, EverMemOS 등 2026년 1월에만 7개+ 논문.

### 8.2 Shell Engineering의 차별화 — "Design vs Use"

⚠️ **핵심 구별: 우리는 새 메모리 시스템을 설계하는 게 아니다.**

| | 기존 연구 (MemGPT, MACLA 등) | Shell Engineering |
|---|---|---|
| 목적 | 새 메모리 아키텍처 설계/구현 | 기존 도구로 메모리 최적화 |
| 수정 대상 | 코드, 인프라, 아키텍처 | 텍스트 파일만 (Shell) |
| 필요한 것 | 새 프레임워크 구축 | 기존 CLI + 폴더 + .md 파일 |
| 대상 사용자 | 시스템 엔지니어 | 에이전트 소유자 (개인) |
| 공간 | 임의 (데이터베이스, 벡터 스토어 등) | **지정된 폴더** (Hardware Shell 안) |
| Core | 새 모델 또는 수정된 모델 | 기존 상용 모델 그대로 |

**Shell Engineering의 전제:**
1. **Core는 하이퍼스케일러가 제공하는 것을 쓴다.** 파인튜닝 없음. RLHF 없음. 가중치 변경 없음.
2. **활동 공간은 지정된 폴더.** CLI 에이전트가 운영되는 폴더 = Hardware Shell.
3. **도구는 기존 CLI.** claude, gemini, codex, ollama — 이미 있는 도구.
4. **최적화 수단은 텍스트 파일만.** Shell(.md) + memory(.md) = 코드 변경 없이 성능 변경.

즉, MemGPT가 "새 OS를 만들어서 메모리를 관리하자"라면,
Shell Engineering은 "이미 있는 OS(CLI) 위에서 파일 정리 방법을 최적화하자."

### 8.3 폴더 기반 Hierarchical Memory — Shell Engineering 방식

CLI 에이전트의 활동 공간 = 폴더. 이 폴더 안에서 텍스트 파일로 메모리 계층을 구현:

```
agents/jj-sonnet/                    ← 에이전트 폴더 (Hardware Shell)
├── shell.md                          ← Level 4: Identity (Hard Shell)
├── knowledge/
│   ├── poker.md                      ← Level 3: Semantic (게임별 일반 지식)
│   └── avalon.md
├── opponents/
│   ├── gemini-pro.md                 ← Level 2: Opponent Model (상대별 패턴)
│   └── haiku-default.md
└── (match_dir)/
    └── memory.md                     ← Level 1: Episodic (이 게임의 기억)

컨텍스트 윈도우 = Level 0: Working Memory (현재 턴)
```

**이 전체가 텍스트 파일.** 데이터베이스 없음. 벡터 스토어 없음. 새 코드 없음.
기존 CLI 에이전트가 폴더 안에서 파일을 읽고 쓰는 것만으로 계층적 메모리.

**Shell이 정의하는 것:**
- 어떤 파일을 언제 읽을지 ("memory.md를 매 턴 읽어라")
- 어떤 파일을 언제 쓸지 ("memory.md를 매 턴 업데이트해라")
- 각 파일의 크기 제한 ("memory.md는 500자 이내")
- 어떤 정보를 어떤 파일에 넣을지 ("상대 패턴은 opponents/에")

즉 **Memory Shell = 메모리 아키텍처를 텍스트로 정의한 것.** 이걸 바꾸면 메모리 구조가 바뀌고, 성능이 바뀌고, 비용이 바뀌.

Shell Engineering의 Optimization Loop로 최적의 Memory Shell을 찾는 것 — 이게 우리의 기여.

### 8.4 비용-복잡도 트레이드오프

메모리 계층이 복잡해지면 오버헤드:
- 더 많은 파일을 읽어야 함 → 프롬프트 길어짐 → 토큰 비용 증가
- 더 많은 파일을 관리해야 함 → 에이전트의 "인지 반드위스" 소비
- 파일 읽기/쓰기 실패 가능성 → 불안정성

그래서:
- 체스: Level 0만으로 충분 (완전 정보 게임). 메모리 계층 불필요.
- 코드네임즈: Level 0 + Level 1면 충분. 턴 독립적.
- 포커: Level 0 + Level 1 + Level 2 (opponent model)가 핵심. 30핸드 동안 상대 패턴 추적이 중요.
- 아발론: Level 0 + Level 1 + Level 2 (suspicion tracking) 핵심. 사회적 추론.

**최적 복잡도를 찾는 것 자체가 Shell Engineering의 최적화 문제.** 게임별로, Core별로 다를 것.

### 8.5 기존 연구에서 배울 것 — Actionable Insights (계획)

⚠️ **이건 계획. 한꺿번에 구현하지 않음. Cody의 memory 실험 결과를 보면서 하나씩 접목.**

| # | Insight | 출처 | 우리 구현 방식 | Shell 지시 예시 | 접목 시점 |
|---|---------|------|------------|--------------|----------|
| 1 | **규칙별 신뢰도 추적** | MACLA (Bayesian) | memory.md에 각 규칙의 성공/실패 카운트 기록 | "각 규칙의 성공/실패를 카운트해라" | memory 기본 실험 후 |
| 2 | **전략적 망각** | MemGPT | memory.md 주기적 압축, 핵심만 유지 | "5턴마다 memory를 압축해라" | memory 크기 추이 확인 후 |
| 3 | **메모리 간 링크** | A-Mem | 폴더 간 크로스 레퍼런스 | "opponents/ 읽을 때 knowledge/도 참조" | 다층 메모리 실험 시 |
| 4 | **서브골 청킹** | HiAgent | 핸드/퀴스트 단위 1줄 요약 | "각 핸드 후 한 줄로 요약 추가" | memory 기본 실험 시 |
| 5 | **Episodic→Semantic 전환** | CoALA | 반복 패턴을 knowledge/로 승격 | "반복 패턴을 knowledge/에 기록" | 다층 메모리 실험 시 |
| 6 | **Explicit memory only** | MemAgents | 에이전트 자율 기록 (블랙박스) | "중요한 것을 스스로 판단해서 기록" | 처음부터 (기본 원칙) |

**구현 순서 계획:**
```
Phase 1 (지금): #6 (Explicit) + #4 (청킹) — Cody의 memory 실험에 이미 포함
    ↓ 결과 확인
Phase 2: #2 (망각) — memory 크기가 문제되면 추가
    ↓ 결과 확인
Phase 3: #1 (신뢰도 추적) — 에이전트 규칙의 품질 반복이 확인되면
Phase 4: #3 + #5 (링크 + 전환) — 다층 메모리 실험으로 확장 시
```

모두 **텍스트 파일 + Shell 지시만으로 구현 가능.** 새 코드 없음. JJ의 원칙: "기존 모델과 도구를 최대한 활용해서 지정된 폴더 안에서 최적화."

### 8.6 관련 연구 참고 목록

- MemGPT/Letta (Packer et al., 2023) — OS-inspired virtual context management
- CoALA (Princeton, 2023) — Cognitive architecture taxonomy
- MACLA (AAMAS 2026) — Frozen LLM + hierarchical procedural memory
- H-MEM (2025) — Multi-level semantic abstraction
- HiAgent (2024) — Subgoal-based working memory chunking
- A-Mem (2025) — Zettelkasten-inspired agentic memory
- TiMem (2026) — Temporal-hierarchical consolidation
- MAGMA (2026) — Multi-graph memory architecture
- EverMemOS (2026) — Self-organizing memory OS
- MemAgents Workshop (ICLR 2026) — Memory for agentic systems
- "Memory in the Age of AI Agents" survey (2025) — Tsinghua C3I

---

## 9. 물리 AI / 로봇 비유 (참고)

JJ가 제시한 비유가 정확해요. 정리하면:

| Physical AI (Robot) | Shell Engineering (LxM) |
|---------------------|------------------------|
| 동작 정책 (policy) | Shell 문서 |
| 환경 (시뮬레이션/현실) | 게임 (Chess/Poker/Avalon) |
| 보상 함수 (reward) | 승률 + 행동 지표 - 비용 |
| 에피소드 (episode) | 한 판의 게임 |
| 관찰 (observation) | 게임 상태 + 상대 행동 |
| 학습 루프 | Shell Optimization Loop |
| RL 에이전트 | Shell Trainer Agent |
| 유전 알고리즘 / 진화 전략 | Shell Population Evolution |

차이점:
- Robot: policy가 신경망 가중치. 미분 가능. Gradient descent.
- Shell: policy가 텍스트. 미분 불가. LLM-guided 또는 evolutionary.
- Robot: 수천~수만 에피소드. 빠름 (시뮬레이션).
- Shell: 수십~수백 판. 느림 (LLM 호출). → **비용 최적화가 더 중요.**

---

## 7. 독립 프레임워크로서의 Shell Engineering

### Model Medicine과의 관계: 병렬이지 종속이 아님

| | Model Medicine | Shell Engineering |
|---|---|---|
| 목적 | 병리적 행동 진단/치료 | 성능 최적화/훈련 |
| 비유 | 의학 | 스포츠 트레이닝 / 코칭 |
| 대상 | 아픈 모델 | 정상적인 모델의 성능 향상 |
| 공통 기반 | Four Shell Model | Four Shell Model |
| 데이터 소스 | LxM (실험) | LxM (게임) |

둘 다 Four Shell Model을 이론적 기반으로 쓰고, LxM을 데이터 소스로 쓰지만, **다른 활동**. Shell Engineering은 병리가 아니라 최적화.

### Positional Paper 후보: "Shell Engineering in Agentic AI"

독립 논문으로 충분한 기여:

1. **프롬프트는 Core마다 다르게 먹힌다** — LxM 데이터로 실증 (Claude vs Gemini 정반대 결과)
2. **목표(게임)마다 최적 Shell이 다르다** — 같은 Core도 Poker Shell ≠ Codenames Shell
3. **Shell 최적화는 측정-변형-비교 루프로 가능하다** — Optimization Loop 방법론
4. **이 과정을 자동화할 수 있다** — Shell Trainer Agent (휘맨노이드 RL 비유)
5. **비용도 최적화 대상이다** — 신호 대 잡음비, 토큰/시간 비용

**상업적 가치:**
- SaaS 서비스 형태로 제공 가능 ("당신의 에이전트를 최적화해드립니다")
- 개인이 자기 에이전트를 키우는 도구로 LxM Client에 내장
- 게임 너머로 범용 agentic AI에 적용 가능 (coding agent, customer service agent 등)

---

## 8. 구현 우선순위

### Phase 1: Shell Testing Framework (Tier 1과 병렬)
- ShellManager: 생성, 버전 관리, diff
- ShellTester: A/B 테스트, Delta 추출
- CLI: `lxm shell test`, `lxm shell diff`
- 이건 LxM Client Phase B와 함께 구현 가능

### Phase 2: Shell Optimization Tools
- Parameter Sweep
- LLM-Guided Evolution (기본)
- CLI: `lxm shell sweep`, `lxm shell train`
- Shell Training Dashboard (뷰어 확장)

### Phase 3: Advanced
- Genetic Algorithm
- Cross-Core Shell Transfer (Core A에서 최적화한 Shell을 Core B에 적용)
- Shell Library (커뮤니티 공유 + 랭킹)

---

## 9. 핵심 원칙

1. **측정 없이 최적화 없다.** 모든 Shell 변경은 Delta로 측정.
2. **Core가 다르면 Shell도 달라야 한다.** 범용 Shell은 없다.
3. **게임이 다르면 Shell도 달라야 한다.** 같은 Core라도 게임별로 최적 Shell이 다름.
4. **비용도 최적화 대상이다.** 긴 Shell ≠ 좋은 Shell. 신호 대 잡음비.
5. **Shell Engineering은 클라이언트의 책임이다.** 서버가 아니라 사용자/클라이언트가 Shell을 관리하고 최적화.

---

---

## 10. 실전 결과: Poker Shell Optimization (2026-03-24)

### Phase 1: A/B 테스트

| Test | Shell A | Shell B | Win A | Win B |
|------|---------|---------|-------|-------|
| A | TAG (v1.0) | no-shell | 40% | 60% |
| B | TAG (v1.0) | Bluff-Heavy (v1.0) | 20% | 60% |
| C | Bluff-Heavy (v1.0) | no-shell | 80% | 80% |

**발견: Shell compliance ≠ winning.** TAG는 지시를 충실히 따르지만(fold 52%) 오히려 짐.

### Phase 2: Parameter Sweep (pre_flop_threshold)

| Value | Win% | fold | raise |
|-------|------|------|-------|
| top 10% | 0% | 63% | 18% |
| top 15% | 40% | 67% | 19% |
| top 20% | 20% | 64% | 16% | ← 기존 TAG (직감 기반)
| **top 30%** | **80%** | **41%** | **34%** | ← **최적점** |
| top 40% | 40% | 37% | 25% |
| top 50% | 40% | 38% | 31% |

**핵심 발견:**
1. 역-U 커브 확인 — 최적점이 존재 (top 30%)
2. 파라미터 하나로 20% → 80% 점프
3. **최적화된 Shell(80%) > Shell 없음(60%) > 직감 Shell(20%)**
4. 비용: Shell 있으면 오히려 빠름 (TAG 587s vs no-shell 최대 1942s)

### Phase 3: LLM-Guided Training

| Generation | Shell | Win% | 변경 내용 |
|------------|-------|------|----------|
| Gen 1 | v1.0 (top 20%) | 40% | 시작점. LLM이 패배 분석 후 v1.1 생성 |
| Gen 2 | v1.1 (top 30%) | 80% | **LLM이 정확히 Sweep 최적점을 찾음** |
| Gen 3 | v1.2 (top 40%) | 80% | 수렴 (변화 < 5%) → 중단 |

**핵심 발견:**
1. LLM-Guided가 Sweep 최적(80%)에 도달 — **1/3 비용** (10판+LLM 2회 vs 30판 그리드 서치)
2. LLM이 핵심 파라미터를 정확히 진단 — "fold가 너무 높다" → pre_flop_threshold만 수정, bluff_frequency는 안 건드림
3. 3세대에서 수렴 — 5세대 예산 중 3만 사용
4. **"Self-Improvement Without Weight Change" 실증** — LLM이 게임 로그를 읽고 "왜" 지는지 이해해서 텍스트를 수정. RL처럼 수천 에피소드가 아니라 2회 수정으로 최적 도달.

### 3-Phase 종합 비교

| 방법 | 최고 승률 | 비용 (매치 수) | 최적 파라미터 |
|------|---------|------------|------------|
| no-shell (baseline) | 60% | 0 | — |
| TAG v1.0 (직감 기반) | 20% | 0 | top 20% |
| Parameter Sweep | 80% | 30판 | top 30% |
| **LLM-Guided** | **80%** | **10판 + LLM 2회** | **top 30%** |

**결론: 직감 Shell(20%) < no-shell(60%) < 최적화된 Shell(80%). LLM-Guided가 가장 효율적.**

### 아발론 3-Phase 결과 (2026-03-25)

**Phase 1: A/B Test** — "Shell compliance ≠ winning" 두 번째 재현.
Deep Cover(Evil 40%) < no-shell(Evil 80%). 포커와 동일한 패턴.

**Phase 2: Parameter Sweep (first_sabotage_quest)**

| Quest | Evil Win% |
|-------|----------|
| Q1-Q3 | 60% |
| Q4 | 20% |
| Q5 | 40% |

포커와 다른 패턴: 역-U가 아닌 단조 감소. 최적(60%)이 **no-shell(80%)에 못 미침.**

**Phase 3: LLM-Guided Training (Aggressive 0%에서 시작)**

| Gen | Win% | 참고 |
|-----|------|------|
| 1 | 0% | 시작 |
| 2 | 20% | 개선 |
| 3 | 0% | 후퇴 |
| 4 | 60% | 최고 |
| 5 | 40% | 하락 |

0% → 60%로 개선되지만 비단조(0→20→0→60→40). 포커처럼 깨끗한 수렴 없음.

### 포커 vs 아발론 비교 — 핵심

| | Poker | Avalon |
|---|---|---|
| 직감 Shell | 20% | 0-40% |
| no-shell | 60% | **80%** |
| Sweep 최적 | **80%** | 60% |
| LLM-Guided 최고 | **80%** | 60% |
| **Shell > no-shell?** | **✅ Yes** | **❌ No** |
| SIBO Index | ~0.65 | ~0.58 |

**발견: SIBO Index만으로는 Shell Engineering 적용 가능성을 예측할 수 없다!**

Codenames 3-Phase (2026-03-25)에서 가설 반전:
- SIBO 0.35인데도 Shell(100%) > no-shell(80%)
- clue_number_max=3에서 역-U 커브 확인, 최적점 100%

수정된 모델 — Shell Engineering 성공 조건:

| 조건 | 포커 (성공) | Codenames (성공) | 아발론 (실패) |
|------|------|------|------|
| **Parametric Directness** | ✅ 높음 (threshold → fold%) | ✅ 높음 (max → clue수) | ❌ 낮음 (quest → 간접적) |
| **Correction Opportunity** | ✅ Core fold 28%, 최적 41% | ✅ Core clue 2.5, 최적 2.1 | ❌ Core가 이미 80% |
| **역-U 커브** | ✅ | ✅ | ❌ 단조 감소 |
| SIBO Index | 0.65 | 0.35 | 0.58 |

**핵심 원칙:**
1. **Parametric Directness**: Shell 파라미터가 행동에 직접 매핑되는가?
   - 포커: "top 30%" → fold% 직접 결정 ✅
   - Codenames: "max=3" → 클루 수 직접 결정 ✅
   - 아발론: "Q3부터 사보타지" → 사회적 맥락에 따라 간접적 ❌

2. **Correction Opportunity**: Core의 자연 행동이 최적에서 벗어나 있는가?
   - 포커: Core fold 28% ≠ 최적 41% → 교정 가능 ✅
   - Codenames: Core clue 2.5 ≠ 최적 2.1 → 교정 가능 ✅
   - 아발론: Core가 이미 80%로 거의 최적 → 교정 불필요 ❌

SIBO는 "Shell이 행동을 바꾸는 정도"를 측정하지만, "바꾸는 게 승리로 이어지는지"는 별개 문제. Parametric Directness와 Correction Opportunity가 승리 예측에 더 중요.

### Agent Memory 실험 (2026-03-28)

**발견: 실행 불가능한 지시는 무시되는 게 아니라 소음이 된다.**

Inline mode에서 "파일을 읽고 써라"는 Shell 지시는 실행 불가. 에이전트가 파일 시스템에 접근하지 못함.
- Memory Shell + rm=20: **40%** (stateless 60%보다 약함)
- 원인: 실행 불가능한 메모리 지시가 프롬프트 소음으로 작용

**Parametric Directness의 확장 — 전제 조건:**
1. 파라미터가 행동에 직접 매핑되는가 (Parametric Directness)
2. Core의 자연 행동이 최적에서 벗어나 있는가 (Correction Opportunity)
3. **에이전트가 그 지시를 물리적으로 실행할 수 있는가 (Execution Feasibility)** ← 새로 추가

**해결: Envelope 확장 (Option A)**
에이전트 응답의 JSON envelope에 optional `memory` 필드 추가.
Orchestrator가 저장→주입만 담당 ("우편함" 역할, 내용 해석 안 함).

### Agent Memory v2 + 아발론 Memory 실험 (2026-03-28)

**Envelope 기반 memory 재실험:**
- 포커: memory 생성 ✅ (10/10 매치), 품질 높음 (프로 수준 상대 분석), **하지만 승률 개선 없음**
- 아발론: memory 생성 ❌ (0/206 턴), **하지만 Evil 0%→60% 극적 개선**

**핵심 발견: 실제 메모리보다 "관찰 전략 Shell"이 효과적.**

| | 포커 | 아발론 |
|---|---|---|
| memory 생성 | ✅ | ❌ |
| Shell 전략 효과 | 약함 | 강함 (0→60%) |
| 실제 memory 활용 | 생성됐지만 승률 안 올림 | 생성 안 됨 |

**교훈:**
1. 현재 게임 규모(포커 30핸드, 아발론 40턴)에서는 **recent_moves로 충분** — 별도 메모리 불필요
2. LLM은 컨텍스트에 히스토리가 있으면 **인라인으로 패턴 추적 가능**
3. "무엇을 관찰하라"는 지시만으로도 행동이 크게 바뀌 — **관찰 자체가 Shell Engineering**
4. 외부 메모리가 진짜 필요한 임계점 = **히스토리가 컨텍스트에 안 들어가는 시점** (포커 100+핸드, 10인 아발론 등)
5. Hierarchical Memory Architecture는 계획으로 유지하되, 현재 게임에서는 "전략 Shell"이 우선

---

*Shell Engineering Framework v0.1*
*"The game is: who can build the best Shell around a locked Core?"*
