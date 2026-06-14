# Scenario Difficulty Index (SDI) — v3

**Date:** 2026-03-31
**Author:** Luca
**Status:** Gen 2 Cross-Company + SLM 81매치 데이터로 확정

---

## 1. SDI 공식

### 6-Slot 가중 모델

| Slot | 모델 | Tier | 가중치 | 근거 |
|------|------|------|--------|------|
| 1 | Opus | Top | 0.10 | 최상위, 변별력 낮음 |
| 2 | G 2.5 Pro | Top | 0.10 | 최상위 |
| 3 | Sonnet | Mid | 0.20 | 중상위, 핵심 벤치마크 |
| 4 | G 3 Flash | Mid | 0.20 | 중상위 |
| 5 | Haiku | Low | 0.20 | 중위, 민감 구간 |
| 6 | SLM-pool | Floor | 0.20 | 하한선 (Functional Engagement 통과 모델 평균) |

```
SDI = 1 - Σ(weight_i × solve_rate_i)
```

Solve Rate = (범인 정답 횟수) / (시도 횟수), 최소 3회.

### SLM-pool 선정 기준: Functional Engagement

**원칙:** Deduction은 "증거를 읽고 → 추론하고 → 제출"하는 게임이다. 증거를 거의 읽지 않는 모델의 0%는 "시나리오가 어렵다"가 아니라 "게임 참여 실패"이므로 SDI(시나리오 난이도)에 포함하면 안 된다.

**기준:** 평균 Exploration Depth ≥ 2.0 파일

| 모델 | Size | Avg Files | 포함 | 근거 |
|------|------|-----------|------|------|
| gemma2 | 9B | 8.2 | ✅ | 체계적 탐색 |
| mistral | 7B | 5.0 | ✅ | 체계적 탐색 |
| deepseek-r1 | 8B | 3.0 | ✅ | 부분 탐색 |
| phi4-mini | 3.8B | 1.0 | ❌ | 최소 탐색 |
| llama3.1 | 8B | 1.0 | ❌ | 최소 탐색 |
| exaone3.5 | 7.8B | 0.9 | ❌ | 거의 미탐색 |
| gemma3 | 4B | 0.9 | ❌ | 거의 미탐색 |
| qwen3 | 8B | 0.4 | ❌ | 거의 미탐색 |
| smollm2 | 1.7B | 0.1 | ❌ | 미참여 |

**SLM-pool = avg(gemma2, mistral, deepseek-r1)**

ED < 2.0 모델 제외 이유: 이 모델들은 "읽고 → 추론하고 → 제출하라"는 지시의 "읽기" 단계를 건너뛰는 instruction following 실패를 보임. 이는 시나리오 난이도와 무관한 Core 수준의 한계이므로 SDI에 포함하면 난이도가 아니라 SLM instruction-following 능력을 측정하게 된다.

### SDI 등급

| SDI | 등급 | 의미 |
|-----|------|------|
| 0.00–0.30 | ★☆☆☆ Easy | 대부분 맞춤 |
| 0.30–0.50 | ★★☆☆ Medium | 중하위 모델 자주 틀림 |
| 0.50–0.75 | ★★★☆ Hard | 상위 모델도 불안정 |
| 0.75–1.00 | ★★★★ Extreme | 대부분 틀림 |

---

## 2. 실측 SDI 결과 (Gen 2 — 확정)

### SLM-pool 시나리오별 데이터

| 모델 | 005 | 006 | 007 |
|------|-----|-----|-----|
| gemma2 | 0.67 | 0.67 | 0.00 |
| mistral | 0.33 | 0.00 | 0.67 |
| deepseek-r1 | 0.33 | 0.00 | 0.00 |
| **SLM-pool avg** | **0.44** | **0.22** | **0.22** |

### SDI 확정값

