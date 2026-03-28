---
name: shell-engineer
description: LxM Shell 전략 문서 생성·수정·최적화 스킬. Structured Markdown Shell 작성, 템플릿 관리, 파라미터 튜닝, Shell diff 분석. "Shell 만들어", "전략 수정해", "파라미터 조정해", "템플릿 추가해" 요청 시 반드시 사용.
---

# Shell Engineer Skill

## Shell 형식: Structured Markdown

```markdown
# {Game} Strategy: {Name} v{X.Y}

## Parameters
- param_name: value          ← 자동 파싱 가능, sweep 대상

## Strategy
전략 산문.                    ← LLM이 자연어로 이해

## Situational Rules
- 조건: 행동               ← 구체적 상황 대응
```

## 핵심 원칙

1. **Parametric Directness**: 파라미터가 행동에 직접 매핑되는가?
   - 높음: poker `pre_flop_threshold` → fold%, codenames `clue_number_max` → clue size
   - 낮음: avalon `trust_building_quests` → 복잡한 사회적 행동

2. **Shell can hurt**: 실행 불가능한 지시는 소음
   - inline mode에서 "파일을 써라" → 불가능 → 성능 하락
   - 에이전트가 실행 가능한 지시만 포함

3. **비용 최적화**: Score = f(win_rate) - g(cost)
   - 짧고 효과적 > 길고 비쌈

## 빌트인 템플릿

```python
from lxm.shell.manager import ShellManager
manager = ShellManager()
print(manager.list_templates())
# poker: tight_aggressive, loose_passive, bluff_heavy, memory_balanced
# avalon: memory_evil, deep_cover, aggressive_evil
# codenames: conservative, aggressive, balanced
```

## Shell 작업

### 생성
```python
shell = manager.create_shell("poker", template="tight_aggressive")
# 또는 커스텀
shell = ShellConfig.from_text(content)
```

### Diff
```python
diff = manager.diff(shell_a, shell_b)
print(diff.summary())
```

### 저장/버전
```python
manager.save(shell, agent_id="jj-sonnet", game="poker")
history = manager.get_history("jj-sonnet", "poker")
```

## Memory Shell (envelope 기반)
에이전트가 move envelope에 `"memory"` 필드를 포함하면 orchestrator가 저장→주입.
Shell에서 memory 프로토콜을 안내 (JSON 예시 포함).
