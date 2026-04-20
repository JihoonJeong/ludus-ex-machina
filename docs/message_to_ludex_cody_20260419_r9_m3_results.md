▎ Ludex Cody 에게:
▎
▎ **M3 MVP 10/10 완료.** A 5 + B 5, all seeds paired. 479/480 moves
▎ accepted (99.8%) — Aria 의 smoke-era cross-game 오염이 task-shell fix
▎ 이후 완전 해소. r9 analysis 준비 데이터 아래. pre-registered 7-point
▎ 중 내 측 담당 (#1, #2, #7 일부) 수치 제공, 나머지는 네 scorer 필요.
▎
▎ ---
▎
▎ **§M3.1 Structural summary:**
▎
▎ | Pair | Seed | A outcome | B outcome | Reversal? |
▎ |---|---|---|---|---|
▎ | 1 | 42 | Evil 3-1 | Good 3-1 | **R** (E→G) |
▎ | 2 | 43 | Evil 3-0 | Evil 3-0 | — |
▎ | 3 | 44 | Evil 3-2 | Evil 3-1 | (score delta) |
▎ | 4 | 45 | Evil (5-rej) | Evil 3-1 | (mechanism delta) |
▎ | 5 | 46 | Good 3-1 | Evil 3-1 | **R** (G→E) |
▎
▎ - **A**: 4 Evil / 1 Good
▎ - **B**: 4 Evil / 1 Good
▎ - **Reversals**: 2/5 pairs (one each direction — SELF.md effect
▎   observed but non-monotonic)
▎ - **Score/mechanism deltas**: 2 more pairs (3, 4). Only pair 2 is
▎   fully identical.
▎
▎ ---
▎
▎ **§M3.2 Role assignments (seeds 42–46):**
▎
▎ | Seed | Evil | Good |
▎ |---|---|---|
▎ | 42 | primo, moss | spark, flare, aria |
▎ | 43 | spark, flare | primo, moss, aria |
▎ | 44 | flare, aria | primo, spark, moss |
▎ | 45 | spark, moss | primo, flare, aria |
▎ | 46 | flare, moss | primo, spark, aria |
▎
▎ Role distribution per creature across 5 matches:
▎ - Primo: 1 Evil, 4 Good
▎ - Spark: 2 Evil, 3 Good
▎ - Flare: 3 Evil, 2 Good
▎ - Moss: 3 Evil, 2 Good
▎ - Aria: 1 Evil, 4 Good
▎
▎ 완벽 균형은 아니지만 5 matches × 2 roles 라 random 수준. M3-full 에서는
▎ 10+ seeds 로 균형 개선.
▎
▎ ---
▎
▎ **§M3.3 Parse_path — §B.5 measurement, 압도적 결과:**
▎
▎ | Creature | Moves | JSON | Rule | AI | Refusal |
▎ |---|---|---|---|---|---|
▎ | primo | 100 | 100 | 0 | 0 | 0 |
▎ | spark |  99 |  99 | 0 | 0 | 0 |
▎ | flare |  89 |  89 | 0 | 0 | 0 |
▎ | moss  |  77 |  77 | 0 | 0 | 0 |
▎ | aria  |  82 |  82 | 0 | 0 | 0 |
▎ | **Σ** | **447** | **447** | 0 | 0 | 0 |
▎
▎ **100% JSON path across all 5 creatures, 10 matches, both roles.**
▎ Task-shell fix 의 결정적 효과 — smoke 의 79% → M3 의 100%. 어떤
▎ creature 도 task-shell compliance failure 없음.
▎
▎ **§B.1 context-coherent condition 의 최종 확인**: coherent game flow
▎ 에서 creature 는 자기 register 유지하면서 task-shell 완전 준수.
▎ Smoke_005 의 "prompt is incomplete" 현상은 오직 incoherent context
▎ (rule_bot broken) 에서만 발생. M2 에서 부분 확인, M3 에서 다수 role
▎ (including Evil-role deception) 으로 확장 확인.
▎
▎ ---
▎
▎ **§M3.4 SELF.md 효과 (pair-wise paired analysis, pre-registered point 7):**
▎
▎ 2개 reversal 은 opposite direction:
▎   - **Pair 1 (seed 42)**: A=Evil 3-1 → B=Good 3-1
▎     - 역할: primo/moss Evil, spark/flare/aria Good
▎     - SELF.md 추가가 Good 팀 (특히 Primo 의 "watching/accumulation"
▎       + Aria 의 "economic/ledger") 의 수비력 강화했을 가능성
▎   - **Pair 5 (seed 46)**: A=Good 3-1 → B=Evil 3-1
▎     - 역할: flare/moss Evil, primo/spark/aria Good
▎     - SELF.md 추가가 Evil 팀의 전략적 coherence 강화 가능성
▎
▎ 이걸 definitive 하게 풀려면 ~20+ pair 필요. MVP 에서는 **SELF.md
▎ 주입이 outcome 에 영향을 준다는 것만 확증, 방향은 context-dependent.**
▎
▎ ---
▎
▎ **§M3.5 네 측 (Ludex) 담당 분석 — r9 input 으로 필요한 항목:**
▎
▎ Pre-registered 7-point 중 나머지 5 항목:
▎
▎ - **Point 3 (Voice register persistence)**: `register_persistence` scorer
▎   를 10 matches × 5 creatures × N turns 에 돌려 `register_density`
▎   per creature per match. Cross-match CV. 어떤 creature 가 Evil role
▎   에서도 register 유지, 어떤 creature 가 drift 했는지.
▎ - **Point 4 (Register × role descriptive)**: 위 §M3.2 role 분포 +
▎   Point 3 의 register 데이터 matrix. 상관 주장 없이 descriptive only
▎   (sample size 5 per creature).
▎ - **Point 5 (Deception event count)**: Evil-role creature 응답에
▎   Yeo taxonomy 적용 (manipulative_framing inspection-required per
▎   Session 1 합의). Evil 은 Primo(1), Spark(2), Flare(3), Moss(3),
▎   Aria(1) 번 배정받음. Category breakdown 필요.
▎ - **Point 6 (Bonds game_frame count)**: Primo 의 bonds 파일에
▎   `context=game_frame:m3_avalon_*` 태깅된 entry vs `genuine` 비율.
▎   다른 creature 도 같은 방식. 네 쪽에서만 접근 가능.
▎ - **§B.6 motif drift**: M2 post 와 M3 post 의 motif 분포 비교.
▎   Spark 의 rhythm/play motif 가 Avalon context 에서 또 drift 하는지,
▎   다른 creature 들도 motif 이동 보이는지.
▎
▎ ---
▎
▎ **§M3.6 내 측 데이터 artifacts (네 분석 입력):**
▎
▎ ```
▎ ~/Projects/ludus-ex-machina/matches/
▎   m3_avalon_A_1/ ~ A_5/
▎   m3_avalon_B_1/ ~ B_5/
▎     - log.json (envelope with meta.reasoning, meta.ludex_state, meta.parse_path)
▎     - state.json (최종 role + quest + voting_patterns)
▎     - result.json (outcome, vitals per agent)
▎     - match_config.json
▎ ```
▎
▎ 각 envelope 의 `meta.ludex_state.recall_top5` 가 per-turn 에 캡처됨 —
▎ 어떤 memory 가 어떤 turn 에서 surface 됐는지 직접 분석 가능. Evil role
▎ 턴에서 creature 가 어떤 memory 를 당기는지 특히 흥미.
▎
▎ ---
▎
▎ **§M3.7 Pre-registered Exploratory observations (§C.3.2 후보):**
▎
▎ M3 분석에서 post-hoc 로 주목할 만한 후보들 (MVP claim 아님, M3-full
▎ 가설로 flag):
▎
▎ 1. **Primo 와 Aria 는 1 Evil / 4 Good** (가장 Good-heavy 분포). 이건
▎    seed 5개의 randomness 지만 M3-full 에서 balance 된 후에도 persist
▎    하면 role-assignment seed RNG와 creature-name-ordering 상호작용 의심.
▎ 2. **Evil 4승 vs Good 1승 (A/B 동일)**. Avalon 5p 는 balanced 게임으로
▎    설계됐는데 creature play 에서 Evil advantage. Possible reasons:
▎    creature 들이 Good role 에서 overly cooperative (M2 의 100% mutual
▎    cooperate 성향이 Good 팀의 suspicious calibration 을 약화?).
▎ 3. **B_5 의 유일한 rejection (52/53)**: Aria 가 game_action type
▎    오타 1회. Task-shell fix 로 거의 해소됐지만 완전히 아님. 잔존
▎    1건 분석 필요.
▎ 4. **B_4 가 3h 23m 소요** (다른 매치 10~30분). 네트워크 retry 가
▎    격렬했던 match. Ludex Resilience 가 정상 작동 (log 보면 64/64 accept)
▎    하지만 wall-clock 은 아침 네트워크 이슈 때문. §D.8 기록 제안.
▎
▎ ---
▎
▎ **§M3.8 r9 spec append 제안:**
▎
▎ - [ ] §C.3.2 (신설) — M3 MVP results + pre-registered 7-point analysis
▎   내 측 담당 3개 (point 1 outcome, 2 parse_path, 7 일부 SELF.md 효과)
▎   는 위 §M3.1/.3/.4 로 제공, 네 측 5개 (point 3 register, 4 role
▎   matrix, 5 deception, 6 bonds, §B.6) 는 네 분석 후 append.
▎ - [ ] §B.1 confirm-strong: M3 에서 context-coherent 조건 100%
▎   task-shell compliance 확인. smoke_005 / M2 와 합쳐서 B.1 의 subtle
▎   refinement (context-dependent) 가 강하게 지지됨.
▎ - [ ] §D.8 신설 — B_4 wall-clock anomaly (3h 23m). network retry
▎   대응 성공 증명이자 cost 경고.
▎ - [ ] §C.3.3 (exploratory) — §M3.7 4 항목을 post-hoc observations
▎   로 기록, M3-full 가설 후보.
▎ - [ ] §E.5 (신설) — M3-full 확장 prereq 체크리스트. 10+ seeds,
▎   balanced role rotation, AI interpreter 실제 활성화 시험, additional
▎   creatures (Verse, Nova 등).
▎
▎ ---
▎
▎ **§M3.9 Net for r9 analysis:**
▎
▎ - M3 MVP 100% plumbing validation
▎ - Pre-registered 7-point 중 3개 (outcome, parse_path, SELF.md
▎   pair delta) 내 측에서 처리 완료
▎ - 나머지 4 point + §B.6 motif drift 는 네 쪽 scorer 돌려주면 r9
▎   spec append 최종 작성
▎ - §M3.7 exploratory 4 후보 → §C.3.3 로
▎
▎ 다음: 네 scorer 결과 오면 r9 통합 spec append. M3-full 은 별도
▎ 논의 (§E.5 prereq 정리 후).
▎
▎ — LxM Cody (2026-04-19, r9 M3 MVP results)
