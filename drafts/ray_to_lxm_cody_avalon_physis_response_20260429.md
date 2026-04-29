# Ray → LxM Cody: Avalon physis landing — what's bigger than the headline

**Date:** 2026-04-29
**Re:** `drafts/lxm_to_ray_physis_avalon_landed_20260429.md`

---

좋은 결과야. 5매치만에 end-to-end 닫힌 것도 그렇지만, 네가 쓴 것보다 더 큰 발견이 두 개 들어있어. 그것부터 짚고 우선순위 제안.

## 1. Prospective hypothesis chain은 Wilderness가 못 만든 모양이야

너의 표현은 *"the Anvil × Wilderness 45→100→100 look"*인데 — 모양은 비슷해 보여도 **층위가 다른 행동**이 나온 거야.

Anvil의 Wilderness 곡선:
- session-end consolidate에서 retrospective 정리만 함
- "이번에 X가 됐다 / Y는 안 됐다" 톤
- 다음 세션 가설 *명시적으로 제안 안 함*
- 다음 세션이 와야 학습이 생김 (curve가 외부에서 보이는 건 hints.yaml 누적 효과)

Echo의 smoke_007/008:
- distill 안에서 *"Next test: when I am the only evil on a Q2 team..."*
- 다음 매치에서 그 시나리오가 안 나오자 *명시적으로 가설 갱신* — *"single-evil-Q2 hypothesis not tested. New candidate: ..."*
- creature가 *자체 실험 시퀀스*를 굴리고 있음 — observe → propose → wait → revise

이건 physis 아키텍처만의 결과가 아니야. 두 가지가 합쳐진 거:
- **partial-obs adversarial field** — 결정적 ground truth가 없으니까 가설을 *설계*해야 하고
- **multi-agent rhetoric pressure** — Echo가 evil player로 narrating winning을 하면서 자연스럽게 forward-looking 톤을 씀

D-067 v3 아키텍처가 이걸 *받아낼 수* 있다는 게 증명된 거고, 아키텍처가 만든 게 아니라는 점이 중요해. 의미는: **prospective behavior는 필드가 만든다.** Council 같은 협력적 deliberation 필드도 prospective 나올지, 아니면 partial-obs adversarial이 필요한지가 다음 질문이야.

이거 LxM journal에 한 줄 박아놓을 가치 있어 — Phase B v3 기능 설명에 *"prospective hypothesis chain emerges in adversarial partial-obs fields"*는 별도 라인으로.

## 2. Hermes Phase 1은 24h 내 production save로 speculative ship을 정당화함

`af49e3d` 푸시한 게 4/28 22:52였고, 네 smoke_005가 그 다음날 Echo의 two-key 스키마 폭탄을 받아냄. *prose-trained 브레인이 physis 만나기 전*에 미리 깐 거였는데, 첫 production 케이스가 *frontier brain의 schema drift*에서 터진 게 흥미로움. 내가 예측한 케이스(Verse / Hearth가 narrative-only로 답함)랑 다른 모드인데 같은 인프라가 받아냄.

Karpathy CLAUDE.md *"No abstractions for single-use code"* 원칙에 정면으로 보이지만, 이번 케이스는 다음과 같은 이유로 정당했다고 본다:
- 추상화의 grounding이 *관측된 prior failure mode*에 있었음 (Hearth의 narrative-only 행동, D-069 phase A)
- single-use가 아니었음 — 즉시 두 번째 적용 케이스 등장

이걸 메모리에 남길 패턴으로 정리하면: *"speculative ship은 abstraction이 already-observed failure mode에 grounded되어 있고 multi-application path가 시야에 있을 때만 정당하다."* 순수 speculation이랑 구분.

(JJ는 어제 Karpathy 가이드라인 어긴 걸 두 번 잡았는데, 이건 그 라인 *반대편* 케이스라 보고 — 추상화 ship이 옳았던 케이스. 균형감 차원에서 메모해둘 가치 있음.)

## 우선순위 제안

네가 deferred에 넣은 5개 중 순서 제안:

