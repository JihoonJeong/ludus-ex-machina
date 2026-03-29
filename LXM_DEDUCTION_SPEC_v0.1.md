# LxM Deduction Game Spec v0.1

## Purpose

Add **Deduction** (AI 추리 게임) as 여섯 번째 LxM 게임. "정보 수집 + 논리 추론" 카테고리를 열고, **LxM 최초의 CLI-native 게임** — 에이전트가 폴더를 탐색하며 단서 파일을 읽고, 메모를 쓰고, 추론하는 진짜 agentic 행동.

**Hand this to Cody and say "build this."**

**Prerequisites:**
- Avalon architecture working (N-player, custom turn order, role-based state)
- Effort estimate: 1-2 weeks

---

## 1. 핵심 컨셉

범죄가 발생했다. 에이전트는 **탐정**이 되어 match_dir에 배치된 단서 파일을 탐색하고, **범인(Who)**, **동기(Why)**, **수단(How)**을 추론해서 제출한다.

### 왜 이 게임인가

| 기존 5게임의 한계 | Deduction이 해결하는 것 |
|---|---|
| 전부 "프롬프트 받고 JSON 반환" | 에이전트가 **폴더를 직접 탐색** |
| CLI의 파일 능력 미활용 | **파일 읽기/쓰기가 게임의 핵심** |
| 정보 수집 능력 미측정 | **어떤 단서를 선택적으로 읽는가** |
| 논리 추론 능력 미측정 | **여러 단서를 조합해서 결론 도출** |
| Agent Memory 효과 미검증 | **단서가 많아지면 메모리 필요** |

---

## 2. 게임 규칙

### 2.1 기본 구조

```
시나리오 = 1건의 사건
사건 = 범인(1명) + 동기(1개) + 수단(1개)
용의자 = 3-5명 (난이도에 따라)
단서 파일 = 8-15개 (난이도에 따라)
미스디렉션 = 1-3개의 거짓/무관 단서
```

### 2.2 에이전트 행동 (File Mode)

에이전트는 match_dir에서 자유롭게 활동:

```
가능한 행동:
  1. READ   — evidence/ 내 파일 읽기
  2. NOTE   — agent_notes.md에 추론 메모 작성/수정
  3. SUBMIT — 최종 답변 제출 (범인/동기/수단)
```

**File mode에서는 에이전트가 직접 파일을 읽고 씀.** Orchestrator는 에이전트를 match_dir에서 호출하고, 에이전트가 자율적으로 탐색.

### 2.3 에이전트 행동 (Inline Mode)

inline mode에서는 Orchestrator가 턴마다 프롬프트를 구성:

```
Turn 1: case_brief.md + evidence 목록 제시 → 에이전트가 읽을 파일 선택
Turn 2: 선택한 파일 내용 제시 → 에이전트가 다음 행동 선택 (더 읽기 / 제출)
...
Turn N: 에이전트가 최종 답변 제출
```

### 2.4 승패 판정

```
정확도 점수 (0-3점):
  범인 맞춤: +1
  동기 맞춤: +1
  수단 맞춤: +1

효율성 보너스:
  읽은 파일 수 / 전체 파일 수 비율로 보너스
  적은 단서로 맞출수록 높은 점수
  예: 15개 중 5개만 읽고 3/3 맞춤 → 최고 효율

최종 점수 = 정확도 × (1 + 효율성 보너스)
```

### 2.5 게임 모드

```
Mode A: Solo (기본)
  - 에이전트 1명이 사건 해결
  - 정확도 + 효율성으로 점수 산정
  - Cross-model 비교: "어떤 모델이 더 잘 푸는가"

Mode B: Race (대결)
  - 2명이 같은 사건을 동시에 풀기
  - 먼저 정확하게 제출한 쪽이 승
  - 오답 제출 시 페널티 (1턴 대기)

Mode C: Asymmetric (범인 vs 탐정) — v2
  - 1명이 범인 역할 (알리바이 파일을 작성/수정)
  - 다른 1명이 탐정 역할 (탐색 + 추론)
  - Avalon과 비슷한 비대칭 구조
```

**v1: Mode A (Solo) + Mode B (Race). Mode C는 나중에.**

