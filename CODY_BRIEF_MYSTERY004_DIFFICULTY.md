# Cody 작업 브리프: mystery_004 난이도 조정 + SDI 보정 시스템

**날짜:** 2026-03-30
**작성:** Luca
**우선순위:** P0

---

## Part 0: case_brief 표준화 (P0 — 완료, Luca 적용 완료)

### 배경
GPT-5.4가 4개 시나리오 전부 evidence 파일 0개로 3/3 정답. case_brief만으로 추론 가능.

### 적용된 표준화 원칙

case_brief는 다음만 포함:
- **사건 발생 사실:** 언제, 어디서, 누가 사망/피해를 입었는지
- **용의자 이름 + 직업만:** 동기 연결고리 제거
- **"수사 중"이라는 사실만:** 구체적 사인, 수법, 현장 디테일 없음

case_brief에서 제거된 것:
- ❌ 사인 힌트 (찻잔, 독물학, IV 이상 등)
- ❌ 방법 힌트 (alarm disabled, keycard, locked room mechanism)
- ❌ 동기 시사 (사업 분쟁, 권력 다투, 낙찰 등)
- ❌ 용의자 역할에서 추론 가능한 정보 ("약사", "아들", "IV 준비" 등)

### 적용 상태
- mystery_001 ~ 004 EN: ✅ 완료
- mystery_001_ko ~ 004_ko: ✅ 완료
- **Cody는 case_brief를 추가 수정하지 말 것. 이미 표준화 적용됨.**

### GPT-5.4 검증 테스트
표준화 후 GPT-5.4로 다시 테스트 필요:
- 파일 0개로 정답 → 여전히 누출 있음
- 파일 2개+ 읽어야 정답 → 표준화 성공

---

## Part 1: mystery_004 난이도 조정

### 현재 문제
phone_records 하나에 KCl 주문 + 수족관 없음 + 7.8억 빚이 전부 있어서 "자백 조서" 수준.

### 수정 사항

#### 1-A. phone_records.md 분산 (필수)

**phone_records.md에서 제거할 것:**
- 한화케미칼 KCl 주문 관련 수사관 주석 전부 삭제
- 7.8억 사채 + 계좌 잔고 정보 삭제
- 서강호 변호사의 상세 문답 삭제
- 남기는 것: 3명의 통화 내역 표 (시간, 상대방, 시간)만. "한화케미칼 서플라이" 연락처와 "서강호 변호사" 연락처는 보이되, 수사관 해석 없이.

**신규 파일 2개 생성:**

`evidence/delivery_records.md`:
- 한화케미칼 KCl 500g 주문 내역 (날짜, 품목, 배송지)
- 수족관 미보유 확인 (경비원 증언)
- 이 파일만으로는 "C가 KCl을 샀다"는 알지만 왜 샀는지(동기)는 모름

`evidence/financial_investigation.md`:
- C의 사채 7.8억 원 내역
- 계좌 잔고 230만 원
- 이전 빚 변제 이력 (2022년 3억, 2023년 4.5억) — will_amendment의 변호사 메모와 교차 확인되는 정보

#### 1-B. scenario.json 업데이트

```json
"evidence_files": [
  "medical_report.md",
  "autopsy_report.md",
  "clinic_access_log.md",
  "cctv_footage.md",
  "alibi_A.md",
  "alibi_B.md",
  "alibi_C.md",
  "phone_records.md",
  "will_amendment.md",
  "malpractice_complaint.md",
  "delivery_records.md",
  "financial_investigation.md"
]
```

- evidence 10 → 12개
- critical_evidence에 "delivery_records.md" 추가
- max_reads 18 → 20으로 상향

#### 1-C. 한글 버전 동일 적용 (mystery_004_ko)

EN 확정 후 동일하게:
- `통화_기록.md` 분산
- `배송_기록.md`, `재정_조사.md` 신규 생성
- scenario.json 동일 업데이트

### 테스트

수정 후 매번:
```bash
# mystery_004만 cross-model 3회
python scripts/run_deduction_crossmodel.py
# SCENARIOS = ["mystery_004"], RUNS = 3
```

목표: Sonnet 1-2/3, Haiku 0-1/3, Opus 2-3/3.
Sonnet이 여전히 3/3이면 → case_brief 추가 축소 또는 red herring 강화.

---

## Part 2: Scenario Difficulty Index (SDI) 보정 시스템

### 개요

시나리오 난이도를 설계자 직감이 아닌 **실증 데이터로 측정**.

### SDI 공식

```python
SDI = 1 - weighted_solve_rate

weights = {
    "opus": 0.15,     # Tier 4 — 못 풀면 결함
    "sonnet": 0.25,   # Tier 3 — 핵심 벤치마크
    "haiku": 0.30,    # Tier 2 — 가장 민감
    "slm_best": 0.30  # Tier 1 — 바닥 측정
}

# solve_rate = 범인 정답 횟수 / 시도 횟수 (최소 3회)
# slm_best = SLM 중 최고 모델 (현재 mistral)
```

### SDI 등급

