# Luca 세션 핸드오프 — 2026-03-29

## 이번 세션에서 완료한 것

### 1. Deduction Game 시나리오 완성
- mystery_002 (Medium) — 나머지 6개 파일 완성: witness_cleaner, cctv_log, alibi_A/B/C, newspaper_clipping
- mystery_003 (Hard) "The Double Alibi" — 전체 신규 작성 (14 evidence files)
  - 가평 펜션 동창 모임, 익사 위장 살인, 범인=C(서유나, 약사), 동기=복수(20년 전 음주운전 남동생 사망), 수단=미다졸람+익사
- 3개 시나리오 전부 완성 (Easy/Medium/Hard)

### 2. Deduction 엔진 구현 + 테스트 (Cody)
- DeductionGame 엔진 구현 완료 (7번째 게임)
- Sonnet 첫 테스트: 3/3 범인 정답 (mystery_003 정답 체크 버그 발견 → 수정)
- 채점 로직 한계 발견 → 선택지(motive_options/method_options) 방식으로 전환
- 한글 시나리오(mystery_001_ko) 번역 + 테스트 완료
- 한글 vs 영어 비교: **한글에서 7배 더 많이 탐색** (언어가 에이전트 확신 수준에 영향 = Hardware Shell 효과)
- Cross-model 테스트: **Opus 3/3, Sonnet 1/3, Haiku 1/3** → LxM 최초로 모델 크기가 결정적인 게임
- Solo Mode 웹 UI 구현 완료 (docs/deduction/, Viewer와 분리)
- Race Mode 구현 완료

### 3. Deduction 스펙 v0.2
- Section 8: Human Participation Modes (Solo → Race → Coach → Suspects)
- Section 9: Creator Ecosystem (시나리오 제작 경쟁, 품질 측정, UGC)
- Deduction을 LxM의 "킬러 컨텐츠"로 포지셔닝 — 장르를 여는 게임

### 4. Cross-Tier 포커 결과 (Ray)
- exaone 5-5 Haiku, 7-3 Flash. Flash 6-4 Haiku.
- **종합: exaone ≥ Haiku > Flash.** Cloud-SLM 벽이 포커에서는 없음.
- 연구 노트에 기록 완료.

### 5. Codenames SLM 결과 (Ray)
- SLM은 Codenames를 거의 못 함. 정상 완료 3% (1/29), Assassin 52%, 타임아웃 54%.
- 서열: mistral > exaone > llama ≈ qwen3 (포커와 다른 서열)
- **Cloud-SLM 벽은 능력 축에 따라 다름:** 구조적 추론(포커)=없음, 언어 연상(Codenames)=절대적, 논리 추론(Deduction)=있음
- Cross-Tier Codenames 실험 취소 (비교 무의미)

### 6. Project Instruction 업데이트
- Shell Engineering 분리 계획 명시
- Paper #3 Deferred로 변경
- Deduction Game, Cross-Tier 결과 반영
- 디스크 PROJECT_INSTRUCTIONS.md + Claude 프로젝트 설정 모두 업데이트

### 7. Shell Engineering 프레임워크 v0.2
- Memento-Skills (arXiv:2603.18743) 분석 추가
- Shell Engineering과의 매핑, 차별화 포인트, 공통 원칙 기록
- LxM 통합 계획 (방법 1: 에이전트 투입, 방법 2: Shell Trainer 통합) — Phase C 이후 진행

### 8. 연구 노트 v0.4
- Section 6: Language Effect on Agent Behavior (한글 vs 영어)
- Section 7: Deduction Game First Results (Opus 3/3)
- Section 8: SLM Codenames (Cloud-SLM wall is ability-dependent)
- Platform Status 업데이트

---

## 현재 팀 상태

### Cody (Mac Lab)
- ✅ Deduction 엔진 + Solo Mode + Race Mode 완료
- ✅ 선택지 채점 완료
- ✅ Cross-model 테스트 완료
- ✅ Render 웹서버 세팅 + 동작 확인 (Free tier)
- 🔄 **현재 작업: Phase C (서버)**
  - P0 (기본 인프라): GitHub OAuth, 유저/에이전트 등록, 매치 결과 저장, 리더보드 API
  - P1 (게임 실행): BYOK API 모드, CLI 모드, 리플레이 서빙
  - P2: Creator 제출 포맷, Race 리더보드, pip install lxm
- **핵심 설계 원칙: BYOK** — AI 비용은 사용자 부담, 서버는 매칭/리더보드/결과만

### Ray (Windows Lab)
- ✅ Cross-Tier 포커 완료 (exaone ≥ Haiku > Flash)
- ✅ Codenames SLM 완료 (SLM은 Codenames 거의 불가)
- ⏸️ **대기 중** — Deduction Cloud 결과 정리 후 SLM Deduction 테스트 예정

### MM Luca (별도 프로젝트)
- Paper #2 submitted
- MTI 디자인 진행 중

---

## 다음 세션에서 할 것

### 우선순위
1. **Phase C 진행 상황 확인** (Cody)
2. **Deduction 추가 작업 논의** — 한글 002/003 번역, 신규 시나리오, Creator 포맷
3. **Ray SLM Deduction 실험 시점 결정** — Cloud 데이터 충분하면 시작

### 보류 중
- Memento-Skills 통합 — Phase C 이후
- Shell Engineering 독립 프로젝트 분리 — 비게임 도메인 검증 필요
- Paper #3 — 시기상조
- Sonnet Deduction 복수 실행 (분산 확인) — 우선순위 낮음

---

## 핵심 발견 (이번 세션)

1. **추리는 모델 크기가 중요한 첫 LxM 게임** — Opus 3/3, Sonnet=Haiku 1/3
2. **언어가 에이전트 탐색 행동에 영향** — 한글에서 7배 더 많이 탐색 (Hardware Shell 효과)
3. **Cloud-SLM 벽은 능력 축에 따라 다름** — 포커=없음, Codenames=절대적, Deduction=있음
4. **4개 게임 4개 다른 서열** — 만능 모델 없음, Cross-Game 프로필 필요
5. **Deduction = LxM 킬러 콘텐츠** — Human Participation + Creator Ecosystem으로 장르 개척
6. **Memento-Skills가 Shell Engineering과 동일 패러다임** — 독립적 확인, 통합 계획 수립

---

## 주요 파일 변경

| 파일 | 변경 |
|------|------|
| PROJECT_INSTRUCTIONS.md | v2026-03-29 전면 업데이트 |
| LXM_DEDUCTION_SPEC_v0.1.md | v0.2로 (Section 8, 9 추가) |
| LXM_SHELL_ENGINEERING_FRAMEWORK_v0.1.md | v0.2로 (Memento-Skills 분석) |
| LXM_RESEARCH_NOTES_PUBLIC_HEALTH.md | v0.4로 (Section 6, 7, 8 추가) |
| games/deduction/scenarios/mystery_002/ | 6개 evidence 파일 추가 (완성) |
| games/deduction/scenarios/mystery_003/ | 전체 신규 (scenario.json + case_brief + 14 evidence) |
