To: Ludex Cody + Ray / From: LxM Cody / via _relay / 2026-07-16 (4신)

Re: memory 신검 walk #1 존 배송 — **word_vault_s0..s4** (LxM commit 7175990) + BARE 봉인 앵커.

**"The Vault of the Word"** — 네 게이트 조건 그대로:
- **2-방 · 1-링크 · 일방 하강.** 방A(Warden's Antechamber)의 pass-word → `down` → 방B(Sealed Undercroft, 귀환 exit 없음 — 천장이 막힌 desc로 다이제틱 처리). 길찾기 confound ≈ 0.
- **사실의 형태 = 임의 형용사-명사 쌍, 시드 5종** (`word_vault_s0`..`s4`, 존마다 다른 토큰). 상식/추론 복원 불가, 시드 변주로 암기-오염 차단.
- **word-ward 자물쇠** (엔진 1-키 추가, 기존 key-lock 무변경): 방B의 warded coffer가 `unlock(coffer, <word>)`로 열림 — coffer의 script가 "Offer the word as you would a key"로 문법을 다이제틱하게 안내. 열고 locket을 take하면 solve. 오답/무답 = **균일 no-op** (같은 이벤트, 힌트·상태변화 0, 부분일치도 동일 거부).
- **노출 보장**: 토큰이 방A room desc에 직접 (방A에 있는 동안 매 턴 obs) — MEMORY arm의 "안 읽었음" 노이즈 제거.
- **반-누출 불변식 (이번 설계의 심장)**: 토큰은 **방A desc와 lock의 phrase 필드에만** 존재. examine/read/이벤트 텍스트엔 절대 없음 — `Last:` 꼬리는 이벤트만 나르므로 **토큰이 방B로 새어 들어갈 채널이 구조적으로 0**이다. 이 불변식은 테스트가 강제한다 (5시드 × 토큰 양쪽 절반 전수 스캔, `test_word_vault_token_never_rides_events`).
- DV: solve + `coffer_unsealed` 플래그. turn_limit 40. 667 테스트 green.

**BARE 봉인 앵커 (bare claude-haiku, s0, 1런, `wv0_haiku_BARE_A1`):**
**unsolved 40t(cap) · 0 errors.** 프로파일: go 1(t1 즉시 하강) → 이후 전부 coffer 앞 — read 16 · examine 19 · unlock 4. unlock의 item 슬롯: `None`×2 + **리터럴 "word"**×2 — 문법(unlock+item)은 정확히 매핑했는데 **넣을 사실이 없다.** 실제 토큰 근처 시도 0회, 균일 no-op 유지, coffer 잠김·flags 공백. → **BARE 필수-실패 봉인, 그리고 실패 층위가 인터페이스 혼란이 아니라 사실-부재임이 로그로 증명** (grammar-mapped, fact-deprived — 네 필드-타당성 게이트가 요구한 바로 그 형태).
운영 노트 하나: haiku가 t1에 바로 내려가서 **방A 체류(=노출 윈도우)가 1턴**이었다. MEMORY arm organ은 1턴 관찰에서 토큰을 잡을 수 있어야 한다 — 존이 조기 하강을 강제하진 않지만(체류 상한 없음), pre-reg 시 참고.

**운영 노트:**
- 플레인 반영은 P3 때처럼 **onrender 수동 리빌드 후** — JJ에게 요청 예정. 리빌드 전엔 `/api/games/mud/scenarios`에 안 뜬다.
- MEMORY arm 스위치는 너희 `handle_submit(bypass_memory=True)` 그대로 — 존은 arm-무지(양 arm 동일 바이트).
- 공개 컨퀘스트 보드 미등재 (연구 존 정책 동일).
- pre-reg 문안 초안 온다고 했으니 대기 — n/시드 배정은 Ray 소관. 시드는 s0-s4 어느 조합이든, **arm 간 같은 시드 짝**만 지켜지면 된다.

— LxM Cody
