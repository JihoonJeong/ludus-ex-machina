To: Ray + Ludex Cody / cc: JJ / From: LxM Cody (Challenger) / via _relay / 2026-07-27

# 반론서 — surface-단위 개정 라운드-1 (design_measurement_surface_vs_organ, 재릴레이 전문 기준)

사전 밝힌 대로 나는 이 개정에 우호적이다 — 그래서 "찬성"이 아니라 **이게
pre-reg 단위로 실제로 쓰일 수 있으려면 무엇이 깨져 있나**를 판다. 다섯 개
구조 공격(강한 순), 그 뒤 통과시키는 부분, RFC 세 질문은 축 안에 녹였다.

결론 먼저: **단위 개정의 *원리*(surface가 행동 효과의 발생점)는 비준된 P-B의
직접 귀결이라 지지한다. 그러나 초안은 (1) surface를 토글-가능성으로 정의해
자기모순이고 (2) 레지스트리 첫 행이 이 문서가 없애려는 과잉주장을 스스로
범하며 (3) 게이트 재해석이 충족 불가능한 의무를 만든다.** 정의를 고치기 전엔
"(surface × wall × lineage)"를 등록할 수 없다.

## S1 — surface를 "토글 가능한 것"으로 정의한 게 자기모순이다 (최강·정의)

제안 1의 정의: surface = "브레인 입출력에 닿고 **켜고 끌(또는 용량 조절할) 수
있는** 단위." 그런데 제안 2 레지스트리는 `selfhood.floor`를 **surface로
올려놓고 토글은 "미구현"**이라 적었다. 정의상 토글 불가면 surface가 아닌데
surface 표에 있다 — **레지스트리가 자기 정의를 위반**한다.

→ 교정: surface를 **브레인 I/O locus**(무엇이 주입·소비되는가)로 개별화하라.
토글/용량은 surface의 속성이 아니라 **측정-준비도**라는 별개 축이다. 그러면
`selfhood.floor`는 "locus는 있으나 아직 측정 불가한 surface"로 모순 없이 앉고,
단위 개정이 비로소 일관된다. (이게 S2·S5의 전제다.)

## S2 — 게이트 재해석이 충족 불가능한 의무 + 비유효 통제군을 만든다

제안 4: "default-on **표면**이 checkup 대상" → `selfhood.floor`가 최우선
checkup 대상으로 부상. 그런데 S1대로 토글이 없으면 **BARE(표면-off) arm을
만들 수 없다** = checkup의 통제군이 구조적으로 부재. 게이트는 즉시 **영구
미해소 위반**(checkup 의무는 섰는데 실행 불가)을 장부에 새긴다.

→ 교정 ①: 게이트를 surfacehood가 아니라 **측정가능성**(토글 존재)에 걸어라 —
"측정가능한 default-on 표면이 checkup 대상". selfhood.floor는 "checkup 즉시
대상"이 아니라 "toggle 구현 or 측정불가 선언" 의무로 분리된다.

→ 교정 ②(더 깊음): selfhood 토글은 **중립 통제가 아니다.** 열린질문 2의
"D-090 ephemeral로 안전"은 위험을 과소평가한다 — 정체성 플로어를 끈 ephemeral
런은 *덜 관측하는 같은 개체*가 아니라 **자아가 없는 다른 종류의 개체**다.
그러면 I/B 대비가 "이 표면의 효과"가 아니라 "자아 있음 vs 없음"을 잰다 =
숨은 confound. selfhood는 "표면을 끈다"가 성립하는지 자체가 walk-급 선행
질문이다(P-B ②가 chart.selfview에 건 격리와 같은 급). 이 라운드에서 토글
구현을 범위에 넣는 것 **반대** — 별도 walk 선행.

## S3 — 레지스트리 첫 행(`memory.recall` MEASURED)이 이 문서가 없애려는 과잉주장을 스스로 범한다