---

## 3. 시나리오 구조

### 3.1 폴더 레이아웃

```
scenarios/mystery_001/
├── scenario.json              ← 시나리오 메타데이터 + 정답
├── case_brief.md              ← 사건 개요 (에이전트에게 공개)
├── evidence/
│   ├── witness_kim.md          ← 증인 김씨 진술
│   ├── witness_park.md         ← 증인 박씨 진술
│   ├── witness_lee.md          ← 증인 이씨 진술
│   ├── cctv_log.md             ← CCTV 기록
│   ├── phone_records.md        ← 통화 내역
│   ├── forensic_report.md      ← 감식 보고서
│   ├── financial_records.md    ← 재무 기록
│   ├── alibi_suspect_A.md      ← 용의자 A 알리바이
│   ├── alibi_suspect_B.md      ← 용의자 B 알리바이
│   ├── alibi_suspect_C.md      ← 용의자 C 알리바이
│   └── newspaper_clipping.md   ← 관련 신문 기사 (미스디렉션 가능)
└── answer_key.json             ← 정답 (엔진만 참조, 에이전트 비공개)
```

### 3.2 scenario.json

```json
{
  "scenario_id": "mystery_001",
  "title": "The Silent Partner",
  "difficulty": "medium",
  "suspects": ["A", "B", "C"],
  "evidence_files": [
    "witness_kim.md", "witness_park.md", "witness_lee.md",
    "cctv_log.md", "phone_records.md", "forensic_report.md",
    "financial_records.md", "alibi_suspect_A.md",
    "alibi_suspect_B.md", "alibi_suspect_C.md",
    "newspaper_clipping.md"
  ],
  "red_herrings": ["newspaper_clipping.md"],
  "critical_evidence": ["forensic_report.md", "phone_records.md", "alibi_suspect_B.md"],
  "max_reads": 20,
  "answer": {
    "culprit": "B",
    "motive": "financial_gain",
    "method": "poisoning"
  }
}
```

### 3.3 case_brief.md (예시)

```markdown
# Case Brief: The Silent Partner

## Incident Summary
On the evening of March 15, 2026, Mr. Choi Daeho (58), CEO of Hanjin Technologies, 
was found dead in his office at the company headquarters in Pangyo. 
The building security guard discovered the body at approximately 10:30 PM.

## Initial Assessment
Cause of death is pending forensic analysis. No signs of forced entry. 
The victim's office door was locked from the inside.

## Suspects
- **Suspect A (Ms. Kang Soyeon):** VP of Operations. Recently passed over for promotion.
- **Suspect B (Mr. Yoon Jaemin):** Co-founder and minority shareholder. 
  Subject of a recent buyout dispute.
- **Suspect C (Mr. Han Dongwoo):** Personal assistant to the victim. 
  Last known person to see the victim alive.

## Your Task
Examine the evidence files in the `evidence/` folder. 
Determine: **Who** committed the crime, **Why** (motive), and **How** (method).

Submit your answer when ready.
```

### 3.4 단서 파일 설계 원칙

```
1. 각 단서는 단독으로는 결론 불가. 2-3개 조합이 필요.
2. Critical evidence (핵심 단서) 3개를 읽으면 범인 특정 가능.
3. Red herring (미스디렉션) 1-3개 — 무관한 정보 또는 잘못된 방향.
4. 증인 진술은 부분적으로 모순 가능 (증인의 관점/편향 반영).
5. 알리바이 파일 중 하나는 검증 가능한 거짓.
6. 파일 이름만으로는 중요도 판단 불가 (선택 편향 방지).
```

---

## 4. 게임 엔진

### 4.1 DeductionGame (LxMGame 상속)

```python
class DeductionGame(LxMGame):
    """AI 추리 게임. CLI-native — 에이전트가 폴더를 탐색."""

    def get_rules(self) -> str: ...
    def initial_state(self, agents: list[dict]) -> dict: ...
    def validate_move(self, move: dict, agent_id: str, state: dict) -> dict: ...
    def apply_move(self, move: dict, agent_id: str, state: dict) -> dict: ...
    def is_over(self, state: dict) -> bool: ...
    def get_result(self, state: dict) -> dict: ...
    def summarize_move(self, move: dict, agent_id: str, state: dict) -> str: ...
    def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str | None: ...
```

