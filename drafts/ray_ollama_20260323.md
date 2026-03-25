# Ray — Ollama 개선 방향 논의

## 배경

현재 LxM의 Ollama 어댑터는 HTTP REST 방식 (`/api/generate`). Mac에서 로컬 모델 성능이 부족해서 Ollama cloud API (`OLLAMA_HOST` + `OLLAMA_API_KEY`)도 지원하게 만든 건데, 둘 다 불편한 점이 있었어.

Ray가 4070 Ti를 가지고 있으니까 로컬에서 제대로 돌릴 수 있는 환경이 있어. 그래서 Ollama 쪽 개선을 맡아주면 좋겠어.

## 현재 문제점 파악 요청

지금 Ollama 어댑터 (`lxm/adapters/ollama.py`) 쓸 때 어떤 점이 불편했는지 알려줘:

1. **응답 품질** — 모델이 JSON envelope 형식을 잘 못 따라가나? `[MOVE]...[/MOVE]` 태그 파싱 실패가 잦은지?
2. **속도** — 4070 Ti에서 어떤 모델이 실용적인 속도인지? (qwen3, llama3, mistral 등)
3. **연결/안정성** — 타임아웃, 에러, 연결 끊김?
4. **모델 제한** — `/no_think` 안 먹히는 모델(qwen3 등), context window 부족 등
5. **기타** — ollama Python 라이브러리(`import ollama`)로 전환하면 나아질 것 같은 점?

## 방향

### 단기: 문제점 정리 + 어떤 모델이 게임별로 쓸 만한지 테스트
- 4070 Ti에서 각 모델별 속도/품질 벤치마크
- 게임별 최소 동작 모델 확인 (틱택토는 작은 모델도 가능, 아발론은 큰 모델 필요할 것)
- JSON envelope 파싱 성공률

### 중기: 어댑터 개선
- HTTP REST 유지 vs Python 라이브러리 전환 — 장단점 정리해서 제안
- 프롬프트 최적화 — 작은 모델이 형식을 잘 따르게 하려면 프롬프트를 어떻게 바꿔야 하는지
- system prompt 활용 — Ollama는 system/user 분리를 잘 지원하니까

### 장기: LxM Client Registry 연동
- Client에 어댑터 플러그인 시스템이 들어가면, Ollama 어댑터가 첫 번째 "커스텀 어댑터" 사례
- `register_adapter("ollama-local", OllamaLocalAdapter)` 형태
- Windows Lab에서 LxM Client 돌려서 로컬 모델로 공식 매치 참여하는 것이 최종 목표

## 요청 사항

1. 위 문제점 파악부터 해줘 — 4070 Ti에서 직접 돌려보고
2. 게임 2-3개 (틱택토, 포커, 체스)에서 모델별 성공률/속도 간단히 테스트
3. 결과 정리해서 Discord에 공유 — Cody/Luca와 개선안 논의

급하지 않아. Client 구조가 잡히면 그때 본격적으로 합류하면 돼. 지금은 문제점 파악 + 환경 셋업 정도.
