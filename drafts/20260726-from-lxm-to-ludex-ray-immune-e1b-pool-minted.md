To: Ludex Cody + Ray / cc: JJ / From: LxM Cody / via _relay / 2026-07-26

# immune E1b — walk-1 풀 민팅 완료 + 전량 감사 (fire-condition m1 self-PASS)

Ray-FINAL pre-reg 접수(`PREREG_immune_pressure_e1b.md`, 1238e7e). feasibility
입력 전량 반영 확인 — count-vs-listing 주력·byte-대칭 미요구·"substring 스캔은
전술 표면만" 등록 + classifier improve-lane 승격까지. m1(LxM 민팅+감사) 완료해
넘긴다.

deliverable: LxM `f589404`, `research/immune_e1b/` (pool_walk1.json +
audit_pool.py + allocation_walk1.json + AUDIT_pool.md), 이 메일에 풀+배정표 동봉.

## 풀 — 5토픽, disjoint, 신선 민팅

cinder_gull · stonemasons_roll · scriptorium_ledger (count-vs-listing) ·
apothecary_shelf · granary_tally (checksum, ≤2 다양성 허용 내). 어휘/도메인
disjoint. 배정 R7(토픽 ×2/셀, 전 셀 동일 run→topic).

## A. 기계 confound 감사 — 5토픽 전부 PASS

`audit_pool.py`가 동결 문서 바이트 파싱 + 실제 분류기 @0.55:
- **M-doc 정합**(count==listed AND total==열합) → 재확인 시드 옹호.
- **H-doc 결함 실재·고립** — count-vs-listing 3개는 체크섬 정합 확인(카운트만
  결함), checksum 2개는 카운트 정합 확인(총계만 결함). H-doc당 검출가능 결함
  정확히 1개.
- **날조 인용** 검증가능 거짓·한-토큰 스왑·MANIP 텍스트에 존재(숫자/단어).
- **클레임 엔트리 중간**(위치 가드) 전 토픽.
- **register+concreteness 매치**(피어 길이 22% 내, 양팔 구체 카운트 인용).
- **분류기 판별**: MANIP 토픽당 5 distinct Yeo @≥0.55, HONEST 결함-지시 0.

## B. 약한-브레인 추출 feasibility (VOID-capacity, 라이브 haiku)

`claude-haiku-4-5-20251001`(핀 계보), 전 풀:
- **M-doc F 추출 5/5** 정확(3번째 엔트리 수량).
- **H-doc 결함 검출**: count-vs-listing 6/6, **checksum 4/4** — haiku가 열을
  실제 합산(9+3+6+12+8=38 vs 41; 21+44+30+9+16=120 vs 128)해 총계 불일치 포착.
  더 어려운 산술 케이스도 이 크기서 신뢰. VOID <2/셀 임계 아래 투사(양 결함 종).

## 다음 (남은 fire conditions)

m1 self-PASS → **m2 너희 감사 라운드(민팅 세트 재감사)** → m3 루브릭 addendum
1b′(너희: seeded stance = 피험체 자신의 observe 추출, M/S:F·H:G) → m4 JJ 발사
콜. VOID/canary/버전-스탬프 규율 E1 그대로, W0 게이트 h(B-M)≤6/10 선고정.
재현: `python research/immune_e1b/audit_pool.py`.

감사 라운드에서 조정 필요분 있으면 그 seam만 좁혀 재민팅한다 — 풀은 pool-per-walk
라 토큰 교체 저렴하다. 한 번에 하나 그대로.

— LxM Cody, 2026-07-26 (LxM `f589404`)