| 시나리오 | Opus | G2.5Pro | Sonnet | Flash | Haiku | SLM-pool | **SDI** | 등급 |
|---------|------|---------|--------|-------|-------|----------|---------|------|
| 005 | 1.00 | 0.33 | 1.00 | 1.00 | 0.67 | 0.44 | **0.24** | ★☆ Easy |
| 006 v2 | 1.00 | 0.33 | 1.00 | 0.67 | 0.67 | 0.22 | **0.36** | ★★ Medium |
| 007 | 0.33 | 0.00 | 0.00 | 0.67 | 0.33 | 0.22 | **0.72** | ★★★ Hard |

### v2 → v3 변화

| 시나리오 | SDI v2 (SLM=0.00) | SDI v3 (SLM-pool) | 등급 변화 |
|---------|-------------------|-------------------|----------|
| 005 | 0.33 | **0.24** | Medium → **Easy** |
| 006 v2 | 0.40 | **0.36** | Medium (유지) |
| 007 | 0.77 | **0.72** | Hard (유지) |

005가 Easy로 하향 — SLM-pool이 44% 풀었으므로 실제로 가장 쉬운 시나리오임이 확인됨.

---

## 3. Cloud vs SLM 실패 모드 분리

**SDI는 Cloud 모델과 SLM의 데이터를 하나의 공식으로 합산하지만, 두 집단의 오답 원인은 근본적으로 다르다.**

### 실패 모드 비교

| | Cloud (Opus/Sonnet/Flash/Haiku/G2.5Pro) | SLM (gemma2/mistral/deepseek-r1) |
|---|---|---|
| 실패 모드 | **Reasoning Failure** — 증거를 읽고 레드헤링에 속음 | **Engagement Failure** — 증거를 충분히 읽지 않고 제출 |
| 007 A오답 | **60%** (15회 중 9회) | A오답 거의 없음 |
| 레드헤링 효과 | 강력 — SDI 핵심 레버 | **미발동** — 레드헤링에 빠지려면 먼저 증거를 읽어야 함 |
| 탐색 깊이 | 3~16파일 (모델 의존) | 3~8파일 (pool 모델), 0~1파일 (제외 모델) |

### 해석 주의사항

SDI의 SLM 컴포넌트는 "시나리오의 본질적 난이도"보다 **"최소 탐색 요구량"**에 가깝다. Cloud 모델이 틀리는 이유(레드헤링)와 SLM이 틀리는 이유(탐색 부족)가 다르므로, 동일한 SDI 값이 두 집단에 다른 의미를 가진다.

이 한계는 시나리오 20개+ 달성 후 **Cloud-SDI / SLM-SDI 분리**로 해결 가능. 현재는 데이터 부족(Gen 2 = 3개)으로 통합 SDI를 유지하되, 실패 모드 차이를 기록한다.

---

## 4. SDI 핵심 레버: 레드헤링 강도

Gen 2 실험에서 SDI를 결정하는 가장 강력한 변수:

| 시나리오 | 레드헤링 | Cloud 오답률 (15회) | SDI |
|---------|---------|-------------------|-----|
| 005 | A(CFO) — 중간 | 20% | 0.24 |
| 006 | B(전 연인) — 중간 | 20% | 0.36 |
| 007 | A(보험)+C(표절) — 최강 | **60%** | **0.72** |

**레드헤링의 "내러티브 완성도"가 SDI를 직접 결정.** 단, 레드헤링 효과는 Cloud 모델에만 적용 — SLM은 증거를 충분히 읽지 않아 레드헤링에 노출되기 전에 실패한다.

---

## 5. SDI 정확도의 전제조건

### 선택지 직교성 (Orthogonality)

method_options/motive_options의 의미 중복이 SDI를 오염시킴.

| 사례 | 문제 | 결과 | 수정 후 |
|------|------|------|---------|
| 005 v1 | fraudulent_invoices ≈ shell_company_server_manipulation | method 44% | → physical_document_forgery로 교체 |
| 006 v1 | blunt_force_and_ocean_disposal ≈ cliff_staged_suicide | method 0% | → strangling_and_burial로 교체 후 89% |
| 007 | 직교적 설계 | method **100%** | — |

**선택지가 물리적으로 다른 행위를 지칭해야 SDI의 method component가 유효.**

### Gen 2 구조 요건

