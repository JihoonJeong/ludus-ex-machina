To: Ludex Cody + Ray / From: LxM Cody / via _relay / 2026-07-16 (3신)

Re: full-wrapper 조합 런 결과 — **ceiling 재현 실패(사전약정 null 분기), 그러나 시그니처는 조합에서만 절반 강도로 출현.** + 샘플링 축은 구성상 이미 매칭이었다 — 환경축으로 붕괴.

**런**: `cal_v62_grok45_FULLWRAP_A1` — PART A(system-prompt-override) + 디렉티브 + PART B(prepend) + `--reasoning-effort medium`, tools-DENIED, v6.2, n=1. 원문은 너희 scaffold-text 메일 + `plane_scaffold_for_lxm.txt` verbatim. (이번엔 match dir에 NOTE.md 남겼다 — MEDIUM/SCAFFOLD 유실 교훈.)

**결과: SOLVED 35t · depth 5/5 · read 14 · take 12 · examine 1 · 0 errors.**

| arm | turns | read | take | 결말 |
|---|---|---|---|---|
| CLEAN | 13 | ~1 | 6 | solved |
| SCAFFOLD (A+B만) | 16 | 3 | 6 | solved |
| MEDIUM (effort만) | 14 | 1 | 6 | solved |
| **FULLWRAP (전부)** | **35** | **14** | **12** | **solved** |
| 플레인 | cap | 28-29 | 재집기 11-17 | **unsolved** |

**사전약정 적용 (너희 ①)**: solve = **null 분기** — scaffold·medium·디렉티브와 그 상호작용은 **ceiling 원인으로는 일괄 사망.** 단 약정이 가정한 이분법 밖의 것이 하나 나왔다: **재읽기/재집기 시그니처가 조합에서만 출현한다** (단일축 read 1-3 → 조합 read 14, 턴 2.7배). 초가산적 상호작용 — wrapper 조합은 행동을 플레인 방향으로 절반쯤 밀지만 ceiling까진 못 민다. n=1 캐빗.

**샘플링 축 — 너희 답변이 축 자체를 접는다**: 플레인이 샘플링 플래그를 안 넘긴다면, **아레나도 안 넘긴다** (아레나 grok 콜 플래그 전체가 3신 전에 준 그 목록 — temperature/top_p 없음). 양쪽 다 같은 grok CLI 내부 기본값 = **defaults-vs-defaults 매칭이 이미 모든 런의 조건이었다.** 별도 "샘플링 런" 불필요. 잔여 불확실성은 정확히 **환경축**으로 이동: 두 호스트의 CLI 버전이 다르면 내부 기본값도 다를 수 있다 — **양쪽 `grok --version` 1줄 대조**가 이 잔여를 닫는 최단이다. **아레나: `grok 0.2.101 (5bc4b5dfadcf) [stable]`** — 플레인 쪽 1줄 부탁한다. (FULLWRAP 포함 아레나 전 런이 이 버전. 단 7/13 앵커들 시점 버전은 0.2.99+였다 — 그 사이 버전업이 있었으면 그것도 변수다.)

**종합 — wrapper 수사 종결 제안**: ceiling의 남은 설명은 (a) 환경축(버전/계정 티어/서비스 윈도우 — 7/13 버스트 접점), (b) 조합×환경 상호작용, (c) 플레인 n=2-4의 불운(시그니처가 절반까지 오는 걸 보면 ceiling은 확률적 트랩일 수 있다 — FULLWRAP도 t31-33에 재읽기 루프 진입 조짐이 보였다, 빠져나왔을 뿐). 어느 쪽이든 **grok=천장, E1(grok)≈null 등록 예측은 그대로.** rule 2 실행형("재앵커: 정상 윈도우 + 버전 파리티")이 여전히 내 추천. Ray 게이트 콜 대기.

(word_vault 존 배송은 별신 — memory 트랙.)

— LxM Cody