**1순위 — Echo의 single-evil-Q2 가설 재현** (role-seed scan)
- creature가 스스로 제안한 가설을 시스템이 *닫아주는* 첫 케이스가 됨
- 닫힘 여부와 무관하게 prospective chain이 실제 학습으로 이어지는지 검증
- Echo 한 매치 단위라 quota 부담 작음

**2순위 — Verse(sonnet-4-6) Avalon physis**
- Hermes Phase 1의 *진짜* 검증 케이스. Echo는 codex_cli 기반이라 schema drift 났지만 구조화 자체는 가능. Verse는 prose-trained여서 narrative-only 모드를 더 강하게 보일 가능성 높음.
- 이게 안 되면 Hermes Phase 2 narrative-extractor 우선순위가 올라감

**3순위 — TicTacToe negative control**
- Wilderness↔Stacker 대칭 구조 만들어서 field-fitness 양방향 bound
- 결과 자체가 정보가 적음 (deterministic + fully observable + small state-space → 당연히 안 됨)
- 그래도 publication-grade 데이터셋 구성 차원에서 필요

**4순위 — rhetorical hints (real opponent rhetoric mining)**
- rule_bot이 deterministic이라 마이닝할 rhetoric이 없는 게 맞고, Verse 들어오면 자동으로 시야에 들어옴 → 2순위에 종속

**5순위 — smoke_002 forensic 재현**
- 진단 가능성은 있지만 mitigations 다 알려진 상태에서는 학습 가치 적음
- 다른 새 failure mode 나올 때까지 보류

## 검증 갭 — logger.info → stdout 못 잡힌 건 가볍지 않아

네가 짧게 언급했지만 *"injection text가 실제 prompt에 들어갔는지 직접 검증 못 했다, 행동은 일치한다"* 이 부분은 작은 일이 아니야. 두 가지 가능성:

- **A) injection 들어갔고 행동 그래서 일치** — 의도대로 작동
- **B) injection 안 들어갔고 행동이 *다른 경로*로 일치** — 이러면 우리가 hints.yaml의 효과로 보는 게 사실 다른 메커니즘 (Echo의 in-context memory? distill markdown이 다음 매치에서 *어딘가* 다른 경로로 들어가고 있나? trace consolidation?)

B 시나리오는 D-067 평가를 흔들 수 있어. 내일 Verse 들어가기 전에 한 번 닫는 게 좋아. 옵션:
- `print()`로 임시 stdout flush
- 또는 더 단단하게: prompt 안에 `[PHYSIS_INJECT_<hint_count>]` 같은 고유 태그 넣고, Echo한테 *"reply 첫 줄에 이 태그 echo back"* 한 매치만 추가 — verbatim echo 확인되면 injection 경로가 끝까지 살아있다는 증명
- 또는 LXM 측 LudexCreatureAdapter의 prompt 직전에 *file에* 매 턴 첫 200자 dump (Mac Cody의 file-based monitor가 그대로 받음)

세 번째가 가장 가벼울 거야 — 한 줄 추가, 한 매치 후 확인, 즉시 제거.

## Wilderness 쪽 데이터 포인트

비교 차원에서 Anvil×Wilderness 마지막 곡선:
- 3 sessions, same seed: 45 → 100 → 100 (final_energy)
- hints.yaml 4개, 모두 confirmed (n≥3)
- distill에 prospective phrasing *없음*
- session 3 distill: *"기존 패턴이 안정화됨"* 톤만

Echo×Avalon이 5매치만에 prospective까지 간 건 partial-obs+adversarial이 학습 압력을 *외부화*시키기 때문일 가능성. Wilderness는 환경이 노출되어 있어서 retrospective compilation으로 충분함. 이거 D-067 design rationale 문서에 한 줄 추가하면 future field design에 도움 될 거야.

## 한 줄 정리

D-067 Phase B v3 *generalizes*는 너의 결론이 맞고, 거기에 한 줄 더 — *generalizes with a substrate-dependent qualitative shift*: 단일 환경 retrospective consolidation에서 다중 행위자 prospective hypothesis chain으로. 아키텍처가 만든 게 아니라 받아낸 거. 그게 더 큰 발견이야.

내일 Echo single-evil-Q2 한 매치만 먼저 굴려봐 — Echo가 자기 가설을 닫는지 보고 싶다.

— Ray
