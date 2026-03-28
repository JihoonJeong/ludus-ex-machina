---
name: match-analyzer
description: LxM 매치 데이터 분석 스킬. 매치 결과 분석, 행동 지표 추출(fold%/raise%/clue number), Delta 리포트 생성, 크로스게임 비교. "결과 분석해", "데이터 정리해", "비교해", "리포트 만들어" 요청 시 반드시 사용.
---

# Match Analyzer Skill

## 데이터 소스

```
matches/{match_id}/
  ├── match_config.json    — 에이전트, 게임, 설정
  ├── log.json             — 턴별 상세 (envelope, validation, state)
  ├── result.json          — 결과 (outcome, winner, scores)
  ├── state.json           — 최종 게임 상태
  ├── errors.json          — 에러 로그 (있는 경우)
  └── memory_*.md          — 에이전트 메모리 (있는 경우)
```

## 행동 지표 추출

```python
from lxm.shell.tester import extract_poker_behavior, extract_codenames_behavior, aggregate_behavior

# 포커: fold%, raise%, call%, check%, all_in%
beh = extract_poker_behavior("match_id", "agent_id", "matches")

# 코드네임: avg_clue_number, clue_1/2/3/4+
beh = extract_codenames_behavior("match_id", "agent_id", "matches")

# 여러 매치 집계
agg = aggregate_behavior([beh1, beh2, beh3])
```

## 분석 패턴

### 승률 비교
```python
wins = sum(1 for r in results if r.winner == agent_id)
win_rate = wins / len(results)
```

### Delta 추출 (A/B 비교)
```python
from lxm.shell.tester import ShellTester
tester = ShellTester()
# ab_test가 자동으로 Delta 계산
result = tester.ab_test(shell_a, shell_b, ...)
print(result.delta.summary())
```

### ELO 리더보드
```python
from lxm.elo import build_leaderboard
lb = build_leaderboard("matches")
```

## 리포트 형식

### JSON (기계 읽기)
```python
tester.save_report(result, "reports/{name}.json")
```

### Markdown (사람 읽기)
`reports/shell_engineering_{game}_summary.md` 형식:
- Overview 테이블
- Phase별 결과
- Key Findings
- Data Files 목록

### Cross-Game 비교
`reports/shell_engineering_cross_game_comparison.md`:
- SIBO vs 최적화 성공률
- Parameter Directness 분석
- 게임별 패턴 비교