| SDI | 등급 | 별 |
|-----|------|----|
| 0.00–0.20 | Easy | ★☆☆ |
| 0.20–0.50 | Medium | ★★☆ |
| 0.50–0.80 | Hard | ★★★ |
| 0.80–1.00 | Extreme | ★★★★ |

### 구현: `lxm/tools/calibrate_scenario.py`

```bash
# 단일 시나리오 보정
python -m lxm.tools.calibrate_scenario games/deduction/scenarios/mystery_001/

# 전체 보정
python -m lxm.tools.calibrate_scenario games/deduction/scenarios/
```

#### 동작:
1. scenario.json 로드
2. 3개 Cloud 모델(opus, sonnet, haiku) × 3회 = 9매치 실행
3. (선택) SLM 데이터가 있으면 사용, 없으면 slm_best = 0 (최악 가정)
4. SDI + 보조 지표 계산
5. `difficulty_card.json` 생성 (시나리오 폴더 안에)

#### difficulty_card.json 출력 예시:

```json
{
  "sdi": 0.467,
  "grade": "Medium",
  "stars": 2,
  "exploration_depth": 0.42,
  "tested_models": {
    "opus": {"runs": 3, "culprit_correct": 3, "avg_files": 4.3},
    "sonnet": {"runs": 3, "culprit_correct": 1, "avg_files": 3.7},
    "haiku": {"runs": 3, "culprit_correct": 1, "avg_files": 2.0},
    "slm_best": {"model": "mistral", "runs": 3, "culprit_correct": 2, "avg_files": 11.7}
  },
  "calibrated_at": "2026-03-30T15:00:00Z",
  "calibration_version": "v1"
}
```

#### 보조 지표 (difficulty_card에 포함):

```python
# Exploration Depth = 평균 파일 읽기 / 전체 evidence 수
exploration_depth = avg_files_read / total_evidence

# Component Difficulty = 동기+방법 오답 비율
component_difficulty = 1 - (motive_correct_rate + method_correct_rate) / 2
```

### 보정 실행 계획

#### Phase 1: mystery_004 조정 후 보정
1. Part 1 수정 완료
2. mystery_004 보정 실행 (9매치)
3. SDI 확인 → 0.20-0.50 범위 (Medium) 목표

#### Phase 2: 기존 시나리오 재보정

mystery_001: 기존 데이터 활용 가능 (Opus 3/3, Sonnet 1/3, Haiku 1/3, mistral 2/3)
mystery_002: **Sonnet/Haiku 3회 데이터 부족 → 추가 9매치 필요**
mystery_003: **동일 → 추가 9매치 필요**

```bash
# 002/003 보정 (각 9매치, 총 18매치)
python -m lxm.tools.calibrate_scenario games/deduction/scenarios/mystery_002/
python -m lxm.tools.calibrate_scenario games/deduction/scenarios/mystery_003/
```

기존 라벨과 SDI가 다를 수 있음. **SDI가 공식 난이도가 됨. 기존 라벨은 참고용으로 유지.**

#### Phase 3: scenario.json에 SDI 반영

보정 후 각 scenario.json의 `difficulty` 필드를 SDI 등급으로 업데이트:
```json
{
  "difficulty": "medium",
  "sdi": 0.467,
  "sdi_grade": "★★☆"
}
```

Solo Mode UI 시나리오 카드에도 SDI 별 표시.

### validate_scenario 업데이트

`difficulty_card.json`이 있으면:
- SDI 값과 scenario.json의 difficulty 라벨 불일치 시 경고
- "Calibrated ✅" vs "Uncalibrated ⚠️" 표시

---

## 작업 순서 요약

| 순서 | 작업 | 담당 | 예상 매치 수 |
|------|------|------|------------|
| 0 | case_brief 표준화 (EN+KO 8개) | **Luca ✅ 완료** | 0 |
| 1 | GPT-5.4 검증 테스트 (표준화 후) | Cody | 4-8 |
| 2 | mystery_004 phone_records 분산 (EN) | Cody | 0 |
| 3 | mystery_004 테스트 | Cody | 9-15 |
| 4 | 목표 미달 시 추가 조정 → 재테스트 | Cody | 0-15 |
| 5 | mystery_004_ko 동일 적용 | Cody | 0 |
| 6 | calibrate_scenario.py 구현 | Cody | 0 |
| 7 | mystery_001~004 전체 보정 | Cody | 36 |
| 8 | difficulty_card 생성 + scenario.json SDI 반영 | Cody | 0 |

**총 예상: 49-74 매치.** 대부분 자동 실행.

**핵심: Step 1(GPT-5.4 검증)을 먼저 돌려서 case_brief 표준화가 효과적인지 확인 후 SDI 보정 진행.**

---

## 참고 문서

- `LXM_SCENARIO_DIFFICULTY_INDEX.md` — SDI 설계 문서 (상세)
- `LXM_DEDUCTION_SPEC_v0.1.md` Section 9.3 — 시나리오 품질 측정
- 기존 cross-model 데이터: `reports/deduction_crossmodel.json`

---

*"난이도는 설계자가 정하는 게 아니라 AI가 측정하는 것이다."*