### 4.2 State 구조

```json
{
  "current": {
    "phase": "investigating",
    "turn": 5,
    "agents": {
      "detective-1": {
        "files_read": ["case_brief.md", "witness_kim.md", "forensic_report.md"],
        "files_available": ["witness_park.md", "cctv_log.md", ...],
        "notes": "Suspect B alibi has inconsistency...",
        "submitted": false,
        "answer": null
      }
    },
    "scenario_id": "mystery_001"
  },
  "context": {
    "max_reads": 20,
    "total_evidence": 11,
    "difficulty": "medium"
  }
}
```

### 4.3 Move Types

```json
// 1. READ — 단서 파일 읽기
{
  "type": "deduction_action",
  "action": "read",
  "file": "forensic_report.md"
}

// 2. NOTE — 메모 작성 (선택적)
{
  "type": "deduction_action",
  "action": "note",
  "content": "Forensic report shows traces of aconitine. Suspect B has pharmacy background."
}

// 3. SUBMIT — 최종 답변 제출
{
  "type": "deduction_action",
  "action": "submit",
  "answer": {
    "culprit": "B",
    "motive": "financial_gain",
    "method": "poisoning"
  }
}
```

### 4.4 Validation Rules

```
READ:
  - file이 evidence/ 내에 존재해야 함
  - 이미 읽은 파일도 다시 읽기 가능 (카운트는 1회만)
  - max_reads 초과 시 자동 submit 강제

NOTE:
  - content는 2000자 이내
  - 덮어쓰기 (최신 메모만 유지) 또는 append (설정 가능)

SUBMIT:
  - culprit: 용의자 ID (A/B/C 등)
  - motive: 사전 정의된 목록 중 택 1 또는 자유 서술
  - method: 사전 정의된 목록 중 택 1 또는 자유 서술
  - 제출 후 게임 종료 (해당 에이전트)
```

---

## 5. 실행 모드

### 5.1 File Mode (CLI-native) ⭐

```
Orchestrator가 하는 것:
  1. match_dir에 시나리오 파일 복사 (case_brief.md + evidence/)
  2. 에이전트를 match_dir에서 호출: "이 사건을 해결하라"
  3. 에이전트가 자율적으로 파일 탐색
  4. 에이전트가 moves/turn_N_agent.json에 move 제출
  5. 에이전트가 READ move 제출 → 엔진이 files_read 업데이트
  6. 에이전트가 SUBMIT move 제출 → 게임 종료

에이전트가 하는 것:
  1. case_brief.md 읽기
  2. evidence/ 폴더 탐색
  3. 원하는 단서 파일 읽기
  4. agent_notes.md에 추론 메모 (선택)
  5. 최종 답변 제출
```

**File mode의 핵심:** 에이전트가 `ls evidence/`를 할 수 있고, `cat evidence/forensic_report.md`를 할 수 있음. 어떤 순서로 뭘 읽을지 에이전트가 결정. **이게 CLI-native.**

**주의:** File mode에서는 에이전트가 answer_key.json을 읽으면 안 됨.
→ answer_key.json은 match_dir에 복사하지 않음. 엔진만 시나리오 폴더에서 참조.

### 5.2 Inline Mode

```
Orchestrator가 하는 것:
  Turn 1: case_brief.md 내용 + evidence 파일 목록 → 프롬프트에 포함
          "다음 증거 파일 중 읽을 것을 선택하세요: [목록]"
  Turn 2: 선택한 파일 내용을 프롬프트에 포함
          "이 증거를 바탕으로: 더 읽기 / 메모 작성 / 답변 제출"
  ...
  Turn N: 에이전트가 SUBMIT

에이전트가 하는 것:
  매 턴 JSON envelope로 응답 (기존 방식과 동일)
```

### 5.3 모드 비교 실험

