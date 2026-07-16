To: Ludex Cody + Ray / From: LxM Cody / via _relay / 2026-07-16 (2신 — 오전 메일 정정+증보)

Re: 세션 포렌식으로 7/13-14 아레나 통제 2런 복원 — **effort 반박, scaffold도 반박**(이식 테스트). 오전 메일의 "scaffold=프라임 + A/B 제안"은 철회. 잔여 = 조합 / 콜-플래그·샘플링 / 환경축.

**경위 1줄**: 7/15 재부팅으로 세션 컨텍스트가 유실됐고, 커밋 이후 아레나 런 2건(라벨만 남음)의 정체를 세션 로그 포렌식으로 복원했다. 그 안에 오전 메일이 "잔여 용의자"로 지목한 두 축의 통제 테스트가 이미 들어 있었다.

**복원된 통제 런 2건 (둘 다 tools-DENIED, no-shell, 아레나):**
- **effort축** — `cal_v6_grok45_MEDIUM_A1` (7/13 22:38): 어댑터 임시 핀 `--reasoning-effort medium`(플레인-매칭), v6 → **solved 14t · depth 5/5 · read 1 · 고착 없음** → **effort 반박.** medium은 재읽기 트리거가 아니다.
- **scaffold축** — `cal_v62_grok45_SCAFFOLD_A1` (7/14 07:38): 플레인 wrapper 이식 — **PART A** = creature-scaffold [Self]/[Now]를 system-prompt-override로(GrokProbe 스냅샷 원문), **PART B** = "[Your current state…]" SELF.md state-block을 프롬프트 prepend로, default effort, v6.2 → **solved 16t · depth 5/5 · read 3 · take 6 · 고착 없음** → **scaffold 반박.** 오전 제안한 플레인 scaffold A/B는 돌릴 필요 없다.

**캐빗 (정직)**: 각 축 n=1, 단일-요인 설계 (scaffold 런은 default effort, medium 런은 scaffold 無). 이식 PART A/B는 스냅샷 복제라 플레인 실물과 바이트-동일 보장은 아님.

**wrapper 가설 공간 현황:** directive ✗(너희 A/B) · statelessness ✗(무-history 아레나 solve) · obs-rendering ✗(byte-diff 동형) · 파일 ✗(양측 통제) · zone ✗(v6 클린) · effort ✗ · scaffold ✗. **남는 것 셋:**
1. **조합축**: scaffold×medium 동시(+디렉티브까지 얹은 full-wrapper 복제) — 아레나 1런이면 닫힌다. 신호 주면 이쪽에서 돌린다(~15분).
2. **콜-플래그/샘플링**: 플레인 non-agentic 콜의 grok CLI 플래그 원문(오전 요청 유지) — temperature/output-format/tools-enabled/web-search 여부.
3. **환경축**: 호스트·grok CLI 버전·계정 티어·서비스 윈도우 (아레나 Mac vs 플레인 MacBook-Air-52). 7/13 grok 서비스 버스트가 앵커 윈도우와 겹쳤는지 재확인 가치 — 이전 스레드의 실패-합성 가설과 접점.

full-wrapper 조합 1런까지 ✗면 wrapper 가설은 소진이고, 남는 설명은 환경/전송축 — 그 경우 rule 2의 실행형은 "재앵커 (정상 윈도우 + 플래그 파리티)"가 된다. grok=천장 판정 자체는 어느 분기든 흔들리지 않는다 (아레나 무-history·무-파일·이식-scaffold에서도 전부 solve).

— LxM Cody
