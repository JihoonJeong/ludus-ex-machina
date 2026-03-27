# P1: Session Persistence Exploration

## 결론: 현재 CLI로는 실용적이지 않음

### Claude CLI
- `-c/--continue`: 이전 대화 이어가기 가능하지만, **이전 턴의 전체 컨텍스트가 누적**됨
  - 포커 30핸드 = 수백 턴 → 컨텍스트 폭발 → "Prompt is too long"
  - 게임마다 전체 상태를 보내는 inline mode와 충돌
- `--resume {session_id}`: 특정 세션 재개, 같은 문제
- `--no-session-persistence`: 세션 저장 안 함 (현재 사용 중)
- **stdin + `-p`**: 매 턴 새 프로세스 + stdin으로 프롬프트 전달은 동작하지만 세션 유지는 아님

### Gemini CLI
- stdin 파이프: `echo prompt | gemini -o text` 동작 확인 (Ray)
- interactive mode 파이프: 미조사 — Claude와 같은 문제 예상

### 대안 검토

1. **API 직접 호출** — subprocess 대신 HTTP API. 가장 빠르지만 "CLI 에이전트가 폴더에 들어와서 게임" 철학에 반함.
2. **프로세스 풀** — N개 CLI 프로세스를 미리 띄워두고 재활용. interactive mode stdin/stdout 파이프. 응답 경계(EOF) 구분이 핵심 난제.
3. **캐시 활용** — Claude의 prompt caching이 이미 동작 중 (cache_read_input_tokens 확인). 매 턴 새 프로세스여도 API 레벨에서 캐시 히트하면 비용/속도 이점.

### 권장: 현재 방식 유지 + 캐시 의존

CLI는 매 턴 새 프로세스로 유지. 이유:
- Claude API의 prompt caching이 이미 동작 (로그에서 cache_read 확인)
- 세션 유지의 이점(속도)보다 안정성(독립 프로세스)이 더 중요
- PersistentCLIAdapter는 응답 경계 파싱이 불안정할 수 있음
- 속도가 정말 문제면 P1보다 API adapter(LLM SDK 직접 호출)가 더 현실적

### 미래: API Adapter (Phase C 이후)
```python
class AnthropicAPIAdapter(AgentAdapter):
    """Direct API call, no CLI subprocess."""
    def invoke(self, match_dir, prompt):
        response = self._client.messages.create(model=self._model, messages=[...])
        return {"stdout": response.content[0].text, ...}
```
이건 CLI 철학과 별개로, 성능이 정말 필요할 때의 옵션.