```
같은 시나리오, 같은 모델:
  Condition A: File mode — 에이전트가 직접 폴더 탐색
  Condition B: Inline mode — Orchestrator가 프롬프트로 단서 제공

측정:
  - 정확도 (범인/동기/수단)
  - 효율성 (읽은 파일 수)
  - 소요 시간
  - 탐색 순서 (어떤 파일을 먼저 읽었나)
  - 추론 품질 (agent_notes.md)

가설:
  - File mode가 더 정확할 수 있음 (선택적 탐색, 정보 필터링)
  - Inline mode가 더 빠를 수 있음 (네트워크 오버헤드 없음)
  - 단서가 많을수록 File mode 유리 (inline은 프롬프트 과부하)
```

---

## 6. 시나리오 관리

### 6.1 난이도 체계

```
Easy (쉬움):
  용의자 3명, 단서 8개, 미스디렉션 0개
  핵심 단서 2개만 읽으면 풀 수 있음
  → 모든 모델이 풀 수 있는 베이스라인

Medium (보통):
  용의자 3-4명, 단서 10-12개, 미스디렉션 1개
  핵심 단서 3개 + 조합 추론 필요
  → 대부분 모델이 풀지만 효율성 차이

Hard (어려움):
  용의자 4-5명, 단서 12-15개, 미스디렉션 2-3개
  핵심 단서 3-4개 + 다단계 추론 + 모순 해소 필요
  → 일부 모델만 정확하게 풀 수 있음
```

### 6.2 시나리오 생성

시나리오는 .md 파일 세트. 새 시나리오 추가 = 폴더 추가.

```
scenarios/
├── mystery_001/   ← "The Silent Partner" (medium)
├── mystery_002/   ← "The Locked Room" (easy)
├── mystery_003/   ← "The Insider" (hard)
└── mystery_004/   ← "The Double Cross" (hard)
```

**v1: 3개 시나리오 (easy/medium/hard 각 1개).** 추후 확장.

시나리오 작성 가이드:
1. case_brief.md로 상황 설정 (500자 이내)
2. 단서 파일은 각 300-500자 (너무 길면 읽기 부담, 너무 짧으면 정보 부족)
3. 정답은 단서를 논리적으로 조합하면 유일하게 도출 가능해야 함
4. 미스디렉션은 "그럴듯하지만 다른 단서와 모순"인 정보
5. 한국어 또는 영어 (에이전트의 언어 능력에 따라 다를 수 있음)

### 6.3 시나리오 검증

새 시나리오 추가 시 검증 체크리스트:
- [ ] 정답이 유일한가 (다른 해석 가능성 없는가)
- [ ] 핵심 단서 3개 이상으로 정답 도출 가능한가
- [ ] 미스디렉션이 정답과 완전히 모순되는가 (애매하면 안 됨)
- [ ] 파일 이름에서 중요도가 드러나지 않는가
- [ ] 난이도 태그가 적절한가

---

## 7. 점수 체계

### 7.1 정확도 점수

```
culprit (범인):  정확 = 1점, 오답 = 0점
motive (동기):   정확 = 1점, 부분 정답 = 0.5점, 오답 = 0점
method (수단):   정확 = 1점, 부분 정답 = 0.5점, 오답 = 0점

정확도 합계: 0-3점
```

"부분 정답" = 자유 서술 시 의미적으로 가까운 경우. 사전 정의 목록에서 선택 시에는 정확/오답만.

### 7.2 효율성 점수

```
efficiency = 1 - (files_read / total_evidence)

예: 11개 중 4개 읽음 → efficiency = 1 - 4/11 = 0.636
예: 11개 중 11개 읽음 → efficiency = 1 - 11/11 = 0.0
```

### 7.3 최종 점수

```
final_score = accuracy * (1 + efficiency * 0.5)

예: 정확도 3/3, 효율성 0.636
    → 3 * (1 + 0.636 * 0.5) = 3 * 1.318 = 3.95

예: 정확도 2/3, 효율성 0.0 (다 읽음)
    → 2 * (1 + 0) = 2.0
```

**정확도가 0이면 효율성은 무의미 (빨리 틀려도 점수 없음).**

### 7.4 Race Mode (Mode B) 추가 규칙

```
선제출 보너스: 먼저 정확히 제출한 에이전트에게 +0.5점
오답 페널티: 틀린 답 제출 시 2턴 동안 submit 불가 (더 읽어야 함)
동시 정답: 효율성 높은 쪽이 승
```

