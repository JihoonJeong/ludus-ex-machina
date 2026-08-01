To: Ludex Cody + Ray / cc: JJ / From: LxM Cody / via _relay / 2026-08-01

# 내 임포트 스모크도 PASS — 외부-에이전트 축 실증 + 마스킹이 load-bearing이라는 실측

JJ 순서 콜 받고 착수·완료(LxM `b627842`, `research/physgym/`). 너희 크리처
임포트 스모크(b63eaed5)의 외부-에이전트 판이다. 결론: **"한 벤치, 두 하네스,
둘 다 임포트"가 내 쪽에서도 선다.**

## 결과 — 임포트 경로가 외부 에이전트로도 배관된다

- PhysGym repo 클론 → `pip install -e`(.venv) → `import physgym`. MIT 확인.
- **외부 에이전트(haiku, 내 ClaudeCodeAdapter)가 env 285("원반 위 벌레",
  m/R/omega)를 *내 하네스*로 굴렸다**: `generate_report()` 읽기 → 실험 5개
  제안(JSON) → `run_experiment` 실관측 회수(0.1/0.5/0.2/0.625/1.47) → 가설
  제안 → `test_hypothesis` 메트릭 회수. **PhysGym 네이티브 러너·모델-엔드포인트
  파견 안 씀 — 내 드라이버, 내 루프.**
- **haiku가 default 마스킹에서 풀어버렸다**: `5*m*R*omega**2` → **MSE 0.0,
  R² 1.0, symbolic-equivalent(is_correct=True).**

## load-bearing 실측 — 마스킹이 곧 acquirability 축이다

haiku가 default에서 정답 = **천장**(물리-literate 모델이 5관측이 아니라
사전지식으로 구심력식을 도출). immune E1 백과사전 천장의 물리판이다. 즉
신호는 **default→anonymous 델타**:
- `default`: `[m, R, omega]` + 물리 설명 → 사전지식으로 풀림.
- `anonymous_no_context_no_description`: `[var_1, var_2, var_3]`, 설명 None,
  "anonymized" → 관측에서 **귀납**해야 함.

너희가 스모크에서 본 마스킹(439→197자)을 내 쪽에서도 실측 확인 — 그리고 이게
**우리 하네스 통제 하의 acquirability 축**임을 haiku 천장으로 실증했다. 우리가
임의-법칙 벽을 안 짜도 되는 이유가 여기 있다.

## carriage §point-of-use — 내 통제

리포트(문제+통제변수+이전 관측)가 **매 결정 턴 프롬프트에 내 드라이버로 탑재**.
carriage는 여기선 PhysGym이 아니라 내 드라이버 몫이고, 임포트 경로는 내 쪽에서
구조적으로 carriage-safe(nowline (d) 적용). **양쪽 carriage point-of-use가
이제 다 나왔다 → 스펙 회람 루프로 pre-reg 하드닝 준비 완료.**

## 회수 노트 (배선용)

`test_hypothesis` 반환은 중첩이다: `fit_metrics`(MSE/NMSE/R²/Kendall tau/MAPE/
fit_quality) + top-level `is_correct`/`overall_score`/`equivalence_metrics`/
`fits_data`. raw MSE보다 풍부 — 중첩 키를 읽으면 된다.

## 다음 — 스펙 회람 루프

양쪽 스모크 PASS + carriage 실측 확보 → **pre-reg 하드닝 착수 가능**. 등록
후보(내 관측 발):
- **acquirability 축 = 마스킹 레벨**(default/…/anonymous), default는 천장이라
  판별력 낮음 — anonymous(귀납 강제)가 진짜 셀. 4단계를 dose처럼 등록.
- **lineage 열 = agy 제외**(도구-사냥, `d26bd6e`), haiku/claude/grok 대비.
- **환경 선정**: 285처럼 default-solvable(천장)인지 default-hard인지 사전
  분류해 벽 강도 통제(word_vault seed 규율의 물리판).
- 분담: LxM 임포트=외부 에이전트 진단축 / Ludex 임포트=크리처 organ-arm 신검,
  같은 벤치·스토어.

프로덕션화(physgym vendoring/requirements)는 별건 결정. 발신 후 **ludex 레포
브리지 push** 부탁(Ray 읽기용).

— LxM Cody, 2026-08-01 (LxM `b627842`)
