# Luca — Agent Memory v2 (Envelope-based) 결과

## 기술적 성공: 메모리 시스템 작동 확인

Envelope `memory` 필드 방식으로 전환 후 **10/10 매치에서 memory 파일 생성.** v1(파일 방식)은 0/10이었으니 완전히 해결.

## 메모리 품질: 놀랍도록 좋음

에이전트가 쓴 실제 메모리 예시:

> "Opponent TAG: raised 9x (h5), bet 120 post-flop. Opponent is aggressive post-flop, do not chase weak draws vs bets."

> "Bluffs rarely. Calls post-flop with weak hands. Short-stacked (140). No bluffing vs calling station short stack with air."

> "Opp passive all streets. Top pair 8s → value shoved all-in. Watch if opp calls/folds to calibrate aggression."

상대 프로파일링, pot odds 분석, 적응적 전략 수정 — 프로 포커 플레이어의 노트와 유사한 수준.

## 승률 결과: 개선 없음

| Condition | Win% | Avg Time |
|-----------|------|----------|
| A: Stateless (rm=20) | 40% | 797s |
| B: Memory + rm=20 | 20% | 1215s |
| C: Memory + rm=3 | 40% | 1368s |

v1과 비교:

| Condition | v1 (memory 미작동) | v2 (memory 작동) |
|-----------|-------------------|-----------------|
| A: Stateless | 60% | 40% |
| B: Memory + rm=20 | 40% | 20% |
| C: Memory + rm=3 | 100% | 40% |

## 해석

### 1. 메모리 시스템은 작동하지만 승률을 올리지 못함
- 에이전트가 유용한 정보를 기록하고 있음 (품질 높음)
- 그 정보를 실제 의사결정에 반영하는 데는 실패하고 있는 것 같음
- "관찰은 잘 하지만 적용을 못 함" — 이건 LLM의 일반적 특성일 수 있음

### 2. 메모리가 프롬프트를 비대화
- B(1215s) vs A(797s) — 메모리 + Shell 지시가 응답 시간 52% 증가
- 메모리의 이점이 비용을 상쇄하지 못함

### 3. 표본 크기 문제
- 5판은 분산이 너무 큼 (v1 C가 100%, v2 A가 40%)
- 통계적 유의성 없음 — 10판 이상 필요

### 4. 가능한 문제: 메모리 활용 vs 메모리 작성
- 에이전트가 메모리를 **쓰는 것**에는 성공
- 다음 턴에서 `[YOUR MEMORY]`를 **읽고 활용하는 것**이 문제일 수 있음
- 프롬프트에 [STRATEGY] + [YOUR MEMORY] + 게임 상태가 다 있으면, 어디에 집중할지 모호해질 수 있음

## 제안

### 단기: 표본 늘리기
- 같은 3조건을 10판씩 (총 30판) 돌려서 분산 줄이기
- 현재 5판은 noise가 signal보다 클 수 있음

### 중기: 메모리 활용 강화
- Shell에 "이전 메모리의 관찰을 바탕으로 이번 턴 전략을 조정해라"를 더 명시적으로
- 또는 메모리 형식을 구조화: `## Opponent Profile` + `## My Adjustments` → 에이전트가 Adjustments 섹션을 직접 실행 가능한 형태로

### 장기: 게임별 비교
- 포커에서 안 됐어도 아발론에서는 될 수 있음 (투표 패턴 추적이 더 직접적)
- "어떤 게임에서 agent memory가 유용한가"가 연구 질문

## 결론

**기술적으로 성공, 실용적으로는 미검증.** Envelope 기반 메모리 시스템은 잘 동작하고 에이전트가 고품질 메모리를 작성하지만, 승률 개선으로 이어지는지는 더 큰 표본으로 확인 필요. 메모리 품질이 높다는 것 자체가 긍정적 신호 — 활용 방법을 개선하면 효과가 나올 가능성 있음.
