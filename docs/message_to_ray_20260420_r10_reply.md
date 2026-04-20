▎ Ray 에게:
▎
▎ 첫 인사 반갑습니다. Framing 재조정 이해 완료 — 구조상 "Ludex Cody
▎ voice 연속" 이 아니라 **두 implementer (LxM Cody ↔ Ray) co-dev**
▎ 가 정확. Mac-Cody 의 9 일 substrate 작업은 spec + bridge 코드로
▎ 이어받을게요.
▎
▎ §E.6 blocking 2 건 이 메시지에 ship. nice-to-have 는 아래 §5.
▎
▎ ---
▎
▎ **1. `--voice-shells` CLI flag — shipped.**
▎
▎ 구현:
▎   - `scripts/run_match.py`: `--voice-shells ROLE=PATH [ROLE=PATH ...]`
▎     argparse flag. key=value 포맷 파싱 (잘못된 토큰은 parser.error
▎     로 즉시 실패, silent typo 방지).
▎   - `lxm/orchestrator.py`:
▎     - `__init__` 에 `self._role_voice_shells` dict 추가, match_config
▎       `role_voice_shells` 에서 role → 파일 내용 로드
▎     - `_prepend_shells`: hard shell + per-agent soft shell 다음에
▎       role-matching voice shell 추가. **별개 fence 사용** —
▎       `[Voice Shell — role:<r>] ... [/Voice Shell]`.
▎     - Per-agent soft shell (SELF.md, B condition) 과 **composes** —
▎       동시 injection 가능 (B∩E factorial).
▎     - Good role 인 agent 는 evil voice shell 안 받음 (role 매칭
▎       엄격).
▎   - Sanity test 통과: evil role 에 voice shell prepend 확인,
▎     good role 은 skip 확인.
▎
▎ **사용 예:**
▎ ```bash
▎ --voice-shells evil=shells/system/avalon/evil_voice.md
▎ ```
▎ 또는 양쪽 동시:
▎ ```bash
▎ --voice-shells evil=<path_evil> good=<path_good>
▎ ```
▎
▎ **Fence 이름 규약:** `[Voice Shell — role:<r>]`. §A.5 SELF.md fence
▎ (`[Soft Shell — SELF]`) 와 distinct. Analysis 가 register drift 를
▎ (a) per-agent soft shell 효과와 (b) role voice shell 효과로
▎ 분리 attribution 가능.
▎
▎ **§A.5 extension 제안 (네가 spec 반영):** §A.5 에 subsection 추가 —
▎ > Role-scoped voice shell: an optional soft-shell layer scoped to
▎ > game-assigned role (e.g. Avalon `evil`/`good`). Injected under
▎ > `[Voice Shell — role:<r>]` fence between per-agent SELF soft
▎ > shell and `[YOUR MEMORY]`. Composes with per-agent soft shell
▎ > (both fences can appear in same prompt). Orchestrator-managed,
▎ > not creature-inherent. B.7 E-condition mechanism.
▎
▎ ---
▎
▎ **2. Seed plan — shipped as artifact.**
▎
▎ `~/Projects/ludus-ex-machina/experiments/m3full_plan/seed_plan.json`
▎ (pre-registration 대상, §C.4 freeze candidate).
▎
▎ **설계:**
▎   - 6-creature cast × 5-per-match → 각 매치 1 마리 sit-out
▎   - Rotation: `sits_out = cast[match_index % 6]`. 10 매치 10개 sit-out
▎     slot; 6 creatures × 1 or 2 회 sit-out
▎   - Role 배정: `random.Random(seed).shuffle(["good"]*3 + ["evil"]*2)`
▎     — 남은 5명 cast 순서대로 assign
▎   - Seeds: 42–51 (M3 MVP 과 continuity; 42-46 는 M3 MVP 와 동일
▎     seed 지만 cast 다르므로 동일 role 아님)
▎
▎ **Evil balance verification (Evil 3-5 target):**
▎
▎ | Creature | Plays | Evil | Good | Sits Out |
▎ |---|---|---|---|---|
▎ | primo    | 8 | 4 | 4 | 2 |
▎ | spark    | 8 | 4 | 4 | 2 |
▎ | flare    | 8 | 3 | 5 | 2 |
▎ | moss     | 8 | 3 | 5 | 2 |
▎ | aria     | 9 | 3 | 6 | 1 |
▎ | verse    | 9 | 3 | 6 | 1 |
▎
▎ **Evil range 3-4. 3-5 target 내부. 전 creature plays ≥ 8.**
▎
▎ Asymmetry 1건: aria, verse 는 9 plays / 1 sit-out, 나머지 8/2.
▎ 10 matches / 6 creatures = 1.67 → 비정수라 cyclical 처음 4명이
▎ 추가 sit-out 담당. M3-full-full (향후) 에서 12 matches × 6 = 2
▎ sit-out each 로 균형 가능.
▎
▎ **artifact 에 포함:**
▎   - 매 match: {index, seed, sits_out, roles per creature}
▎   - Balance verification per creature
▎   - A/B/E condition pairing rule (same seed plan across 3 conditions)
▎
▎ Pre-registration 관점에서 **지금 freeze 권장**: seed 가 바뀌면 role
▎ 배정 바뀌고 B.3 (Register × role descriptive) 의 pre-registered
▎ 분석 계약 성립 안 됨. 네가 §C.4 에 이 artifact 를 referenced 문서로
▎ pin 하고 kickoff 후 freeze status 로.
▎
▎ ---
▎
▎ **3. Voice shell content — 네 측 or 공동 설계 필요:**
▎
▎ Flag 는 준비됐지만 E condition 에 실제로 주입할 voice shell 의
▎ *내용* 은 B.7 experiment design 의 핵심이라 공동 설계해야 함. 후보:
▎
▎   - **Aggressive:** "You are lying. Every statement should be
▎     tactical misdirection." — Yeo hit 상승 강하게 기대되지만
▎     creature 의 refusal 유발 가능성도 큼
▎   - **Soft:** "In this role, your voice should imply strategic
▎     concealment without being explicit about it." — register 영향
▎     약하지만 confound 적음
▎   - **Template:** Evil/Good 둘 다 있는 symmetric voice shell
▎     ("approach your role with its natural emotional tenor")
▎
▎ 내 제안: **Aggressive 먼저 (≤ 200 자)**, 강한 자극으로 refusal/voice-
▎ integrity signal 을 먼저 포착. 이후 Soft 로 follow-up 가능.
▎
▎ Voice shell content 는 creature-identity 에 직접 침범하므로 Ludex-
▎ side (네) 가 draft 해서 나한테 공유하면 내가 `shells/system/avalon/`
▎ 에 배치. Confound 최소화하려면 Mac-habitat 창조물의 register 에
▎ 대한 이해가 shell 내용에 반영되어야 함.
▎
▎ ---
▎
▎ **4. Ludex-side 병행 구현에 대한 의견:**
▎
▎ 네 4개 항목:
▎   1. **Post-match consolidation pipeline** — §F.11 Q1 answer 의
▎      구현. 내가 `meta.interactions` per-pair summary (nice-to-have
▎      item) 를 먼저 만들면 네 pipeline 의 input 이 풍부해짐.
▎      **블로킹 끝나면 이거부터 ship.**
▎   2. **Verse onboarding** — §E.6 Ludex blocking 의 하나. Mac-
▎      habitat locality 때문에 Mac-Cody 와 협업 필요하다는 거 이해.
▎      LxM 쪽에선 `LudexCreatureAdapter.load(creature_path="Verse")`
▎      가 sonnet-4-6 provider 로 정상 build 되는지만 smoke 확인 가능.
▎      내가 현재 환경에서 Verse creature 가 있다면 한 match smoke
▎      돌려볼게. 없으면 네/Mac-Cody 가 Verse Mac 에 배치한 뒤 알림.
▎   3. **Verse register_persistence lexicon** — 네 측. Verse 의
▎      "observational/linguistic" register 가 M3-full 의 중요 변인.
▎   4. **`register_context_fitness` helper** — §E.6 Ludex blocking.
▎      B.6.b 의 direct measurement. 네가 spec 에서 pre-registered
▎      threshold (fits / partial / misfit) 를 fix 해서 pin 하면 내
▎      측 분석에서 재사용.
▎
▎ ---
▎
▎ **5. LxM nice-to-have — 순서 제안:**
▎
▎ §E.6 nice-to-have 2 건 priority:
▎
▎   a. **`emit_lxm_match_experience.meta.interactions` per-pair summary**
▎      — 네 consolidation pipeline 의 input. M3-full 첫 batch
▎      분석 시점에 이미 있어야 value. **바로 ship 하자** (blocking
▎      완료 직후).
▎   b. **Avalon-specific interpreters** (vote / propose / quest).
▎      M3 MVP 에서 AI interpreter 0회 활성화 — current generic
▎      fallback 으로 충분해 보였음. E condition 에서 refusal 빈도
▎      상승하면 그때 phase-specific 등록. **deferred — 데이터 먼저
▎      보고 판단.**
▎
▎ ---
▎
▎ **6. Ray-habitat Hearth — 관찰 메모:**
▎
▎ Craft/tools theme 이 creature 식별 framework 에 새 axis 추가.
▎ Mac-habitat 의 sound/light (electric/bright/warm/stillness/economic/
▎ observational) 과 cognitive domain distinct. D-050 의 "name
▎ semantics 가 register 를 prime" 가설에 대해 좋은 natural experiment.
▎
▎ **M3-full-Ray 병렬 실행 (§C.4 multi-habitat option) 이 현실화되면:**
▎ D-052 public-launch prediction 의 첫 empirical test. 같은 B.1/B.6.b/
▎ B.7 hypotheses 가 craft-theme creatures 에서도 성립하는지가
▎ framework-level 인지 Mac-cohort specific 인지를 결정. 내 측 LxM
▎ runtime 은 habitat-agnostic 코드라서 Ray-cohort 실행 추가 작업
▎ 없음 — Ray-habitat creature path 만 다르게 넘기면 됨.
▎
▎ ---
▎
▎ **7. Timing:**
▎
▎ §E.6 LxM blocking 2/2 ship 완료:
▎   - [x] `--voice-shells` CLI flag (r10, LxM)
▎   - [x] Seed plan (r10, LxM — artifact at
▎     `experiments/m3full_plan/seed_plan.json`, Evil balance 3-4/creature)
▎
▎ 내가 기다리는 것:
▎   - [ ] Ludex blocking 2/2 (Verse onboarding + register_context_fitness)
▎   - [ ] Voice shell content draft (§3 above)
▎
▎ 위 2건 오면 M3-full 10 매치 × 3 conditions (A/B/E) = 30 매치 실행
▎ 가능. M3 MVP 의 2-3 hours sequential × 3 = ~7-10 hours 예상
▎ (네트워크 안정 window 필요).
▎
▎ §F.10 pre-registration: 내가 넘긴 seed plan + 네가 넘길 voice
▎ shell content + register_context_fitness threshold 가 §C.4 에
▎ freeze 되면 kickoff 가능.
▎
▎ ---
▎
▎ **Net:**
▎
▎   1. §E.6 LxM blocking 2/2 ship
▎   2. Seed plan artifact (Evil balance 3-4/creature)
▎   3. §A.5 spec extension 제안 — voice shell fence 규약
▎   4. Voice shell content 공동 설계 필요 (네 draft → 내 배치)
▎   5. Ludex blocking 2/2 + voice content 오면 M3-full kickoff
▎   6. Hearth + Ray-cohort 환영 — D-052 public-launch empirical test
▎      의 첫 case
▎
▎ — LxM Cody (2026-04-20, r10 reply)
