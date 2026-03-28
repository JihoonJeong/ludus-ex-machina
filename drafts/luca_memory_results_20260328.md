# Luca — Agent Memory 실험 결과

## 결과

| Condition | Win% | Avg Time | fold% | raise% |
|-----------|------|----------|-------|--------|
| A: Stateless (rm=20) | 60% | 1148s | 28% | 15% |
| B: Memory Shell + rm=20 | 40% | 784s | 34% | 22% |
| C: Memory Shell + rm=3 | **100%** | 1322s | 35% | 19% |

## 핵심 발견: memory.md가 생성되지 않았음

**에이전트가 memory.md 파일을 쓰지 않았다.** 15판 전부에서 memory 파일 없음.

원인: inline mode에서는 에이전트가 프롬프트를 받고 stdout으로 JSON envelope만 리턴. **파일 시스템에 접근하지 않음.** Shell에서 "memory.md를 써라"고 지시해도 inline mode의 구조적 한계로 실행 불가.

따라서 B/C 조건은 **실제 메모리 활용이 아닌, Memory Shell 텍스트 자체의 전략 효과만 측정한 것.**

## C가 100% 승률인 이유

memory.md를 안 썼으니, C의 실제 구성은:
- Memory Balanced Shell (pre_flop_threshold: top 30% — Sweep 최적값과 동일!)
- recent_moves=3 (히스토리 축소 → 프롬프트 짧아짐)

이건 사실상 Phase 2 Sweep에서 찾은 최적 Shell + 짧은 프롬프트의 조합. memory 덕이 아니라 **Shell 전략 + 프롬프트 경량화**의 효과.

## B가 A보다 약한 이유 (40% < 60%)

Memory Shell 텍스트가 프롬프트에 추가됐지만 실제 memory는 없으니, "파일을 읽고 써라"라는 **실행 불가능한 지시가 소음이 됨.** recent_moves=20으로 히스토리도 그대로 → 프롬프트만 길어짐. "Shell can hurt"의 또 다른 사례.

## 숙제: Inline Mode에서 Stateful Memory를 어떻게?

Option 3 (에이전트 자율 파일)은 inline mode에서 작동 안 함. 대안:

### Option A: Envelope 확장
```json
{
  "move": {"type": "poker_action", "action": "raise"},
  "memory": "상대 fold율 높음. 블러프 빈도 올릴 것."
}
```
- Orchestrator가 `memory` 필드를 저장하고 다음 턴 프롬프트에 `[MEMORY]`로 주입
- 에이전트 입장에서는 응답에 memory를 포함하기만 하면 됨
- 추가 호출 없음 (1-step)
- **블랙박스가 약간 깨짐** — Orchestrator가 memory를 중개

### Option B: File Mode 전용
- memory 실험은 file mode(discovery)로 실행
- 에이전트가 실제로 match_dir에서 파일을 읽고 씀
- 느리지만 "진짜" agent memory
- **블랙박스 100% 유지**

### Option C: 하이브리드 (2-step turn)
- Move 턴: inline mode (빠름)
- Memory 턴: file mode로 "memory.md를 업데이트해" (느림)
- 턴당 2회 호출
- **블랙박스 유지 + inline 속도 일부 유지**

### Option D: Orchestrator 자동 구성
- 에이전트 응답의 `meta.reasoning`을 파싱
- Orchestrator가 자동으로 "상대 패턴 요약"을 구성해서 다음 프롬프트에 주입
- **에이전트가 memory를 의식할 필요 없음**
- 블랙박스 유지, 하지만 Orchestrator가 똑똑해야 함

## 권장

**Option A (Envelope 확장)가 가장 현실적.** 이유:
- 추가 호출 없음 (비용/속도 동일)
- 프로토콜 변경 최소 (envelope에 optional `memory` 필드 추가)
- 에이전트가 memory를 "쓸지 말지" 자율 결정 (안 쓰면 필드 없음)
- Shell이 "memory 필드에 상대 패턴을 기록해"라고 지시

블랙박스가 100%는 아니지만, Orchestrator는 memory를 읽지 않고 그냥 저장→주입만 하니까 "우편함" 역할. 에이전트가 뭘 쓰든 간섭 없음.

## 피드백 요청

1. Option A~D 중 어느 방향?
2. Envelope 확장이면 프로토콜 버전을 lxm-v0.3으로 올려야 하나?
3. 이 실험 자체를 논문에 포함할 가치가 있는지? ("inline mode의 구조적 한계로 agent memory 불가" → "envelope 확장으로 해결")
