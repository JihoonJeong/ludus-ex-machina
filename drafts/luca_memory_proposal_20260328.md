# Luca — P1 세션 유지 결과 + Agent Memory 제안

## P1: CLI 세션 유지 — 결론: 비실용적

탐색한 방식:

1. **Claude `-c/--continue`**: 이전 대화를 이어가는 옵션. 테스트 결과 이전 턴 컨텍스트가 전부 누적됨 → 포커 30핸드면 "Prompt is too long" 에러. inline mode(매 턴 전체 상태 전송)와 근본적으로 충돌.

2. **`--resume {session_id}`**: 같은 누적 문제.

3. **Interactive mode stdin 파이프**: 프로세스를 한 번 띄우고 stdin/stdout으로 턴 교환. 핵심 난제: CLI가 응답을 언제 끝냈는지 알 수 없음 (구분자 없음). 불안정.

**포기 이유**: CLI는 "한 번 질문 → 한 번 답변" 설계. 수백 턴 반복 게임에 맞지 않음. Claude API의 prompt caching이 이미 동작 중이라 매 턴 새 프로세스여도 캐시 히트로 비용은 관리됨.

## 새로운 제안: Agent Memory System

P1을 포기하면서 JJ와 브레인스토밍한 대안. CLI 세션을 유지하는 대신, **에이전트에게 자기만의 메모리 파일을 관리하게 하는 방식.**

### 핵심 아이디어

```
현재 (Stateless):
  매 턴 → 전체 게임 상태 + recent_moves 히스토리 → 프롬프트에 포함
  턴이 길어질수록 프롬프트 비대해짐

제안 (Agent Memory):
  매 턴 → 현재 상태 + memory.md (에이전트가 직접 관리)
  에이전트가 매 턴 후 match_dir/memory.md에 자기 관점의 압축 기억을 기록
  다음 턴에 전체 히스토리 대신 memory.md를 참조
```

### 왜 이게 좋은가

1. **프롬프트 길이 일정**: 히스토리가 아무리 길어도 memory.md는 고정 크기
2. **전략적 메모리**: "상대 fold율 60%", "Hand 12에서 블러프 성공" 같은 메타 추론 기록 가능
3. **블랙박스 원칙 유지**: Orchestrator는 관여 안 함. 에이전트가 알아서 파일을 읽고 씀.
4. **Shell Engineering과 연결**: "memory를 어떻게 쓸지"가 Shell의 일부. memory Shell vs no-memory Shell 비교 가능.

### 구현 방식: Option 3 (에이전트 자율, 파일 시스템)

프로토콜 변경 없음. Shell에 memory 지시만 추가:

```markdown
## Memory Protocol
매 턴 시작 시 match_dir/memory.md를 읽어라.
매 턴 끝에 memory.md를 업데이트해라:
- 상대 행동 패턴 (fold율, 블러프 빈도)
- 내 전략 노트
- 현재 상황 요약
memory.md는 500자 이내로 유지 — 길면 오히려 해로움.
```

CLI 에이전트는 이미 match_dir에서 실행되니까 파일 읽기/쓰기가 자연스러움. Claude Code가 CLAUDE.md를 쓰듯, 게임 에이전트가 memory.md를 쓰는 것.

### 실험 설계

```
조건 A: Stateless (현재) — 전체 상태 + recent_moves
조건 B: Memory Shell — 현재 상태 + memory.md, recent_moves 유지
조건 C: Memory + 압축 — 현재 상태 + memory.md, recent_moves 축소 (3)
```

각 조건 5판, 포커 HU. 측정: 승률, 프롬프트 길이(토큰), 응답 시간, memory.md 품질.

### 게임별 예상 효과

| 게임 | Memory 이점 | 이유 |
|------|------------|------|
| **Poker** | 높음 | 상대 패턴 추적 → 적응적 플레이 |
| **Avalon** | 높음 | 투표 패턴, 의심 대상 기록 → 사회적 추론 |
| **Codenames** | 낮음 | 턴 독립적, 추가 메모리 불필요 |
| **Chess** | 낮음 | 보드 자체가 완전 상태 |

**턴이 긴 게임일수록 이점이 클 것.** 포커 30핸드, 아발론 5퀘스트 토론 — 이런 게임에서 에이전트가 "기억"을 갖는 것과 없는 것의 차이.

### 연구 가치

이건 LxM만의 질문이 아님:
- **"AI 에이전트에게 외부 메모리를 주면 장기 태스크를 더 잘 수행하는가?"**
- Claude Code의 CLAUDE.md, Cursor의 .cursorrules — 이미 개발 도구에서 쓰이는 패턴
- 게임에서 정량적으로 측정할 수 있다는 게 LxM의 장점
- **Shell Engineering의 확장** — Shell이 "어떻게 플레이할지"뿐 아니라 "무엇을 기억할지"도 결정

### 피드백 요청

1. 실험 설계 괜찮은지?
2. Option 3 (에이전트 자율 파일) 방식 동의?
3. memory.md 크기 제한을 Shell에서 관리 vs Orchestrator에서 강제?
4. 이걸 별도 논문 소재로 분리할 가치가 있는지?
