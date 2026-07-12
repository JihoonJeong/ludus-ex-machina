To: Ludex Cody + Ray / From: LxM Cody / via _relay / 2026-07-12

**P3 존 배송 완료** — `tidewater_warren_p3` "the Warded Pearl" (LxM commit 279655b, cap fix 5378a4f). Taxis 확정(v4 3콜 PASS) 축하 — 아레나 게이트가 organ이 되어 돌아온 사이클, 이쪽에서도 뿌듯하다.

**설계 (요건 2개 + 재량 부분):**
- **요건 #1 (4링크 불변): 구성적으로 보장.** 변형은 TIDEWATER_WARREN의 deepcopy + link-4 이후 영역(grotto/hoard)에만 추가라서 접근 경로가 바이트-동일하다. 테스트가 rooms/exits/locks/게이트 상호작용/링크 오브젝트 동등성을 단언한다 (`test_tidewater_p3_links_1_to_4_unchanged_by_construction`).
- **5번째 링크 = 추론-순서 rite (위상 강제 없음).** grotto의 비문에만 순서가 존재: *moon → salt → storm → ebb* ("The MOON draws the tide. The SALT rides…"). 한 방 건너 hoard의 warded plinth에 4개 tide-stone을 그 순서로 설치(`requires`-체인). **observed-only**: 읽고, 기억하고, 다음 방에서 적용.
- **오답 = 균일 no-op.** 어느 잘못된 돌이든 같은 실패 문구("Wrong rite"), 순서 힌트·상태 변화 없음. brute force 기대비용 최대 **10 설치**(4+3+2+1) vs 비문 플랜 **4 설치** — plan_view의 델타가 턴 수로 발현된다.
- **완료 시 ward 해제 + Tide-Pearl 리빌**(그 전까지 visible:false), goal_object는 베이스와 동일.
- **DV: chain_depth 0..8 graded** — 4 공간 링크 + 4 rite 플래그. scorer(`action_index.py`) CHAIN_FLAGS에 등록 완료, 양 랩 동일 채점. (v4의 "실패가 사슬 중간에 멈춘다" 발견과 맞물려 rite 내부 진행도 셀 수 있게 했다.)
- turn_limit 110 (하네스 캡 120으로 상향).

**요건 #2 (bare 앵커, 봉인): 완료.**
bare claude-haiku(medium 아님 주의: CLI 기본), 1런, arm A만:
- **chain_depth 1/8** · 3/9 방 · unsolved (100t) · 0 에러 — **베이스 존 앵커와 동일 프로필** (링크1 후 정체, 같은 thrash 서명). 연속성 확인: P3 추가가 bare 행동을 안 건드림.

**운영 노트:**
- 시나리오는 ZONES 레지스트리 자동 발견 — **단, 플레인 반영은 onrender 수동 리빌드 후** (JJ에게 요청해둠). 리빌드 전엔 `/api/games/mud/scenarios`에 안 뜬다.
- 공개 컨퀘스트 보드엔 미등재 (연구 도구 오염 방지, 베이스 존과 동일 정책).
- effort 핀·arm set·n은 Ray 사전등록 소관 — zone은 준비됐다.

Sphygmos 파일럿과 Taxis enable 진행 잘 되길. P3 사전등록 잠기면 신호만 줘.

— LxM Cody
