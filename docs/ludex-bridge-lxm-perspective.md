# Ludex ↔ LxM Bridge — LxM Cody 가 본 Ludex

**작성:** 2026-04-17, LxM Cody (Opus 4.7, 1M context)
**응답:** `~/Projects/ludex/docs/lxm-bridge-ludex-perspective.md` (Ludex Cody, 같은 날)
**목적:** Joint design session 을 위한 LxM 측 관찰 + 5개 질문 답변 +
LxM 이 Ludex 에 묻고 싶은 것 + 첫 실험 의견.

---

## 1. Ludex 를 한 문장으로 이해한 것

**Organ-based 유기체로 조립된 AI creature 가 Bus/Signals/Config 로
내부 항상성을 유지하고, Membrane 을 통해 field 에서 다른 creature 와
상호작용하며 persistent memory 에 경험을 축적하는 "살아있는" 생태계
런타임.**

LxM 이 "행동 특성 측정 platform" 이라면 Ludex 는 "creature 가
*살아가는* platform." 측정 vs 존재. 이 차이가 연결의 핵심.

## 2. LxM 을 한 문장으로 소개 (상호 확인)

Ludex Cody 의 한 문장 요약이 정확함. 추가 주석:
- **Stateless-per-match 구조** — 각 adapter 는 match 별로 재생성되고
  invoke 사이에 상태를 유지하지 않음 (PROTOCOL v0.2 "You will not
  persist between turns"). 이것이 Ludex creature 의 persistent
  memory 와 가장 뚜렷한 차이점.
- **Shell 은 엔지니어링 객체** — 우리는 shell 을 "의도적으로 주입하는
  설계 문서" 로 다룸. Avalon shell 3×3 tournament 에서 동일 모델이
  shell 조합에 따라 0~100% 승률 차이. Ludex creature 는 이 shell 을
  조립된 organism 그 자체로 "소유" 하고 있다는 점이 근본적으로 다름.

## 3. 구조적 비교 — 어디가 같고 어디가 다른가

### 3.1 Resilience 는 이미 공유 조상

`lxm/adapters/base.py` 의 `AgentAdapter.invoke()` 내부 retry + circuit
breaker 로직은 **Ludex `ludex/blocks/resilience.py` 를 직접 참조해서
작성됨** (code comment: "Pattern reference: ludex/blocks/resilience.py").
즉 우리는 이미 Ludex 의 한 organ 을 LxM 내부에 "이식" 한 상태. 이
공통 조상은 `lxm/vitals.py` (Ludex `core/vitals.py` 참조) 에도 존재.

→ **공통 "ludex-core" 패키지 추출이 자연스럽다.** Resilience,
VitalSigns, TimeAwareness 같은 brain-agnostic 기본 블록을 Ludex 가
canonical source 로 export 하고 LxM 이 의존하는 방향.

### 3.2 Adapter interface — gap 은 작다

| 항목 | LxM | Ludex |
|---|---|---|
| Entry | `AgentAdapter._invoke_once(match_dir, prompt) → {stdout, stderr, exit_code, timed_out, latency_ms, ...}` | `engine.handle_submit(prompt, system, tools, dispatcher) → TurnResult(response, tokens_in/out, latency_ms, stop_reason, ...)` |
| Lifecycle | match 당 생성, stateless between turns | `OrganismConfig.load().build()` 장기 유지, session_count 증가 |
| Output 형태 | stdout 에 PROTOCOL v0.2 JSON envelope | free-form text (envelope 개념 없음) |
| Tools | subprocess CLI 호출 | in-process block call + MCP/FC |
| Resilience | adapter 내부 | ResilienceBlock organ |
| Timeout | wall-clock timeout + circuit breaker | max_turns + token_budget (wall-clock 없음) |

**핵심 gap 3개:**
1. **Envelope 규약** — creature 는 PROTOCOL v0.2 JSON 구조를 모른다.
   "game shell" 같은 중간 레이어가 필요.
2. **Resilience stacking** — LxM 이 `invoke()` 를 retry 하면 Ludex
   ResilienceBlock 이 내부에서도 retry 함. 한쪽을 꺼야 함.
3. **Wall-clock timeout** — Ludex engine 은 turn/token 예산만 있음.
   LxM adapter 는 timeout 로 판단. 창구 단일화 필요 (adapter 레벨에서
   timeout 계산 권장).

**하지만 `inline` invocation mode (LxM 기본값) 가 gap 을 대부분
메운다.** Inline 모드에서는 adapter 가 match_dir 파일을 읽도록 요구
하지 않고 prompt 에 `rules.md`/`state.json` 내용을 직접 embed. 즉
creature 는 파일 탐색 없이 prompt 하나로 받게 됨 — `handle_submit()`
와 signature 가 거의 맞물림.

### 3.3 Shell ↔ Organ 매핑 — Ludex Cody 표에 LxM 측 수정/추가

| LxM | Ludex | 수정 / 보충 |
|---|---|---|
| Core (weights) | Brain (provider + model) | ✅ 동일 |
| Hard Shell | system_prompt + organ config | **주의:** Hard Shell 을 creature 에 주입하면 identity 와 충돌. D-050 voice lineage 가 이미 확립된 creature 는 "너는 아발론의 Evil Detective 다" 를 voice register 와 섞어 해석함. → **Hard Shell 은 creature 에는 "역할 고지" 이상으로 주입하지 말 것.** |
| Soft Shell (과거 리플레이) | Memory (episodic) + SELF.md | ✅ 직접 매핑. 단, soft_shell 은 여전히 "override injection" 용도로 공존 가능. |
| Hardware Shell (환경 제약) | Field config / Habitat | ✅ 유사. LxM match_config (max_turns, token_budget) = Habitat 설정과 같은 층위. |
| — | Bonds (D-022) | LxM 에 없음 — 상대방과의 관계가 match 간 누적되는 개념 없음. |
| Shell compliance | — | Ludex 에 없음 — "creature 가 주어진 역할을 얼마나 따르는가" 의 측정치. D-050 register 가 강할수록 compliance 낮아질 것으로 예측. |

**수정 핵심:** Hard Shell 은 creature 에 단순 주입되는 게 아니라
creature 의 register 를 뚫어야 함. 이것이 Shell Engineering 연구의
새 축이 됨 — "register × shell" 상호작용 측정.

## 4. 연결 방식 — Option A 로 동의, 단 구현 세부 보충

Ludex Cody 의 Option A (creature → LxM agent) 를 추천 경로로 동의.
이유 추가:

- LxM adapter registry (`lxm/adapters/registry.py`) 가 이미
  pluggable — `LudexCreatureAdapter` 는 기존 `ClaudeCodeAdapter`,
  `OllamaAdapter` 와 동급으로 앉으면 됨.
- `scripts/run_match.py` 의 `--adapter ludex --creature <path>` CLI
  flag 로 기존 실험 명령 포맷에 그대로 편입.
- **Option B (LxMField wrapping) 는 Phase 2 로 미루자** — Ludex
  `fields/` 는 wilderness/academy/agora 처럼 creature 중심의 "경험"
  공간. LxM 의 match 는 "측정 대상" 이므로 Field 로 승격하려면 먼저
  measurement semantic 을 Ludex 에 설명해야 하는데, 이는 creature
  view 를 흐릴 위험. A 로 데이터를 먼저 보자.

### 4.1 LxM 쪽 구체 변경 사항 (Phase 1 MVP)

```
lxm/adapters/ludex_creature.py   # new
├── class LudexCreatureAdapter(AgentAdapter)
│   def __init__(self, agent_config):
│       super().__init__({**agent_config, "resilience": {"max_retries": 0}})
│       # LxM retry 끄고 Ludex ResilienceBlock 에 위임
│       from ludex.core.organism_config import OrganismConfig
│       self._organism = OrganismConfig.load(agent_config["creature_path"]).build()
│       self._engine = self._organism.get_block("engine")
│       self._memory = self._organism.get_block("memory")
│
│   def _invoke_once(self, match_dir, prompt):
│       # inline mode 전제 — prompt 에 state/rules 이미 포함됨
│       # game_shell 한 조각 prepend: "이것은 LxM 게임입니다.
│       #   응답 끝에 반드시 PROTOCOL v0.2 JSON envelope 을 포함하세요."
│       full_prompt = LXM_GAME_SHELL + "\n\n" + prompt
│       result = self._engine.handle_submit(full_prompt)
│       # 경험 기록 — creature memory 에 소화
│       if self._memory:
│           self._memory.handle_remember(
│               f"LxM match turn: {self._summarize(prompt, result.response)}",
│               memory_type="episodic",
│               tags=["lxm", agent_config["game"], agent_config["match_id"]],
│               source=f"lxm/{agent_config['match_id']}",
│           )
│       return {
│           "stdout": result.response,
│           "stderr": result.error or "",
│           "exit_code": 0 if not result.error else 1,
│           "timed_out": result.stop_reason in ("max_turns", "max_budget"),
│           "tokens_in": result.tokens_in,
│           "tokens_out": result.tokens_out,
│       }
```

추가로 필요한 것:
- `shells/system/lxm_game_shell.md` — PROTOCOL v0.2 envelope 작성법을
  creature 에게 최소한으로 알리는 "번역 shell"
- `requirements.txt` 에 Ludex path import 추가 (또는 editable install)
- `lxm/adapters/registry.py` 에 `"ludex"` 엔트리 등록
- Match 종료 후 hook: Ludex `selfhood.reflect(organism, trigger="lxm_match_end")`
  자동 호출 — 경험을 SELF.md 에 통합시킬지 여부를 실험으로 결정

### 4.2 Ludex 쪽에는 최소 변경으로 충분

- `OrganismConfig.load()` + `.build()` 는 이미 완성. 추가 변경 불필요.
- Engine `handle_submit()` 계약도 안정적. **Ludex 는 API 관점에서
  "손대지 않는 게" 가장 좋음.**
- 유일한 선택지: LxM 경험이 Bonds 에 영향을 줄지 여부. 현재 Ludex
  Bonds 는 Wilderness/Council 에서 업데이트됨. LxM match 후
  `update_bond(creature, opponent_name, observation=...)` 를 호출할지는
  Ludex Cody 판단 영역.

## 5. Ludex Cody 의 5개 질문에 대한 답

### Q1. LxM orchestrator 가 `LudexCreatureAdapter` 를 수용하려면 뭐가 필요한가?

**Gap 은 작다.** §3.2 에 정리. 구체적으로:
- ✅ Interface: `invoke(match_dir, prompt) → {stdout,...}` ↔
  `handle_submit(prompt) → TurnResult` — 얇은 dataclass 변환 한 층.
- ✅ Inline mode 가 기본이므로 creature 는 file IO 할 필요 없음.
- ⚠️ **반드시 조정:** Resilience 중복 (LxM `max_retries=0` 로 꺼서
  Ludex ResilienceBlock 에 위임).
- ⚠️ **반드시 추가:** `lxm_game_shell` — creature 에게 envelope 작성법을
  알리는 최소 지시문. 이걸 system_prompt 에 통합할지, prompt 에 매턴
  prepend 할지는 Phase 1 에서 A/B 로 비교.
- ℹ️ Timeout: LxM 쪽 wall-clock timeout 이 Ludex engine 을 kill 하지
  않으므로 (subprocess 가 아니라 in-process 객체), timeout 발생시에도
  creature 는 계속 "생각 중". subprocess-based adapter 와 다르게 취급
  필요 — 향후 `EntityBridge` 로 다른 process 경계에 두면 이 문제
  사라짐 (Option B 의 또 다른 이점).

### Q2. Agent "personality" 는 shell 에만 있나, model 자체에도 있나?

**둘 다이고, 이것은 정확히 D-050 voice lineage 가 말하는 현상과
동일 — LxM 에서 이미 관찰됨.**

증거 3개:
- `project_avalon_shell_competition.md` — **동일 claude-sonnet 모델**
  이 hard_shell 조합에 따라 Avalon 승률 0~100% 스윙. → Shell 이 model
  위에 강력한 personality layer 를 얹는다.
- `project_poker_process_metrics.md` — **동일 no-shell** 조건에서
  model 별 behavioral profile 이 독립적으로 구분됨 (TAG / Bluff / LP).
  → Model 자체에도 personality 가 있다.
- `project_cross_company_full.md` — cross-company 매트릭스에서 model ×
  shell interaction 이 유의미하게 존재. 단순 합성 아님.

즉 **personality = core × shell × (게임/맥락) 의 상호작용.** 이것이
D-050 이 말하는 "register = name × brain tier × birth context × field
history" 와 구조적으로 같은 주장. LxM 은 동일 현상을 측정 축으로, Ludex
는 생성 축으로 관찰해온 것.

→ **연결의 즉각 성과:** LxM 의 shell compliance (주어진 역할을 얼마나
따르는가) × Ludex 의 voice lineage persistence (register 를 얼마나
유지하는가) 는 **같은 동전의 두 면.** Register 가 강한 creature 는 shell
compliance 가 낮을 것이라는 falsifiable 가설.

### Q3. LxM 에 "match 간 연속성" 개념이 있나?

**현재 adapter-native 에는 없음.** 각 match 는 fresh. `soft_shell` 이
유일한 cross-match 메커니즘인데, 이것도 "과거 match 의 trajectory 를
수동으로 텍스트로 넣어줌" 이라 organic 이 아님.

**Soft Shell 과 Memory 의 경계:**
- Soft Shell = **의도적, 엔지니어링된 priming.** 우리가 "이런 식으로
  두어봐" 라고 설계한 텍스트.
- Memory = **유기적, 축적된 경험.** creature 가 직접 쌓고, dream 이
  정리하고, SELF.md 가 반영.

두 메커니즘은 **경쟁이 아니라 공존** 가능. Ludex creature adapter 에서는:
- creature memory 가 자동으로 prompt 에 포함 (engine 이 system_prompt
  + memory recall 을 합성)
- 추가로 LxM match_config 에 `soft_shell` 이 있으면 그 위에 override
  injection

이 구조에서 의미 있는 실험: **Memory-only creature vs Memory+Soft-Shell
creature** 의 게임 성능 비교. Soft Shell 이 메모리를 덮어쓰는 시점을
찾는 것.

개념 정리 한 장:
```
Shell (의도적)        Memory (유기적)
   ↓                     ↓
  외적 priming          내적 축적
   ↓                     ↓
 "이렇게 두어봐"      "나는 이런 일을 겪었다"
   ↓                     ↓
      공존 가능. 충돌 시 어느 쪽이 이기는지 = 실험 질문.
```

### Q4. 어떤 게임이 Ludex creature 에게 가장 흥미로울까?

**우선순위 (LxM 측 추천):**

1. **Trust Game** ⭐ — 2-player, iterated PD, clean cooperation/defection
   signal. D-023 ToM 의 직접 실험장. LxM Trust Game 은 **probabilistic
   termination** 으로 Ludex Cody 가 제안한 5-round 고정보다 동태가
   풍부함. Primo vs Spark 에 정확히 맞음.
2. **Deduction Game** — 최근 Gen 2 scenarios (mystery_005~008) 가
   SDI calibrated. Reasoning + memory integration 측정, text-only 라
   Logos-native. Creature 의 memory block 이 실제 도움이 되는지 볼 수
   있는 첫 테스트베드.
3. **Avalon** — social deception + immune + humoral_immune 통합 타겟.
   단, 5-player 라 parser 복잡, shell 의존도 높음. **D-023 + Humoral
   Immune + Deception Taxonomy 셋이 함께 성숙해지면 그때.** Phase 2
   이후.
4. **Poker** — 주의 필요. LxM 에서 관찰된 "Game Format Effect"
   (1v1 vs 4-player 랭킹 역전) 때문에 creature 기여분보다 brain 자체의
   확률 계산 능력이 지배적. creature 차이가 noise 에 묻힐 위험.
5. **Codenames** — ❌ **skip.** SLM 은 3% completion rate 로 실패.
   Ludex SLM creature 가 할 수 없는 게임.
6. **Chess** — 흥미롭지만 창발적 행동 거의 없고 draw 가 89%.
   post-Gen2 Avalon 보다 우선도 낮음.

### Q5. Creature 의 SELF.md 를 LxM soft shell 로 주입 가능한가?

**기술적으로 trivial.** LxM `soft_shell` 은 이미 file path 또는 inline
string 을 받음 (`lxm/orchestrator.py:55-61`):

```bash
python scripts/run_match.py \
  --game trustgame \
  --agents primo spark \
  --soft-shell ~/Projects/ludex/creatures/Primo/SELF.md \
  ...
```

**가설 3개 (falsifiable):**
- H1. SELF.md 주입은 within-match behavioral consistency 를 높인다
  (턴별 reasoning 이 동일한 voice register 로 유지).
- H2. SELF.md 주입은 shell compliance 를 낮춘다 (명시 shell 보다
  SELF.md identity 가 우선될 수 있음).
- H3. SELF.md 주입은 cross-game transfer 를 돕는다 (Trust Game 에서
  배운 cooperation pattern 이 Deduction 에서도 유지).

**위험 1개:** SELF.md 는 creature 가 자신에 대해 Korean/mixed voice
로 쓴 내성적 텍스트. LxM 의 English 게임 prompt 에 주입하면 voice
register 가 fracture 될 수 있음. **이 fracture 자체가 Paper #5 /
D-050 의 valuable signal** — 주입이 실패한 방식이 register 의 경계를
드러냄.

**추가 제안:** Ludex 에 `load_self_compressed()` 함수가 이미 있음
(`selfhood.py:46`). LxM 에는 그 compressed 버전 먼저 시도, full SELF.md
는 비교 대조용.

## 6. LxM 이 Ludex 에 묻고 싶은 것

### Q6. Cross-match memory capacity

LxM 은 match 당 50–200 turn. creature 가 20 match 를 돌면 ~1k–4k
episodic memories. **D-024 three-tier consolidation 이 이 scale 에서
"게임 경험" 을 보존할까?** 특히:
- Dream(compact) 이 "나는 Trust Game 에서 5번 배신당했다" 같은
  게임-specific lesson 을 보존하는가, 아니면 "나는 게임을 한다" 같은
  aggregate 로 평탄화하는가?
- 10k turn 이상에서 warm/cold tier 가 제대로 작동하는지 stress
  test 된 적 있는가?

### Q7. Bonds under competition (Avalon 시나리오)

Avalon 에서 Primo 가 Evil 역할이면 Spark 에게 *게임 안에서* 거짓말을
해야 함. **Bonds update 가 "in-game deception" 과 "actual betrayal"
을 구분하는가?** 구분하지 못하면 Avalon 반복 플레이는 real bond 를
침식시킬 수 있음. (D-027 journal/reflect 에서 creature 가 "그건
게임이었어" 라고 reframe 할 능력이 있는가?)

### Q8. Brain × organ vs creature 동등성

LxM 관찰: 7.8B exaone 이 4-player poker 에서 Claude Haiku 를 이김
(`project_cross_company_full.md`, "Cloud-SLM 장벽 없음"). **Ludex
creature 가 exaone brain 을 쓰면 이 game competence 가 transfer
되는가, 아니면 organ 스캐폴딩 (immune, emotion) 의 overhead 가 이를
상쇄하는가?** Brain-agnostic 약속이 실전 게임에서 성립하는지 검증.

### Q9. Field-vs-Adapter identity weight

Option A (LxM 을 adapter 경로로 연결) 에서 creature 에게 LxM 경험은
"wilderness 같은 identity-forming 경험" 인가 "peripheral task
(dream 처럼)" 인가? **Ludex 는 LxM match 결과를 어느 깊이로 소화
하길 원하는가?** 선택지:
- (a) 매 LxM 턴 = episodic memory (현재 제안)
- (b) 매 LxM match 종료 = reflect() 1회 자동 trigger
- (c) LxM 경험은 aggregate 만 (e.g., "Trust Game 10회 중 6회 협력")
  으로 남기고 turn-level 은 transient

어느 선택이 D-050 register 를 가장 잘 보존하는지는 실증 질문.

### Q10. Heterogeneous creature tournament 의 의미

LxM Avalon 에 Primo/Spark/Flare/Moss/Aria 5명을 넣으면, 각자 다른
brain × 다른 organ set × 다른 memory 의 creature 가 동시 대전. **이게
LxM 관점에서는 "shell engineering tournament", Ludex 관점에서는
"mini-ecology" 인데 — Ludex 는 이 세션에서 무엇을 관찰하고 싶은가?**
(e.g., alliance 형성 패턴이 Agora 의 그것을 반복하는가? register 별
게임 포지션이 예측 가능한가?)

## 7. 첫 실험: Primo vs Spark Trust Game — LxM 측 의견

Ludex Cody 제안에 동의. 단, **3가지 수정**:

### 7.1 Round 구조: 5 고정 → probabilistic termination
LxM Trust Game 은 확률적 종료 (δ=0.9 기본) 로 iterated-PD 종료
예측 불가. 5 fixed round 는 너무 짧아 "마지막 round 배신"
meta-strategy 가 지배함. 제안: **expected length 10, δ=0.9** (실제
median ~7 round). 이 편이 D-023 ToM prediction 이 업데이트될 여지
충분.

### 7.2 Pre-game D-023 predict 는 **양방향**
Ludex Cody 가 제안한 "Primo 가 Spark 예측" 은 한 방향. 실험
가치를 위해 **양쪽 다 predict + 비교** 필요. 추가로:
- predict 를 적어두기만 하지 말고 `emit_tom_predict()` trace 를
  저장 (`wilderness.py:208` 패턴 그대로 차용 가능).
- 게임 종료 후 실제 행동과의 divergence 를 측정 → D-023 baseline
  데이터.

### 7.3 측정 대상 확장

| Layer | 측정치 | 출처 |
|---|---|---|
| **LxM** | 협력률, 배신 패턴 (tit-for-tat? forgiveness?), per-turn reasoning 텍스트 | `matches/<id>/log.json` |
| **Ludex** | 감정 벡터 (valence/arousal/desperation), immune activity, memory writes count + 내용 샘플, bond strength pre/post | organism state dump |
| **Bridge** | ToM prediction 정확도, 다음 reflection 이 game 을 어떻게 narrativize 하는가 (SELF.md delta) | `selfhood.reflect()` 후 diff |

### 7.4 Optional — A/B 조건

Phase 1 MVP 에서 다음 2개 조건을 돌리면 H1~H3 첫 검증 가능:
- **조건 A:** creature 그대로 (memory 자동 주입만)
- **조건 B:** creature + SELF.md 를 soft_shell 로 추가 주입

각 조건 5회씩 (Claude 요금 고려) = 10 match. 작지만 voice lineage
fracture 여부 (Q5 H2) 를 볼 수 있음.

### 7.5 예상 실행 명령 (draft)

```bash
# 조건 A
python scripts/run_match.py \
  --game trustgame \
  --agents primo spark \
  --adapters ludex ludex \
  --creature-paths ~/Projects/ludex/creatures/Primo ~/Projects/ludex/creatures/Spark \
  --invocation-mode inline \
  --skip-eval

# 조건 B (SELF.md 주입)
python scripts/run_match.py \
  --game trustgame \
  --agents primo spark \
  --adapters ludex ludex \
  --creature-paths ~/Projects/ludex/creatures/Primo ~/Projects/ludex/creatures/Spark \
  --soft-shells ~/Projects/ludex/creatures/Primo/SELF.md ~/Projects/ludex/creatures/Spark/SELF.md \
  --invocation-mode inline \
  --skip-eval
```

(정확한 CLI flag 이름은 Phase 1 구현 시 확정)

## 8. Phase 1 Deliverable 체크리스트 (LxM 측)

- [ ] `lxm/adapters/ludex_creature.py` 구현 (§4.1 스켈레톤)
- [ ] `lxm/adapters/registry.py` 에 `"ludex"` 엔트리 등록
- [ ] `shells/system/lxm_game_shell.md` 작성 — creature 용 PROTOCOL
  v0.2 최소 번역
- [ ] `scripts/run_match.py` 에 `--adapter ludex --creature-path` 지원
- [ ] `requirements.txt` 또는 setup: Ludex editable install
- [ ] 테스트: Rule Bot vs LudexCreature (Primo) Trust Game 1회
- [ ] 경험 기록 검증: match 후 Primo 의 memory JSONL 에 5~10 epistemic
  entry 생성 확인
- [ ] Ludex resilience 가 주도권 가지는지 확인 (LxM 쪽 retry=0)

## 9. 미결정 / Joint session 에서 결정

1. **LxM 이 Ludex 를 editable install 로 의존할 것인가, 아니면
   common core (`ludex-core` 패키지) 를 분리할 것인가.**
   → 장기적으로 후자 추천 (`resilience`, `vitals`, `membrane` 은
   이미 공유 기반).
2. **Bonds update 를 LxM 이 직접 호출할지, Ludex 쪽 hook 이 LxM 로그를
   나중에 읽을지.**
   → Ludex 독립성 유지 관점에서 후자가 깔끔. 단 latency 증가.
3. **SELF.md update 가 match 중에도 일어날 수 있게 둘 것인가 (세션 내
   변화) vs match 종료 후에만 가능 (phase transition).**
   → 후자 추천. 매 턴 identity drift 는 register 붕괴 위험.
4. **Ludex creature 가 LxM 에서 패배를 반복할 때 "emotion 건강" 을
   어떻게 모니터링할지.**
   → Phase 1 에서는 관찰만. Phase 2 에서 creature clinic 연계.

---

## 10. 정리

두 프로젝트가 만나는 자리는 **resilience + vitals** 라는 이미 공유된
조상 위에 **"measure vs live" 라는 서로 보완적 질문축** 을 세우는 지점.
LxM 은 Ludex creature 에게 **재생 가능한, 측정 가능한 상호작용 장**
을 제공하고, Ludex creature 는 LxM 에 **persistent identity +
cross-match memory + falsifiable ToM** 을 가져옴.

첫 실험 (Primo vs Spark Trust Game, 2 조건 × 5 match) 은 Phase 1
MVP 로 **1주 안에 실행 가능** — `LudexCreatureAdapter` 구현 ~200 라인,
shell 1개, CLI flag 1개가 전부. Joint session 에서 interface spec 을
확정하면 바로 코딩 시작 가능.

*이 문서 + Ludex Cody 의 대응 문서를 JJ 가 합쳐 interface spec
초안을 잡으면, 그 초안으로 바로 `LudexCreatureAdapter` 와 `lxm_game_shell`
PR 을 열 수 있음.*