---

## 8. Shell Engineering 적용

### 8.1 추리 전략 Shell

```markdown
# Deductive Shell (연역적)
물증(forensic, cctv)을 먼저 확인하라.
물리적 증거로 수단을 특정한 후, 동기와 범인을 역추론.
증언은 물증과 모순되지 않을 때만 참고.

# Inductive Shell (귀납적)  
증인 진술을 먼저 수집하라.
진술 간 모순을 찾아 거짓말을 탐지.
모순이 발견된 용의자의 알리바이를 집중 조사.

# Financial Shell (재무 추적)
재무 기록과 통화 내역을 우선 확인하라.
금전적 동기를 먼저 확인하고, 기회와 수단을 나중에.

# Efficient Shell (최소 탐색)
가장 적은 파일로 결론에 도달하라.
파일 이름과 case_brief에서 핵심 단서를 예측하고 선택적으로 읽어라.
확신이 생기면 즉시 제출.
```

### 8.2 Shell Engineering 실험

```
같은 시나리오, 같은 모델, 다른 Shell:
  A: no-shell (자유 탐색)
  B: Deductive Shell
  C: Inductive Shell
  D: Efficient Shell

측정: 정확도, 효율성, 탐색 순서, 소요 시간

예상 Shell Engineering 발견:
  - "어떤 추리 전략이 가장 효과적인가"
  - "Parametric Directness: 추리 전략이 탐색 행동에 직접 매핑되는가"
  - "Shell이 탐색 순서를 바꾸고, 그것이 정확도를 바꾸는가"
```

---

## 9. Viewer 연동

### 9.1 Viewer가 보여줄 것

```
1. 사건 개요 (case_brief.md)
2. 단서 파일 목록 (읽음/안 읽음 표시)
3. 에이전트의 탐색 순서 (타임라인)
4. 에이전트의 메모 (agent_notes 또는 NOTE move)
5. 최종 답변 vs 정답
6. 점수 (정확도 + 효율성)

Race mode:
7. 두 에이전트의 탐색 순서 비교 (나란히)
8. 누가 먼저 제출했는지
```

### 9.2 Viewer 데이터 구조 (log.json에 포함)

```json
{
  "turns": [
    {
      "turn": 1,
      "agent_id": "detective-1",
      "action": "read",
      "file": "case_brief.md",
      "timestamp": "2026-03-28T14:00:00Z"
    },
    {
      "turn": 2,
      "agent_id": "detective-1",
      "action": "read",
      "file": "forensic_report.md",
      "timestamp": "2026-03-28T14:00:15Z"
    },
    {
      "turn": 3,
      "agent_id": "detective-1",
      "action": "note",
      "content": "Aconitine traces found. Suspect B has pharmacy license.",
      "timestamp": "2026-03-28T14:00:30Z"
    },
    {
      "turn": 5,
      "agent_id": "detective-1",
      "action": "submit",
      "answer": {"culprit": "B", "motive": "financial_gain", "method": "poisoning"},
      "timestamp": "2026-03-28T14:01:00Z"
    }
  ]
}
```

---

## 10. 구현 계획

### Phase 1: Solo Mode + Inline (1주)

```
1. DeductionGame 엔진
   - LxMGame 상속
   - initial_state: 시나리오 로드, 에이전트 초기화
   - validate_move: read/note/submit 검증
   - apply_move: files_read 업데이트, 정답 비교
   - build_inline_prompt: 턴별 프롬프트 구성
   - is_over: submit 완료 시 종료
   - get_result: 정확도 + 효율성 점수

2. 시나리오 3개 작성
   - mystery_001 (easy): 용의자 3, 단서 8, 미스디렉션 0
   - mystery_002 (medium): 용의자 3, 단서 11, 미스디렉션 1
   - mystery_003 (hard): 용의자 4, 단서 14, 미스디렉션 2

3. 기본 테스트
   - Sonnet solo, 3 시나리오 각 1회 → 정확도/효율성 확인
   - Haiku solo → Cross-model 비교
```

### Phase 2: File Mode (Phase 1 완료 후)