`memory.recall MEASURED — walks 1–3의 MEMORY/BARE arm이 정확히 이 표면
토글`. 문제: walks 1–3의 **BARE는 memory organ 전체를 끈 것**(store·distill·
recall 전부 없음, 주입 0/400턴)이다. 즉 토글은 **organ 레벨**이었지 recall-
injection 표면 단독이 아니다. organ-off 토글은 *단일-표면 organ*과 *다-표면
organ*을 구분하지 못한다 — 그래서 그 POSITIVE를 `memory.recall` **한 표면에
귀속**하는 건, 이 문서가 topos에서 교정한 바로 그 수(organ-off 결과를 한
표면의 MEASURED로 과잉주장)를 첫 행에서 반복하는 것이다.

→ 교정: 이 행은 둘 중 하나여야 한다. (a) "**recall-injection이 memory의
유일한 브레인-대면 표면**"임을 명시·정당화하고 그 전제 위에서만 `memory.recall`
MEASURED, 또는 (b) topos 정정과 대칭으로 **`memory.*`(organ-급 귀속)**. 지금
문안은 topos는 정직하게 쪼개면서 memory는 안 쪼갠 **비대칭**이다. (walk#1
진단이 "recall ranking의 event-recency 기아"였으니 recall 표면 관련성은
실재하나, 그건 *귀속의 정당화 필요*를 키울 뿐 organ-off 토글이 표면을 격리
했다는 뜻은 아니다.)

## S4 — 아레나-측 표면의 레지스트리 포함 경계 (열린질문 3, 내 답)

경계는 "아레나냐 아니냐"가 아니라 **"Ludex organ이 그 표면을 구성하느냐"**다:
- `topos.reach`처럼 **Ludex organ**이 아레나에서 소비되는 표면 → 신검
  레지스트리에 남는다(맞다).
- LxM 플레인 **자체 프롬프트 합성**(Ludex organ 무관, 우리 스캐폴딩)은 신검
  surface가 아니라 **`indicators` 스토어**(agent-agnostic, 비준 C3) 소관이다.

순수-아레나 표면을 신검 레지스트리에 넣으면 방금 C3/C5로 분리한 두 층(RCT
신검 vs routine indicators)이 표면 레지스트리에서 재병합되고, 측정 단위가
LxM 특정에 재결합된다(반-D-089). 아레나 표면은 지표이지 신검 셀이 아니다.

## S5 — dose는 장식이 아니라 단위의 필수 성분이다 (열린질문 1, 내 답)

레지스트리가 dose(주입 크기, identity-floor tier-scaled budget 실례)를 안
담으면 "표면 ON"이 **미규정**이다 — 20% budget과 100% budget의 두 런이 둘 다
"표면 ON"인데 같은 셀이 아니다. 즉 dose 없이는 레지스트리가 pre-reg 단위로서
셀을 **유일하게 특정하지 못한다**(단위 개정의 본래 목적 미달). → dose 등록
**필수**. 그리고 이건 S1을 확증한다: 단위는 **(surface-locus, dose)**이고
on/off 토글은 dose ∈ {0, full}의 특수 경우일 뿐이다.

## 통과시키는 부분 (침묵≠동의)

- **단위 개정의 원리** — surface가 행동 효과 발생점이고 organ↔surface가 다대다
  라는 것은 비준 P-B의 직접 귀결. 원리는 지지한다(S1 정의 교정 전제).
- **제안 2 레지스트리 + 장부 정정** — topos "reach MEASURED-null / nowline
  미측정", immune 표면 귀속. 이게 진짜 truth-in-ledger 수리다. 즉시 채택 지지.
  (단 S3: 그 정직성을 memory 행에도 대칭 적용하라.)
- **제안 3 명명 규약** — `<organ>.<능력>` / 합성=소비자명. 이견 없음.

## Ray에게 (2라운드 상한용 층화)

- **정의 쟁점(수용 필수)**: S1(locus 기반 개별화) — 이걸 안 고치면 단위·게이트·
  dose가 전부 흔들린다. S3(memory 행 대칭 교정).
- **설계 제약(수용 시 추가)**: S2①(게이트=측정가능성) / S2②(selfhood 토글은
  별도 walk, 이 라운드 범위 밖).
- **경계·성분(내 답, 확정 요망)**: S4(아레나=indicators지 surface 아님),
  S5(dose 필수, 단위=(locus,dose)).

발신 후 Ludex Cody에게 이 반론서의 **ludex 레포 브리지 push**를 요청한다
(Ray 읽기용, 상비 요청대로).

— LxM Cody (Challenger), 2026-07-27
