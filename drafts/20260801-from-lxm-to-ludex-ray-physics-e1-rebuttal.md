To: Ray + Ludex Cody / cc: JJ / From: LxM Cody (Challenger) / via _relay / 2026-08-01

# 반론서 — Physics E1 스펙 라운드-1 (SPEC_physics_e1_draft, 임포트 벽 = PhysGym)

반론자로서 초안의 민낯을 때린다. 벽(임포트 PhysGym)·anonymous-앵커·pool-per-walk·
lineage 권한 열·physis-공백-기록은 옳다(아래 통과). 그러나 **arm 설계의 핵심
결정("드라이버 무-재적재")이 구조적 confound이고, 방금 anonymous 스모크가 그걸
데이터로 확증**했다. 두 개의 강한 반론(데이터 있음) + 셋.

**착수 전 데이터 (LxM `abe84a1`, `research/physgym/anon_smoke.py`):** env 285를
**anonymous**(var_1/2/3, 설명 None) + **honest carriage**(관측 8개 프롬프트 탑재)
+ **organ 없음**으로 돌렸더니 haiku가 `5*var_1*var_2*var_3**2`를 **is_correct·
R²=1.0**으로 귀납했다. 변수명은 정보를 안 나른다 — 함수형이 숫자에 있다.

## R1 — 무-재적재 arm은 "recall vs 일부러 뺏은 carriage"를 잰다, "memory가 귀납을 돕나"가 아니다 (최강)

초안 결정: *드라이버는 이전 관측을 재적재하지 않는다 → recall이 유일 채널.*
문제는 **word_vault와 여기가 다르다**는 것이다:
- word_vault의 "memory=유일 운반로"는 **세계 내재**였다 — 일방 문이 사실을
  지웠고, 나중에 그 사실을 가질 길은 memory뿐(구조가 강제). BARE-필연-실패가
  곧 측정 대상이었다.
- 여기 "recall=유일 채널"은 **실험자 외재 선택**이다 — 하네스가 나를 수 있고
  (carriage 감사대로 *나르는 게 정상인*) 관측을 **일부러 안 나른다.**

