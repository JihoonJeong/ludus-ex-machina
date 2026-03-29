# Luca — Deduction Game 구현 + 첫 테스트 결과 (수정)

## ⚠️ 이전 보고서 오류 수정

mystery_003에서 "범인 틀림 (C를 제출, 정답 B)"라고 보고했는데, **정답이 C가 맞았음.** Sonnet이 3개 시나리오 전부 범인을 맞춤.

## 구현 완료

- `games/deduction/engine.py` — DeductionGame (LxMGame 상속)
- READ/NOTE/SUBMIT 3가지 move type, inline prompt builder
- 점수: accuracy(0-3) × (1 + efficiency × 0.5)
- `viewer/static/renderers/deduction.js` — Viewer 렌더러 추가
- `mystery_001_ko` — 한글 시나리오 (번역 완료, 테스트 중)
- 레지스트리 등록 (7 games), 286 테스트 통과

## Sonnet 결과 (수정)

| 시나리오 | 난이도 | 범인 | 동기 | 수단 | 파일 읽음 | 점수 |
|---------|--------|------|------|------|----------|------|
| mystery_001 | Easy | ✅ B | 0.5 | 0.5 | 0/12 | 3.0 |
| mystery_002 | Medium | ✅ B | 0.5 | 0.5 | 4/11 | 2.64 |
| mystery_003 | Hard | ✅ C | 0 | 0 | 5/14 | 1.32 |

**3/3 범인 전부 정답.** Sonnet이 추리를 매우 잘함.

## 해석 (수정)

### 1. Sonnet은 추리 능력이 높다
3개 난이도 모두 범인 정답. Hard(가평 펜션 익사 위장)에서도 5개 파일만 읽고 범인(C, 서유나 약사)을 정확히 지목. 복수극의 동기까지 "숨겨진 개인적 원한"으로 파악 — 정확하지만 키워드가 다름.

### 2. 점수가 낮은 이유: 채점 로직 한계
Hard에서 1.32점인 이유:
- 동기: Sonnet이 쓴 "premeditated killing with concealed personal grievance" vs 정답 "revenge" → 의미는 같지만 단어 교집합 없음 → 0점
- 수단: "midazolam dissolved in whisky → drowning" vs "sedative_drowning" → 같은 내용이지만 키워드 불일치 → 0점

**엔진 문제, 에이전트 문제 아님.** `_score_text_match()`가 단순 단어 교집합만 체크.

### 3. 채점 개선 필요
옵션:
- **A: 선택지 제공** — scenario.json에 motive_options/method_options 추가, 에이전트가 선택
- **B: 동의어 사전** — "revenge" = ["revenge", "vengeance", "retaliation", "grievance"]
- **C: Semantic matching** — LLM에게 "이 두 답이 같은 의미인가" 판단 요청 (비쌈)

권장: **A + B 조합.** 선택지 제공하되, 자유 서술도 허용하고 동의어로 매칭.

### 4. Easy가 너무 쉬움
파일 0개 읽고 바로 정답. case_brief의 힌트가 너무 많거나, 시나리오 자체가 단순.
- case_brief에서 범인 단서 제거
- 또는 Easy라도 최소 2개 파일은 읽어야 풀리게

### 5. 탐색 전략이 인상적
Medium에서 forensic → cctv → alibi → phone 순서 — 연역적 추론. Hard에서도 toxicology → alibi → autopsy 순서로 물증부터 확인.

## 한글 시나리오 (진행중)

mystery_001_ko 번역 완료. 테스트 진행 중. 결과 나오면 영어 vs 한글 비교:
- 같은 시나리오, 같은 모델 — 언어만 다름
- 정확도, 탐색 순서, 추론 품질 차이

## 다음 단계

1. **채점 개선** — 선택지 + 동의어 사전
2. **한글 비교** — mystery_001 EN vs KO
3. **Cross-model** — Haiku, Opus 비교
4. **Shell Engineering** — Deductive vs Inductive vs Efficient Shell
