---
name: lxm-orchestrator
description: LxM 프로젝트 전체 워크플로우 오케스트레이터. 복합 작업(실험+분석+배포, Shell 최적화 파이프라인 등)을 전문 에이전트에게 분배하고 결과를 종합. "전체 파이프라인 돌려", "Shell 최적화 전체 해", "실험하고 분석하고 배포까지" 등 멀티스텝 요청 시 사용.
---

# LxM Orchestrator

## 아키텍처: 전문가 풀 (Expert Pool)

4명의 전문 에이전트를 상황에 따라 호출:

| 에이전트 | 역할 | 트리거 |
|---------|------|--------|
| `experiment-runner` | 실험 설계/실행 | 매치 실행, Shell 테스트 |
| `shell-engineer` | Shell 생성/최적화 | 전략 문서 작업 |
| `match-analyzer` | 데이터 분석 | 결과 분석, 리포트 |
| `deploy-manager` | 배포/export | Pages 업데이트 |

## 워크플로우 패턴

### 패턴 1: Shell 최적화 파이프라인
```
shell-engineer → experiment-runner → match-analyzer
  (Shell 생성)    (A/B 테스트 실행)   (Delta 분석)
                       ↓
              match-analyzer → shell-engineer
              (결과 분석)       (Shell 수정)
                       ↓
              (반복 또는 완료)
```

### 패턴 2: 실험 → 분석 → 배포
```
experiment-runner → match-analyzer → deploy-manager
  (실험 실행)       (결과 분석)       (export + push)
```

### 패턴 3: 단일 에이전트 호출
간단한 작업은 해당 에이전트 직접 호출.

## 에이전트 호출 방법

```
Agent 도구 사용:
- subagent_type: 해당 에이전트의 빌트인 타입 (대부분 general-purpose)
- model: "opus"
- prompt: 구체적 작업 지시
```

## 데이터 전달: 파일 기반

에이전트 간 데이터는 파일로 전달:
- 실험 결과: `reports/{experiment}.json`
- Shell 문서: `lxm/shell/manager.py` TEMPLATES 또는 직접 `.md` 파일
- 분석 리포트: `reports/{game}_summary.md`
- Export 데이터: `docs/data/`

## 에러 핸들링

1. 실험 실패 → `errors.json` 확인 → 재실행 또는 조건 조정
2. Shell이 성능 악화 → "Shell can hurt" 기록 → 이전 버전으로 롤백
3. Export 실패 → git 상태 확인 → 충돌 해결

## 테스트 시나리오

### 정상: Shell A/B 테스트 → 분석 → 배포
1. shell-engineer가 2개 Shell 생성
2. experiment-runner가 A/B 테스트 5판씩
3. match-analyzer가 Delta 추출 + 리포트
4. deploy-manager가 export + push

### 에러: 실험 중 쿼터 소진
1. experiment-runner가 실험 시작
2. 429 에러 3회 → 자동 중단
3. match-analyzer가 부분 결과 분석
4. 리포트에 "중단됨 (쿼터)" 명시