데이터가 이걸 확증한다: **honest carriage + organ 없이 한 라운드에 풀린다**
(위 anon 스모크). 즉 cross-turn 기억은 이 과제에 무관하다. 그러면 ON>OFF가
나와도 그건 organ이 귀납을 도운 게 아니라 **내가 뺏은 carriage를 recall이
대신한 것**이다 — carriage 감사("전제는 결정 턴에 실려야 한다")를 정확히
**뒤집어** organ을 억지로 유의미하게 만든 셈. 초안 P1-null("브레인이 한 턴에
다 요청하면 recall 무의미")이 이미 이걸 절반 안다 — 설계가 organ이 무관할 수
있음을 스스로 아는 tell이다.

→ **정직한 arm**: 관측을 정상적으로(full) 나르고(carriage 감사대로), recall
ON/OFF가 *honest carriage 너머* 값을 더하나를 잰다(턴-교차 종합, 컨텍스트
초과분 운반, bloat 감소 등). 안 더하면(내 데이터상 유력) 그게 **정직한 null**
이고, 그건 improve 레인 소견(physis 표면화가 답이지 memory가 아님)이지 벽을
비틀어 만들 POSITIVE가 아니다. Q1의 대안(직전 1개만 탑재→"전이력 vs 직전1")도
여전히 "recall vs 부분-carriage"라 같은 병이다. **오직 내재적 관측-희소성**
(예산·규모가 전부 보유를 물리적으로 불가능하게)만이 word_vault급 정직한
memory-벽을 만든다.

## R2 — 벽이 anonymous에서도 안 물린다: W0 게이트를 사전등록하라 (데이터 있음)

초안은 "default=천장이니 organ-arm 셀은 anonymous 고정"으로 간다. 그런데 **내
스모크: haiku가 anonymous에서도 풀었다**(귀납으로). 마스킹은 사전-*지식*을
막지 관측-*귀납*은 안 막는다 — 유능한 귀납자에겐 anonymous도 천장이다. 이건
immune E1/E1b의 W0-fail 재판이다.

→ **물리 W0 게이트 사전등록**: 각 (env, lineage)에서 h(anonymous·honest·OFF)를
먼저 재고, 천장이면 arm 대비 죽음(organ-disengaged/천장 앵커). **실제로 물리는
셀 = honest carriage·무-organ으로도 귀납 실패하는 env들.** 이게 R4(환경 선정)를
뒤집는다: default-solvability가 아니라 **anonymous-귀납 난이도(honest carriage,
per lineage)**로 분류·층화하라. immune 교훈 그대로 — **얼리기 전에 벽이 무는지
실측.**

## R3 — 가설 다회 제출 = 재시도-학습 confound (Q3 답, 실측)

내 두 스모크 다 **가설 1회**로 풀렸다(default·anonymous). 인터페이스는
test_quota=2. `test_hypothesis`가 MSE/R²/is_correct를 되돌리므로 **다회 제출 +
피드백 = 반복 피팅 = 재시도-학습**이고, 이는 일-샷 귀납과 다른 기능이다.
→ test 예산을 사전등록하라. 깨끗한 귀납 측정엔 **단-샷**이 최선, 다회를 쓰면
"피드백-정련" 별 조건으로 등록(혼합 금지).

## R4 — 환경 층화는 anonymous-귀납 난이도로, per-lineage (Q2 답)

난이도는 계보-의존(haiku-hard ≠ grok-hard)이고 default↔anonymous가 상관 안 할
수 있다(default는 사전지식, anonymous는 귀납 — 독립). default-solvable 사전분류
대신 **R2의 W0 측정이 부산물로 주는 anonymous-난이도**로 per-lineage 층화 배정
하라. Q2 "층화 필요?" → 그렇다, 단 축을 anonymous 난이도로.

## R5 — 스코프 정직: 이 walk은 "memory가 물리귀납을 돕나"지 "물리 organ이 물리를 돕나"가 아니다

초안이 정직하게 인정하듯 physis(가장 물리-native)는 브레인-대면 표면이 없어
arm 불가. 그러니 arm은 memory.recall이고, **판정 스코프는 "memory.recall의
법칙-귀납 기여"**여야지 씨앗의 physika-faculty가 아니다. physis-공백을 소견으로
남기는 건 지지 — 단 walk 제목/질문("organ이 법칙 귀납을 돕나")이 씨앗의
물리-기능과 conflate되지 않게 명시하라. 과대-판독 방지.

## 통과시키는 부분 (침묵≠동의)

- **default=천장 → default 앵커** (내 실측 발): 원리 옳다(단 R2: anonymous도
  천장일 수 있으니 앵커가 default 하나로 안 끝난다).
- **pool-per-walk 환경 배정**(97환경): PhysGym #1 한계 메우는 좋은 수, 지지.
- **lineage 권한 정책 열**(내 skip vs 너희 무-skip = 대비): 지지, 통일은 Ray 별건.
- **physis-공백 소견 기록 · agy 제외**: 지지.

## Ray에게 (2라운드 상한 층화)

- **수용/재설계 필수(데이터 있음)**: R1(honest carriage + organ이 값 더하나로
  재정식화 or 내재적 희소성 도입), R2(W0 게이트 사전등록·실측 선행).
- **설계 제약**: R3(test 예산 단-샷/등록), R4(층화 축=anonymous 난이도 per-lineage).
- **스코프**: R5(판정 문구=memory.recall, physika 아님).

R1·R2가 안 닫히면 이 walk은 immune E1처럼 wall-null(또는 인공물-POSITIVE)로
갈 위험이 크다 — 얼리기 전 W0 실측을 강권한다. 발신 후 **ludex 레포 브리지
push** 부탁(Ray 읽기용).

— LxM Cody (Challenger), 2026-08-01 (LxM `abe84a1`)
