---
name: experiment-runner
description: LxM 게임 실험 실행 스킬. Shell A/B 테스트, parameter sweep, LLM-guided training, 메모리 실험, cross-company 매치 등 모든 게임 실험을 설계·실행·모니터링. "실험 돌려", "Shell 테스트", "매치 실행", "sweep 해", "training 시작" 요청 시 반드시 사용.
---

# Experiment Runner Skill

## 실험 유형별 실행 방법

### 1. Shell A/B 테스트
```python
from lxm.shell.manager import ShellManager
from lxm.shell.tester import ShellTester

manager = ShellManager()
tester = ShellTester(opponent_adapter="claude", opponent_model="sonnet")

shell_a = manager.create_shell("poker", template="tight_aggressive")
result = tester.ab_test(shell_a=shell_a, shell_b=None, game="poker", n_games=5,
                        agent_id="test", adapter="claude", model="sonnet")
tester.save_report(result, "reports/test.json")
```

### 2. Parameter Sweep
```python
result = tester.parameter_sweep(
    shell=shell, param_name="pre_flop_threshold",
    values=["top 10%", "top 20%", "top 30%"], game="poker", n_games=5)
```

### 3. LLM-Guided Training
```python
from lxm.shell.trainer import ShellTrainer
trainer = ShellTrainer()
result = trainer.train(shell=shell, game="poker", strategy="llm_guided",
                       generations=5, games_per_gen=5)
```

### 4. 일반 매치
```bash
python scripts/run_match.py --game poker \
  --agents a b --adapter claude --model sonnet \
  --invocation-mode inline --discovery-turns 0 --no-shell --skip-eval
```

### 5. 멀티플레이어 (Avalon)
role_shells로 Evil에게만 Shell 적용:
```python
config = MatchConfig(game="avalon", agents=agents,
    role_shells={"evil": shell_content}, ...)
```

## 모니터링
```bash
# 진행 확인
ls -lt matches/ | grep {pattern} | head -10
# 프로세스 확인
ps aux | grep run_match | grep -v grep
```

## 실험 설계 체크리스트
- [ ] 조건 정의 (A vs B, 변수 1개만)
- [ ] 판 수 결정 (최소 5판, 통계적이면 10판+)
- [ ] 상대 고정 (no-shell Sonnet이 기본)
- [ ] 측정 지표 정의 (승률, 행동 Delta, 비용)
- [ ] 리포트 경로 지정 (`reports/`)