```
4. File Mode 지원
   - match_dir에 시나리오 파일 복사
   - answer_key.json은 복사하지 않음 (엔진만 참조)
   - 에이전트의 파일 탐색 행동 로깅
   - File mode vs Inline mode 비교 실험

5. agent_notes.md 지원
   - File mode에서 에이전트가 자유롭게 메모 파일 작성
   - 메모 내용을 log.json에 기록
```

### Phase 3: Race Mode (Phase 2 완료 후)

```
6. Mode B (Race) 구현
   - 2 에이전트 동시 진행
   - 선제출 보너스, 오답 페널티
   - 동일 시나리오 동시 탐색
```

### 시나리오 제작 참고

**v1 시나리오는 Luca(이 Claude)가 작성.** case_brief.md + evidence/ 파일 세트. Cody는 엔진 구현에 집중.

시나리오 작성 시 주의:
- 정답이 논리적으로 유일해야 함
- 단서 간 모순 없음 (미스디렉션은 의도적 모순)
- 영어로 작성 (다국어는 나중에)
- 각 파일 300-500 words

---

## 11. 연구 가치

### 11.1 측정 가능한 새로운 축

| 축 | 설명 | 기존 게임에서 가능 여부 |
|---|---|---|
| 정보 필터링 | 어떤 단서를 선택적으로 읽는가 | ❌ |
| 논리 추론 정확도 | 여러 단서를 조합해서 정답 도출 | ❌ |
| 탐색 전략 | 연역적 vs 귀납적 vs 효율적 | ❌ |
| CLI 에이전트 능력 | 파일 시스템 활용 | ❌ |
| Agent Memory 임계점 | 단서가 많을 때 메모리 효과 | ⚠️ (현재 게임에서는 불필요) |

### 11.2 Shell Engineering 연구 질문

```
Q1: "추리 전략 Shell이 정확도를 바꾸는가?" → Parametric Directness 검증
Q2: "효율성 Shell이 탐색 순서를 바꾸는가?" → Correction Opportunity 검증
Q3: "File mode vs Inline mode에서 Shell 효과가 다른가?" → Execution Feasibility 검증
Q4: "단서가 많은 Hard 시나리오에서만 Agent Memory가 효과적인가?" → Memory 임계점
```

### 11.3 Cross-Model 연구 질문

```
Q5: "어떤 모델이 추리를 잘 하는가?" → 새로운 능력 축
Q6: "파일 탐색 순서가 모델마다 다른가?" → 행동 프로파일 확장
Q7: "SLM(Ollama)도 추리를 할 수 있는가?" → Cross-Tier
Q8: "추리 능력과 포커/아발론 능력은 상관이 있는가?" → 다차원 능력 확인
```

---

## 12. 기술적 세부 사항

### 12.1 File Mode에서의 보안

```
문제: 에이전트가 answer_key.json을 읽으면 치팅
해결:
  1. answer_key.json은 match_dir에 복사하지 않음
  2. 엔진이 scenarios/ 원본에서 직접 참조
  3. match_dir에는 case_brief.md + evidence/ 만 복사
```

### 12.2 File Mode 턴 구조

```
Option A: 자유 시간제 (권장)
  - 에이전트에게 "N분 안에 해결하라" 시간 제한
  - 에이전트가 자유롭게 파일을 읽고, 메모를 쓰고, 답 제출
  - Orchestrator는 타임아웃만 관리
  
Option B: 턴 기반
  - 매 턴 에이전트에게 "다음 행동?" 물어봄
  - 에이전트가 read/note/submit 중 선택
  - 기존 Orchestrator 턴 구조와 호환
```

**v1: Option B (턴 기반).** 기존 Orchestrator 호환. 나중에 Option A 추가 가능.

### 12.3 File Mode 에이전트 호출

```
File mode에서 에이전트 호출 방식:

claude "이 폴더의 사건을 해결하세요. 
case_brief.md를 먼저 읽고, evidence/ 폴더의 단서를 탐색하세요.
답을 알았으면 moves/ 폴더에 JSON으로 제출하세요."

→ 에이전트가 자율적으로:
  ls evidence/
  cat evidence/forensic_report.md
  cat evidence/phone_records.md
  ...
  echo '{"protocol":"lxm-v0.2", ...}' > moves/turn_005_detective.json
```

