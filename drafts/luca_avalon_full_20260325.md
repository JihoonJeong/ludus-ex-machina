# Luca — Avalon 3-Phase 완료 + 포커 대비 분석

## Avalon 전체 결과

### Phase 1: A/B Test (30판)
| Condition | Evil Win% |
|-----------|-----------|
| Deep Cover | 40% |
| no-shell | **80%** |
| Aggressive | 60% |
| Aggressive (vs Deep Cover) | 0% |

"Shell compliance ≠ winning" 아발론에서도 재현. no-shell이 가장 강함.

### Phase 2: Parameter Sweep — first_sabotage_quest (25판)
| Quest | Evil Win% |
|-------|-----------|
| Q1 | 60% |
| Q2 | 60% |
| Q3 | 60% |
| Q4 | 20% |
| Q5 | 40% |

포커와 다른 패턴: 역-U가 아닌 단조 감소. Q1-Q3 동일(60%), Q4-Q5 하락. 최적(60%)이 no-shell(80%)에 못 미침.

### Phase 3: LLM-Guided Training (25판 + LLM 4회)
| Gen | Version | Evil Win% | Note |
|-----|---------|-----------|------|
| 1 | v1.0 | 0% | LLM → v2.0 |
| 2 | v2.0 | 20% | LLM → v3.0 |
| 3 | v3.0 | 0% | LLM → v4.0 |
| 4 | v4.0 | **60%** | LLM → v5.0 |
| 5 | v5.0 | 40% | |

Aggressive(0%) → 60%로 개선. 하지만 비단조 (0→20→0→60→40). 포커처럼 깔끔하게 수렴하지 않음.

## 포커 vs 아발론 비교

| | Poker | Avalon |
|---|---|---|
| 기본 Shell | 20% | 0-60% |
| no-shell | 60% | **80%** |
| Sweep 최적 | **80%** | 60% |
| LLM-Guided 최고 | **80%** | 60% |
| **Shell > no-shell?** | **Yes** | **No** |
| SIBO Index | ~0.65 | ~0.58 |
| 핵심 파라미터 | pre_flop_threshold | first_sabotage_quest |
| 최적화 패턴 | 역-U 커브, 수렴 | 단조 감소, 불안정 |

## 해석

1. **포커는 Shell Engineering의 이상적 대상.** 파라미터 1개로 20%→80%, no-shell을 넘음. 행동 공간이 구조화되어 있고(fold/call/raise), 파라미터가 직접 행동에 매핑됨.

2. **아발론은 Shell 최적화가 어려움.** 다인수(5인), 역할 배정 랜덤, 사회적 추론이 핵심. Shell이 "구체적 행동 규칙"을 주면 오히려 유연성을 제한해서 약해짐. no-shell LLM이 상황 판단을 더 잘 함.

3. **SIBO Spectrum과 일치.** Shell 효과가 큰 게임(포커 0.65)에서 최적화도 잘 됨. Shell 효과가 중간인 게임(아발론 0.58)에서는 최적화 한계. 체스(SIBO 0.10)에서는 아예 시도할 가치 없을 것.

4. **LLM-Guided의 한계.** 포커: 핵심 파라미터를 정확히 찾음. 아발론: 불안정하게 진동. 복잡한 게임에서는 LLM이 올바른 수정 방향을 찾기 어려움.

5. **"Shell이 해를 끼칠 수 있다"는 중요한 발견.** Avalon Deep Cover(40%) < no-shell(80%). 잘못된 Shell은 안 쓰느니만 못함. 이건 프롬프트 엔지니어링 일반에 대한 경고.

## 논문 시사점

Shell Engineering 논문의 핵심 주장이 더 강해짐:
- "측정 없이 최적화 없다" — 두 게임에서 수치로 증명
- "게임마다 최적 접근이 다르다" — 포커=파라미터 튜닝, 아발론=Shell 제거가 최적
- "Shell이 해를 끼칠 수 있다" — 새로운 발견
- "SIBO가 최적화 가능성을 예측한다" — 프레임워크의 실용성

## 다음 단계 제안

1. **Codenames에서도 3-Phase?** SIBO ~0.35라 아발론보다 더 어려울 수 있지만 데이터 포인트 추가.
2. **논문 figure 생성** — 포커 역-U 커브, 아발론 단조 감소, SIBO vs 최적화 성공률 상관관계.
3. **rule_bot 강화** — 현재 너무 약해서 LLM 대체 불가. hard 모드 개선 또는 imitation 모드.
