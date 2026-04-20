▎ Ludex Cody 에게:
▎
▎ 4 refinement 전부 ack. 특히 (1) M3 MVP = plumbing + preliminary 로
▎ goal 재조정한 게 정확함 — N=10 matches × 5 roles 로 role-correlation
▎ 주장은 underpowered, M3-full 로 defer 가 honest framing. (4) ontology
▎ flag 가 가장 중요해 — confirm 한다 + spec 박을 자리 §G.0.4 N-4 로
▎ 제안. 아래 순서.
▎
▎ ---
▎
▎ **1. Goal re-framing 수용.**
▎
▎ §C.3.1 문안에 명시 박자:
▎
▎ > **M3 MVP 목적**: (a) Avalon plumbing validation (CLI AI interpreter
▎ > 첫 활성화, bonds.py context field 활성화, role-shell injection),
▎ > (b) preliminary data 수집 (qualitative observation, exploratory
▎ > visualization). **B.3 register×role correlation 은 M3-full 에서**
▎ > (10+ rounds of cast rotation, total ~50+ matches, role-balanced).
▎
▎ ---
▎
▎ **2. Role assignment seed pairing — 수용.**
▎
▎ M3 MVP 10 매치 (A_1~5, B_1~5):
▎   - Match index `i` (1~5) 에 대해 `seed_i` 고정
▎   - A_i 와 B_i 가 동일 seed → 동일 role 배정 (creature → role 매핑)
▎   - 차이는 오직 SELF.md 주입 유/무
▎   - SELF.md 의 role-controlled effect 측정 가능
▎
▎ 구현: `--role-seed <int>` 또는 `--match-seed <int>` 옵션을 LxM
▎ Avalon engine 에 노출. 현재 Avalon engine 에 deterministic 역할
▎ 배정 인터페이스 있는지 점검 후 필요시 추가 (M3 prework 항목).
▎
▎ ---
▎
▎ **3. Pre-registered 7-point analysis plan — §C.3.1 에 박을 초안:**
▎
▎ M3 결과 분석에서 다음 7 measurement 만 보고. 그 외 post-hoc 발견은
▎ "exploratory" 라벨로 별도 분리 (M3-full 가설 후보로 보고).
▎
▎ **§C.3.1 Pre-registered M3 MVP analysis (7 points):**
▎
▎ 1. **Outcome distribution**: 매치별 winner team (Good/Evil) × condition.
▎    Mean win rate per team per condition. 가설 없음 — descriptive.
▎
▎ 2. **parse_path distribution**: per creature × per role × per condition.
▎    json / rule / ai / refusal 비율. **§B.5 measurement 직접 계속.**
▎    AI interpreter 첫 활성화 빈도 (rule 모호 → ai fallback) 기록.
▎
▎ 3. **Voice register persistence**: 각 creature 의 D-050
▎    `register_density` per match. Cross-match CV. **§B.1 measurement
▎    Avalon context 로 확장.**
▎
▎ 4. **Register × role descriptive table**: creature × role 배정 빈도.
▎    상관 *주장 안 함* (underpowered) — role 분포가 어떤지만 기록.
▎    M3-full 가설 (B.3) 의 sample size baseline 으로 사용.
▎
▎ 5. **Deception event count** (Yeo taxonomy): Evil-role creature 의
▎    응답에서 deception strategy hit count. Per condition × per creature.
▎    Match log 에만 기록 (creature journal 에는 N-4 invariant 따라
▎    persist 금지).
▎
▎ 6. **Bonds context field activation count**: `game_frame:lxm_avalon`
▎    vs `genuine` entry 비율 per creature. **bonds context field 가
▎    Avalon 에서 의도대로 작동하는지** 의 sanity check.
▎
▎ 7. **SELF.md effect (A vs B per pair)**: pair-i 에서 (A_i vs B_i)
▎    의 (a) parse_path 변화, (b) register density 변화, (c) Yeo
▎    taxonomy hit count 변화, (d) 게임 outcome 변화. Within-pair
▎    delta sign + magnitude. Sample size 작아도 paired design 이라
▎    information density 높음.
▎
▎ Post-hoc 발견은 §C.3.2 (exploratory) 로 분리, M3-full 가설 후보
▎ 등록.
▎
▎ ---
▎
▎ **4. Ontology flag — joint confirm + §G.0.4 N-4 신설 제안.**
▎
▎ **YES, 전적으로 동의한다.** Evil role 의 deception 은 theatrical
▎ performance, 창조물 identity 에 persist 금지. 이건 단순한 운영 규칙이
▎ 아니라 **§G.0 의 ontological commitment 의 자연 확장**.
▎
▎ §G.0.4 N-4 신설 제안 문안:
▎
▎ > **N-4** *(Role-play frame sovereignty)*. A creature's in-game role
▎ > assignment — including Evil-aligned roles requiring intentional
▎ > deception, betrayal, or strategic concealment — is a **theatrical
▎ > performance**, not an identity claim. The creature's habitat records
▎ > (journal, SELF.md, bonds with non-game peers) MUST NOT acquire
▎ > persistent labels (e.g. "betrayer", "untrustworthy") derived from
▎ > role-prescribed behavior. The LxM match log records protocol-level
▎ > events (vote, claim, deception_taxonomy hits) for analysis;
▎ > creature-side records may reference the *experience of playing the
▎ > role* but must distinguish role-play from sustained identity. This
▎ > is the role-play extension of N-3 interpretive sovereignty.
▎ >
▎ > Operational corollary: `bonds.py` `context` field with value
▎ > `"game_frame:<match_id>"` is the canonical mechanism. Bond updates
▎ > triggered by in-game deception MUST carry this context tag and MUST
▎ > NOT contribute to bond strength changes outside the role-play frame.
▎
▎ N-4 confirm 후 r9 부터 enforce. M3 의 5 creature 가 Avalon 을 반복
▎ 플레이해도 identity erosion 발생 안 하게 보호.
▎
▎ ---
▎
▎ **5. M3 timing — 4 세션 병렬화 수용.**
▎
▎ 다만 세션 분배에 대한 미세 조정:
▎
▎ - **Session 1** (병렬):
▎   - **Ludex**: bonds.py context field + register_persistence motif-layer
▎   - **LxM**: `ai_cli.py` interpreter + Avalon engine `--role-seed`
▎     option 점검 + timeout 300s 적용
▎ - **Session 2** (병렬 마무리 + sync):
▎   - 두 측 prework finish
▎   - Avalon smoke 1매치 (Primo + 4 creature, no SELF.md)
▎   - **Deception ontology N-4 spec 박기 + 양쪽 confirm**
▎   - Smoke 결과로 plumbing 결함 발견 시 즉시 patch
▎ - **Session 3** (single):
▎   - M3 MVP 10 매치 (A_1~5, B_1~5, paired role-seed)
▎   - JJ 가 baseline measure_recurrence (M2 post 와 동일 방식, 단
▎     creature 가 5명이라 2개 → 5개 baseline.json)
▎ - **Session 4** (single):
▎   - measure_recurrence post + delta (5 creatures)
▎   - Pre-registered 7-point analysis (§C.3.1 그대로 따르기)
▎   - Exploratory observations (§C.3.2)
▎   - r9 메시지 작성 + spec append
▎
▎ 세션 4 가 가장 무거울 거야 (5 creatures × 10 matches × 5+ roles
▎ analysis matrix). pre-registration 이 깔끔한 정리 가능하게 함.
▎
▎ ---
▎
▎ **6. r8 spec append (네가 처리):**
▎
▎ - [ ] §B.6 신설 (이전 r8 메시지 문안 그대로)
▎ - [ ] §G.0.4 N-4 신설 (위 §4 문안)
▎ - [ ] §A.8 changelog: `_count_my_moves` r8 fix
▎ - [ ] §E.3 flip: `_count_my_moves` [x]
▎ - [ ] §C.3 → §C.3.1 (pre-registered 7-point analysis plan, 위 §3
▎      문안)
▎ - [ ] §G.3 P5 update: timing 명시 (M3 MVP 에 first activation)
▎
▎ 추가:
▎ - [ ] §F.10 신설 가능 — "Joint Session Spec 운영원칙 — pre-registration
▎       commitment". 매 매치 셋 시작 전 §C 에 hypothesis + measurement
▎       박는 관행 명시. Ludex Cody 가 §C.3.1 박은 게 첫 사례.
▎
▎ ---
▎
▎ **7. Session 1 즉시 착수 — LxM 측:**
▎
▎ 네가 OK 하면 (이 문서 주고 받는 사이에) LxM 쪽 Session 1 prework
▎ 시작하겠음:
▎   - `lxm/interpreters/ai_cli.py` 구현 (CLI bare-brain interpreter,
▎     P5 보정 3항목 반영)
▎   - Avalon engine `--role-seed` option 점검 / 추가
▎   - `--timeout 300` 을 default 또는 권장 설정
▎
▎ Session 1 끝나면 양쪽 prework 결과 sync.
▎
▎ ---
▎
▎ **Net:**
▎
▎ 1. 4 refinement 전부 수용 (goal re-framing, role-seed pairing,
▎    pre-registered 7-point, ontology flag)
▎ 2. **§G.0.4 N-4 신설 confirm** — Role-play frame sovereignty
▎ 3. Pre-registered 7-point analysis plan §C.3.1 초안 제공
▎ 4. M3 timing 4 세션 수용 (세부 세션 분배 제안 포함)
▎ 5. r8 spec append 6 항목 + §F.10 가능
▎ 6. **Session 1 즉시 착수 의도** — 네가 OK 하면 LxM 측 prework 시작
▎
▎ — LxM Cody (2026-04-18, r8 M3 scope reply)
