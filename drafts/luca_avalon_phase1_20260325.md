# Luca — Avalon Phase 1 + Rule Bot 업데이트

## Avalon Phase 1: A/B 테스트 결과

30판 완료. 5인 all-Sonnet, Good = no-shell 고정.

| Test | Condition | Evil Win% |
|------|-----------|-----------|
| A | Deep Cover | 40% |
| A | no-shell | **80%** |
| B | Aggressive | 60% |
| B | no-shell | 60% |
| C | Deep Cover | 40% |
| C | Aggressive | **0%** |

### 핵심 발견

1. **"Shell compliance ≠ winning" 아발론에서도 재현.** Deep Cover(Evil 40%)가 no-shell(Evil 80%)보다 약함. 포커 TAG와 같은 패턴.

2. **no-shell Evil이 80%로 가장 강함.** Shell 없이 자유롭게 플레이하는 게 오히려 나음 — LLM의 자체 판단이 현재 템플릿보다 나음.

3. **Aggressive 0% (vs Deep Cover)** — 이전 Cross-Shell 데이터와 일치. 프레임워크가 기존 결과를 재현함.

4. **포커와 동일한 패턴 확인: 기본 Shell이 성능을 해침.** 두 게임에서 동일하게 나타나므로 게임을 넘어 일반화 가능.

### 시사점

- 포커: TAG(20%) → 최적화 후 80%. 아발론에서도 같은 개선 가능할 것.
- Deep Cover의 문제: "초반 신뢰 쌓기"가 오히려 Good에게 유리한 정보를 줌? 아니면 사보타지 타이밍 제약이 문제?
- **아발론 Phase 2 (Parameter Sweep)** 으로 `first_sabotage_quest` 최적점 찾는 게 다음 단계.

## Rule Bot 구현 완료

Gap Analysis의 규칙 기반 봇 4게임 전부 구현:

| 게임 | 전략 | 난이도 |
|------|------|--------|
| **Poker** | 핸드 강도 기반 (Chen-inspired) | easy/medium/hard |
| **Chess** | Stockfish 래퍼 (depth 1/5/10) | easy/medium/hard |
| **Trust Game** | always_cooperate / tit_for_tat / suspicious_tft | easy/medium/hard |
| **Tic-Tac-Toe** | first_empty / heuristic / minimax | easy/medium/hard |

레지스트리에 `rule_bot`으로 등록. 사용:
```bash
python scripts/run_match.py --game poker \
  --agents my-sonnet rule-bot --adapters claude rule_bot --models sonnet medium
```

### Rule Bot as Shell Test Opponent

rule_bot을 Shell 테스트 상대로 쓸 수 있으면:
- **LLM 비용 절반** (상대 호출 = 0원)
- **속도 2배** (상대 응답 즉시)
- **결정적** (같은 상태 → 같은 응답)

검증 결과:

| Shell | vs LLM (Sonnet) | vs rule_bot(medium) |
|-------|-----------------|---------------------|
| TAG | 40% | 100% |
| Bluff-Heavy | 80% | 100% |
| Optimal | 80% | 100% |

**rule_bot(medium)은 너무 약해서 LLM 대체 불가.** fold 36-51%로 Sonnet(28%)보다 훨씬 수동적. Shell 효과를 측정하려면 상대가 어느 정도 강해야 하는데, 현재 rule_bot은 기준에 못 미침.

개선 옵션:
- hard 모드 강화 (더 공격적 + 블러프 추가)
- Sonnet no-shell의 행동 분포를 모방하는 "imitation" 모드
- 또는 현재는 LLM 상대로 유지하고, rule_bot은 Training Mode 전용으로

### 초기 rule_bot 버그 수정
포커에서 `to_call` 파싱 버그 발견 → 수정 완료. 포커 상태에 `to_call` 필드가 없고 `current_bet`(게임) - `current_bet`(플레이어)로 계산해야 했음.

## 다음 단계

1. **rule_bot 검증 결과** 대기 → LLM 상대와 유사하면 이후 Shell 테스트 전부 rule_bot으로
2. **아발론 Phase 2** — Deep Cover parameter sweep (first_sabotage_quest)
3. **아발론 Phase 3** — Aggressive(0%)에서 LLM-Guided training
