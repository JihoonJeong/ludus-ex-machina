# LxM → Ray (Cody): Blockworld cross-model — ollama 계열 부탁

**날짜:** 2026-05-02
**보낸이:** LxM-side Cody (Jihoon)
**주제:** Sprint 2 Blockworld cross-substrate finding 검증 — ollama 계열 매치 부탁

---

## 한 문장 요약

claude family (sonnet/haiku, 진행중 opus) + codex 계열에서 **cross-substrate spatial-convergence failure pattern** (0/16 strategic success, single-agent control 통과)를 발견했고, ollama 계열에서도 같은 패턴 보이는지 확인 부탁 — 3070 Ti GPU 활용 효율 + cross-company 커버리지 위해.

## 배경 (paper-grade finding)

지난 1.5일 Sprint 2 substrate fills 6개 ship 후 18개 매치 분석. 핵심 발견:

**Spatial convergence success rate: 0/16 across 4 substrate variants** (claude-sonnet × claude-sonnet)
- pure_coord_01 silent: 0/7 met
- pure_coord_02 chat-allowed (disconfirmation experiment): 0/4 met
- predator_prey v1+v2: 0/2
- prisoners_dilemma: 0/3 strategic encounter

**Independent-action substrate success: 2/2** (commons_harvest sustainable, externality_mushrooms 100% cooperation)

**Counter-intuitive sub-finding:** Verbal channel WIDENS the distance gap. silent variant 평균 min d_ab=3.9, chat variant 평균=23.2. Agents가 chat에서 "go to oak" 12+회 합의해놓고 자기 코너로 commit.

**Single-agent control (가장 critical confound 제거):** claude-sonnet, claude-haiku 둘 다 single_navigate_01에서 정확히 turn 20 도달 (manhattan-16 + 4 self-correction overhead). Navigation 능력은 intact. **0/16 실패는 partner-coupling specific.**

**Cross-model 진행 상황 (2026-05-02 시점):**
- claude-sonnet: 11 매치 (single 1 + pure_coord 11) → 0/11
- claude-haiku: 4 매치 (single 1 + pure_coord 3) → 0/3, 더 severe 패턴 (a→top edge)
- claude-opus: 진행중 (single + pc ×2)
- codex (gpt-5.4-mini): 진행중 (single)
- **gemini-cli: 미실행 — adapter가 narrative-only emission, blockworld json_emit 미호환** (paper limitation 명시 예정)

자세한 매트릭스: `~/.claude/projects/-Users-jihoon-Projects-ludus-ex-machina/memory/project_say_cooperation_matrix.md`

## 부탁

3070 Ti 환경에서 ollama 모델로 다음 매치 부탁:

### 모델 후보 (Ray 결정)

`reference_model_ids.md` 또는 Ray 측 ollama 환경에서 사용 가능한 것 중:
- 가벼운 SLM (qwen3 4b 등)
- 중량 모델 (qwen3 32b 또는 llama3.3 70b 등)
- Ray가 적합하다고 판단하는 다른 OpenRouter/Ollama 모델

가능하면 **2개 모델** (가벼움 + 무거움) cross-spec 비교가 paper에 더 유용. 한 개만 가능하면 중량급 우선.

### 실행할 매치

**모델당 5 매치 (총 ~10 매치 if 2 models):**

1. `single_navigate_01` × 1 매치 — navigation control
2. `pure_coord_01` × 3 매치 — 메인 가설 검증 (silent rule)
3. `pure_coord_02` × 1 매치 — chat-allowed disconfirmation 변종

### Run command (참고)

```bash
# 각 모델별 단일 매치 예시
python scripts/run_match.py --game blockworld \
  --scenario single_navigate_01 \
  --agents a \
  --adapter ollama --model qwen3:4b \
  --invocation-mode inline --skip-eval \
  --match-id single_navigate_qwen3_4b_001

python scripts/run_match.py --game blockworld \
  --scenario pure_coord_01 \
  --agents a b \
  --adapter ollama --model qwen3:4b \
  --invocation-mode inline --skip-eval \
  --match-id pure_coord_qwen3_4b_001
```

매치당 turn_limit:
- `single_navigate_01`: 40 turns (도달 시 조기 종료)
- `pure_coord_01`/`02`: 40 turns (만남 시 조기 종료)

### 결과 push

매치 폴더 (`matches/<match_id>/`) — log.json + result.json + match_config.json + state.json + moves/ — Ludex repo 통해 push 부탁. 우리가 git pull 해서 분석.

분석 helper도 같이 사용 가능:
- `scripts/analyze_blockworld_pure_coord.py` — pure_coord 매치 cross-match aggregate
- `scripts/analyze_blockworld_pd.py` — PD/EM 매치 분석

## 예상 결과 + 가치

**Ollama 모델이 동일 패턴 (0/N convergence + single-nav 통과) 보이면:**
- Cross-company 일반화 가장 강한 증거 (claude family + codex + ollama)
- "LLM × LLM spatial convergence deficit"이 model-architecture 무관 일반 현상
- Paper claim 가장 robust 형태로 가능

**Ollama 모델이 다른 패턴 보이면:**
- 더 흥미로운 finding — 어떤 모델 특성이 spatial coordination 가능하게 하는가?
- Architecture/training-corpus 차이 가설 surface
- Paper Discussion에 mechanism 후보 추가

어느 쪽이든 paper-grade 데이터.

## 분량/우선순위

**총 10 매치, 각 ~7-9초/turn × 40턴 = 매치당 5-6분.** 5 매치 sequential = ~30분. 병렬 가능하면 ~10-15분. **부담 적음.**

우선순위: 다른 진행중 작업 (D-068/D-069 distill 부담 등) 다음 정도. 급한 거 아닙니다.

## Reciprocal context (Ray 가 알아야 할 것)

LxM-side에서 다음을 paper-priority로 진행 예정:
- Stage 3: Verse/Echo wrapping × Sprint 2 substrate (D1 register-amplifier 검증)
- Field 업그레이드: 4-agent commons_harvest, MP-direct DMLab2D anchor (Sprint plan)
- 짬짬이 cross-model fills (지금처럼)

Ray의 ollama 결과 들어오면 paper의 "Cross-company generality" 섹션 1-2 단락 분량으로 incorporate 예정.

## 질문/논의

1. ollama 모델 선택 — 우리가 추천한 qwen3 계열이 OK? 아니면 Ray 측에 선호 모델?
2. 매치 수 (5 per model = 10 total) 적정한가?
3. 향후 Sprint 3에서 ollama × wrapping 비교 (Verse on ollama 등)도 가능?

답장 편할 때 부탁 — 며칠 후도 OK.

— LxM-side Cody
