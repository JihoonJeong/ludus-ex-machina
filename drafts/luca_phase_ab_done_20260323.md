# Luca — Phase A/B/B2 구현 완료

## 완료된 것

Shell Engineering Framework 스펙 기반으로 Phase A ~ B2 전부 구현했어.

### Phase A: Config + Registry
- `lxm/config.py` — MatchConfig, AgentConfig, **ShellConfig** dataclass
  - ShellConfig: Structured Markdown 파서 (Parameters/Strategy/Rules 섹션 분리)
  - `from_cli_args()` — 기존 run_match.py 100% 호환
  - `from_dict()` — 서버 JSON 수신용 (Phase C 준비)
- `lxm/adapters/registry.py` — 4 adapters + 6 games 플러그인 레지스트리
  - `register_adapter("my_runtime", MyAdapter)` — 커스텀 어댑터 등록 가능

### Phase B: Client + Shell Manager + Shell Tester
- `lxm/client.py` — LxMClient
  - `prepare()` → `run()` → `submit_result()` 라이프사이클
  - 서버 모드 스텁: `connect()`, `wait_for_match()`
- `lxm/shell/manager.py` — ShellManager
  - `create_shell(game, template)` — 빌트인 템플릿 5개 (poker 3, avalon 2)
  - `save()` / `load()` — 에이전트별 버전 관리
  - `diff(shell_a, shell_b)` — 파라미터/전략/규칙 차이 추출
  - `get_history()` — 버전 이력
- `lxm/shell/tester.py` — ShellTester
  - `ab_test(shell_a, shell_b, game, n_games)` — A/B 테스트 + Delta 추출
  - `parameter_sweep(shell, param, values, game, n_games)` — 그리드 서치
  - Delta: 승률 변화 + 행동 변화 + 비용 변화

### Phase B2: Shell Trainer
- `lxm/shell/trainer.py` — ShellTrainer
  - `train(strategy="parameter_sweep")` — 좌표 하강법, 파라미터 하나씩 최적화
  - `train(strategy="llm_guided")` — 패배 로그 분석 → LLM에게 수정 요청 → 반복
  - `analyze_losses()` — 패배 패턴 추출
  - `suggest_modification()` — LLM 호출로 Shell 개선안 생성
  - 자동 버전 범핑, 수렴 감지, 스윕 값 자동 생성

### 기존 코드 영향: 없음
- run_match.py 변경 없음
- orchestrator.py 변경 없음
- 286 테스트 전부 통과

## 다음: 테스트

코드는 있는데 **실제로 돌려본 건 유닛 레벨뿐**이야. 실전 테스트가 필요해:

### 1순위: ShellTester A/B 테스트
```bash
# 포커: TAG vs Bluff-Heavy
lxm shell test poker --shell-a shells/poker/tight_aggressive.md --shell-b shells/poker/bluff_heavy.md --games 5
```
- 빌트인 템플릿끼리 먼저 붙여보기
- Delta 리포트가 제대로 나오는지 확인
- 예상: TAG가 Bluff-Heavy를 이길 것 (이전 SIBO 데이터 기반)

### 2순위: Parameter Sweep
```bash
# 포커: bluff_frequency 스윕
lxm shell sweep poker --shell tight_ag.md --param bluff_frequency --range "1/10,1/5,1/3" --games 3
```
- 파라미터 파싱이 실전에서 동작하는지
- 최적값 찾기가 되는지

### 3순위: LLM-Guided Training
```bash
# 포커: 5세대 자동 진화
lxm shell train poker --agent test-sonnet --strategy llm_guided --generations 5 --games 3
```
- LLM이 패배 분석 후 Shell을 실제로 개선하는지
- 수렴하는지
- 이게 제일 중요하면서 제일 비쌈 (세대당 LLM 호출 + 매치 실행)

### 테스트 순서 의견

포커부터 시작하는 게 좋겠어:
- 2인이라 빠름
- SIBO 데이터가 이미 있어서 기대값 비교 가능
- 파라미터가 명확 (fold%, bluff%, raise%)

그 다음 아발론:
- Shell 효과가 가장 극적 (0-100% 스윙)
- 5인이라 느리지만 재밌는 데이터

**어떤 순서/범위로 테스트할지 의견 줘. CLI 아직 안 만들어서 Python 코드로 직접 호출하는 방식으로 테스트할 예정.**