이건 discovery mode의 확장 — 현재도 discovery_turns에서 에이전트가 파일을 읽음. 추리 게임은 **전체 게임이 discovery mode.**

### 12.4 Inline Mode 프롬프트 구성

```python
def build_inline_prompt(self, agent_id: str, state: dict, turn: int) -> str:
    agent_state = state["current"]["agents"][agent_id]
    
    if turn == 1:
        # 첫 턴: case brief + 파일 목록
        prompt = f"""
{self.case_brief}

Available evidence files:
{self.format_file_list(agent_state["files_available"])}

Files you've read so far: {agent_state["files_read"]}

Choose your action:
- READ a file: {{"type": "deduction_action", "action": "read", "file": "<filename>"}}
- SUBMIT answer: {{"type": "deduction_action", "action": "submit", "answer": {{"culprit": "?", "motive": "?", "method": "?"}}}}
"""
    else:
        # 이후 턴: 이전 읽은 파일 내용 포함
        last_read = agent_state.get("last_read_content", "")
        prompt = f"""
You previously read: {agent_state["files_read"]}

Content of last file read:
---
{last_read}
---

Remaining files: {self.format_file_list(agent_state["files_available"])}

Your notes so far: {agent_state.get("notes", "None")}

Choose your action:
- READ another file
- NOTE your reasoning
- SUBMIT your answer
"""
    return prompt
```

---

## 8. Human Participation Modes

Deduction Game은 LxM 최초의 인간 직접 참여 게임. AI만 경쟁하는 다른 게임과 달리, 인간이 직접 추리에 참여하고 AI와 경쟁/협력할 수 있다.

### 8.1 Mode: Solo (Human Only)

인간이 혼자 시나리오를 풀.
- 웹 UI에서 단서 파일을 클릭해서 열람
- 답변 제출 시 점수 산정 (정확도 + 효율성)
- 리더보드에 인간 기록도 표시
- **구현:** Viewer 확장 수준. Solo UI가 나머지 모드의 기반.

### 8.2 Mode: Race (Human vs AI)

같은 시나리오를 인간과 AI가 동시에 풀.
- 타이머 시작 → 인간은 웹 UI, AI는 inline mode 동시 진행
- 먼저 정확하게 제출한 쪽이 승리
- 결과 카드: "나 vs Sonnet — 누가 더 빨리 풀었나" → 공유 가능
- **구현:** Solo + AI 동시 실행 + 타이머.

### 8.3 Mode: AI Coach

인간이 추리하는 동안 AI가 힌트 제공.
- "이 단서를 먼저 읽어보세요", "이 용의자의 알리바이를 확인해보세요"
- AI의 코치 품질도 측정 가능 (코치 받은 인간 vs 안 받은 인간)
- **구현:** Solo + AI 힌트 레이어.

### 8.4 Mode: AI Suspects (심문 모드)

인간이 탐정, AI가 용의자 역할.
- AI 용의자가 캐릭터에 맞게 답변 (범인은 거짓말, 무고한 사람은 진실)
- 인간이 자유롭게 질문 → AI가 역할극으로 응답
- 단서 파일 + 심문 조합으로 추리
- **LxM에서만 가능한 독자적 경험**
- **구현:** 복잡. 용의자 페르소나 생성 + 자연어 대화 + 거짓말 일관성. v2.

### 구현 순서
```
Phase 1: Solo (웹 UI에서 단서 클릭 + 답 제출)
Phase 2: Race (Solo + AI 동시 실행 + 타이머 + 결과 카드)
Phase 3: Coach (Solo + AI 힌트 레이어)
Phase 4: Suspects (심문 모드 — Mode C의 확장)
```

---

## 9. Creator Ecosystem — 시나리오 제작 + 경쟁

Deduction Game의 핵심 차별화. 다른 LxM 게임(Poker, Chess 등)은 게임 규칙이 고정되어 있지만, Deduction은 **시나리오가 무한히 확장 가능**하고, 그 확장을 **참여자들이 만든다.**

### 9.1 두 가지 경쟁 축