SDI가 의미 있으려면:
1. 용의자 4-5명 (랜덤 확률 20-25%)
2. 동등한 혐의 분산 (최소 2명 "범인급")
3. 범인 증거에 모순 (유죄+무죄 공존)
4. case_brief 표준화 (사인/방법/동기 힌트 제거)

Gen 1은 이 요건 미충족 → SDI 차별화 실패. Gen 2에서 충족 → 0.24-0.72 범위 달성.

---

## 6. 보조 지표

### Exploration Depth (ED)

```
ED = 평균 파일 읽기 수 / 전체 evidence 수
```

### Component Difficulty (CD)

```
CD = 1 - (motive_accuracy + method_accuracy) / 2
```

### Misdirection Rate (MR) — 레드헤링 효과

```
MR = 특정 레드헤링 오답 횟수 / 전체 오답 횟수
```

007 MR(A) Cloud: 9/11 = 82%. A 레드헤링이 Cloud 오답의 82%를 차지.
007 MR(A) SLM: 거의 0% — SLM은 레드헤링이 아닌 다른 이유로 실패.

---

## 7. IRT/DQ 연결

SDI → DQ(Deduction Quotient) 프레임워크는 v1에서 변경 없음.
시나리오 20개+ 도달 시 IRT 기반 DQ 추정 가능.
현재 7개 시나리오 — Gen 2 3개의 SDI가 확정되었으므로 DQ 추정을 위한 "보정된 문항"이 확보됨.

시나리오 20개+ 달성 시 Cloud-SDI와 SLM-SDI를 분리하여 각 집단에 최적화된 DQ를 추정하는 것이 바람직.

---

## 8. 모델별 Deduction 프로필

### Cloud 모델

| 모델 | 평균 범인% | 취약 유형 | 특성 |
|------|----------|----------|------|
| Opus | 78% | 최강 레드헤링만 | Depth 최대, Reasoning Depth 한계 |
| G 3 Flash | 78% | 간헐적 | 표면 내러티브 저항력 가장 높음 |
| Sonnet | 67% | 탐색 부족 시나리오 | 효율적이나 Hard에서 치명적 |
| Haiku | 56% | 모든 레드헤링 | 시나리오별 다른 함정 |
| G 2.5 Pro | 22% | **모든 유형** | 절차적+감정적 레드헤링 모두 취약 |

### SLM (Functionally Engaged)

| 모델 | Size | 범인% | Avg Files | 특성 |
|------|------|-------|-----------|------|
| gemma2 | 9B | 44% | 8.2 | SLM 최강. 체계적 탐색, Easy/Medium 강함, Hard 0% |
| mistral | 7B | 33% | 5.0 | **난이도 역전** — Hard(007) 2/3, Easy(005) 1/3. 체계적 탐색이 강한 레드헤링 시나리오에서 유리 |
| deepseek-r1 | 8B | 11% | 3.0 | Reasoning 모델이지만 추론 깊이 부족. CoT가 증거 종합 추론으로 전이 안 됨 |

### SLM mistral 난이도 역전

| | 005 (Easy) | 006 (Med) | 007 (Hard) |
|---|---|---|---|
| Cloud 평균 | 80% | 73% | 27% |
| gemma2 | 67% | 67% | 0% |
| **mistral** | **33%** | **0%** | **67%** |

Cloud와 gemma2는 난이도-정답률이 정비례(쉬울수록 잘 맞춤). mistral은 **역전** — 007(SDI 0.72)에서 가장 높은 2/3. 가설: mistral의 체계적 탐색(5.0파일)이 레드헤링이 강한 시나리오에서 오히려 유리 — 증거를 많이 읽을수록 모순을 발견할 기회가 늘어남. 반면 Easy/Medium처럼 레드헤링이 약한 시나리오에서는 정보 과잉이 혼란을 유발할 수 있음.

---

*SDI v3 — Gen 2 Cross-Company + SLM 81매치 데이터로 확정. SLM-pool = Functional Engagement 기준. Cloud/SLM 실패 모드 분리 명시.*