```
풀기 경쟁 (Solver Leaderboard):
  "누가 더 잘 푸는가" — 정확도 + 효율성
  AI 모델별, 인간별 릭드

만들기 경쟁 (Creator Leaderboard):
  "누가 더 좋은 미스터리를 만드는가" — 시나리오 품질 평가
  인간, AI, 인간+AI 협업 모두 참여 가능
```

### 9.2 시나리오 제작 모드

```
Mode A: Human Author
  인간이 직접 scenario.json + case_brief.md + evidence/ 작성
  전통적 미스터리 창작

Mode B: AI Author + Human Review
  AI가 줄거리를 생성하고 scenario.json + evidence/ 자동 생성
  인간이 논리적 결함/난이도/재미를 검수하고 수정
  품질 관리된 반자동 생성

Mode C: Human Outline + AI Expansion
  인간이 줄거리/범인/동기만 제공
  AI가 단서 파일, 증인 진술, 알리바이, 미스디렉션을 확장
  가장 실용적인 협업 모드

Mode D: AI vs AI (Infinite Content)
  AI가 시나리오를 자동 생성 → 다른 AI가 풀기
  인간 개입 없이 무한 콘텐츠 생산
  시나리오 생성 AI의 품질도 측정 가능
```

### 9.3 시나리오 품질 측정

제출된 시나리오를 여러 AI/인간에게 풀게 해서 객관적 품질 점수 산정:

```
정답률 (solve_rate):
  0-10%   → 너무 어렵거나 논리적 결함
  10-30%  → Hard
  30-60%  → Medium (이상적)
  60-90%  → Easy
  90-100% → 너무 쉬움

미스디렉션 효과 (misdirection_rate):
  red herring에 걸린 비율 → 높을수록 좋은 미스디렉션

탐색 다양성 (path_diversity):
  풀이자마다 다른 순서로 단서를 읽는가 → 다양할수록 잘 설계된 시나리오

효율성 분산 (efficiency_variance):
  정답자들의 파일 읽기 수가 다양 → 여러 경로로 풀 수 있는 시나리오

종합 품질 점수 = f(solve_rate, misdirection_rate, path_diversity, efficiency_variance)
```

### 9.4 Creator Leaderboard

```
릭드 기준:
  제출한 시나리오의 평균 품질 점수
  시나리오 수
  풀이자 만족도 (선택적)

카테고리:
  - Best Human Creator
  - Best AI Creator (어떤 모델이 더 좋은 미스터리를 만드는가)
  - Best Human+AI Team
```

### 9.5 Model Medicine 가치

```
Creator 측면:
  "어떤 모델이 더 좋은 미스터리를 만드는가" → 창의성/서사 능력 측정
  "어떤 모델이 논리적 결함 없는 시나리오를 만드는가" → 논리적 일관성 측정
  "미스디렉션 효과가 높은 시나리오를 만드는 모델" → Theory of Mind (풀이자를 속이는 능력)

Solver 측면:
  "어떤 모델이 어떤 난이도까지 풀 수 있는가" → 추론 능력 계층
  "모델 크기와 추리 능력의 관계" → SLM vs Cloud 추론 비교
  "언어별 추리 능력 차이" → 다국어 측정 축
```

### 9.6 시나리오 제출 포맷

```
제출자가 제공해야 하는 것:
  scenario.json   — 정답 + 메타데이터
  case_brief.md   — 사건 개요
  evidence/       — 단서 파일들 (8-15개 권장)

검증 기준 (자동):
  - scenario.json 포맷 유효성
  - 모든 evidence_files이 실제로 존재하는지
  - critical_evidence로 정답 도출이 논리적으로 가능한지 (검증 AI로 체크)
  - red_herring이 정답과 모순되지 않는지
```

### 9.7 구현 순서

```
v1: 내부 시나리오만 (Luca/JJ 제작) + AI Solver
v2: Human Participation (Solo → Race → Coach)
v3: Creator Submission (인간 제작 시나리오 제출 + 자동 품질 평가)
v4: AI Creator (AI 자동 생성 + AI Suspects 심문 모드)
```

---

*LxM Deduction Game Spec v0.2*
*"The truth is in the folder. You just have to find it — or create it."*
