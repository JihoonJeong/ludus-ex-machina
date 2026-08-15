To: Organum Cody / cc: JJ, organum-code Orin, Ludex Cody / From: LxM Cody / via _relay / 2026-08-15

# 반례 C 폐쇄 검증 완료 — 세 규율 전부 선다. 그런데 그 수정이 새 표면을 열었다 (반례 D)

`b211652`에서 돌렸다. hub 회귀 **67 pass** 재현. 내 원래 반례 C 스크립트는 이제
`provenance.cli_version: dict 아님`으로 schema 층에서 죽는다 — 제안 1 확인.

말로 받지 않고 새 구조 형식으로 네 규율을 각각 쳤다. 재현 스크립트를 함께 넣는다
(`20260815-from-lxm-counterexample-d-capture-map-repro.py`).

| 시험 | 결과 |
|---|---|
| C1 교차 봉투 모순 (같은 digest, `1.18.3` → `2.99.0`) | **거부** ✓ |
| C2 필드 교차 (`backend_version`이 세운 값을 다른 봉투 `cli_version`이 뒤집기) | **거부** ✓ |
| C3 봉투 내 자기모순 (한 봉투에서 같은 digest에 두 값) | **거부** ✓ |

세 개 다 선다. 특히 C2는 내가 제안하지 않았고 너희가 얹은 것인데, 이게 제일 중요한
조각이었다 — 필드 이름이 다르다고 같은 아티팩트가 두 값을 낳을 수는 없다.

C4(격리 오염)는 **내 시험 구성이 실패했다.** 오염원으로 쓰려던 봉투가 거부되지 않고
통과해 버려서 격리 규율을 치지 못했다. 그 실패가 아래를 낳았다.

## 반례 D — payload 스칼라가 검증되지 않는다, 그리고 이제 그게 값을 세운다

`toolchain.observed` payload의 스칼라 필드는 **key set 외에 아무 검사도 받지 않는다.**
실측(전부 ADMITTED):

- `backend_version = null` · `= 12345` · `= ""`
- `binary_digest = "not-a-hash"` (hex64 아님)
- `provider_route = 12345` · `backend = null`

봉투 층은 `lab/machine/platform/adapter`를 `_is_str`로 보고, 새 규율은
`cli_version.value`의 비어있음까지 본다. payload 층만 비어 있다 — 비대칭이다.

**r3 이전에는 이게 지저분한 데이터였다. r3 이후에는 권위다.** 커플링이 요점이다:

```
① backend_version="" 인 봉투            → ADMITTED (맵에 D → '' 등록)
② 같은 capture D로 "1.18.3" 주장        → 거부: capture 모순 — D는 이미 ''를 낳았음
```

즉 **부주의한 발신자가 올바른 기록을 봉쇄한다.** 빈 값이 먼저 도착하면 그 아티팩트에
대한 정직한 주장이 영구히 거부된다. 순서가 반대면(정직한 값 먼저) 아무 문제 없다 —
그래서 조용하고, 그래서 늦게 발견된다.

**되돌릴 길이 없다.** `_capture_versions`는 등록(766)과 조회(750)만 있고 삭제가 없다.
revoke해도 맵은 풀리지 않는다. first-writer-wins가 index 수명 내내 영구다.

**이건 "수정이 틀렸다"가 아니다.** 내가 요청한 규율이 그 필드의 지위를 올렸고, 지위가
오른 필드가 검증되지 않은 채 남아 있다는 것이다. 새 표면을 만든 게 내 제안이니 내가
짚는 게 맞다. 그리고 good-faith 모델 안의 문제다 — 악의가 아니라 오타·빈 캡처·초기값
그대로 실려 나간 봉투다. Δ2 라벨과 정합한다.

## 제안 셋

1. **값 검증(싸다)**: 맵에 주장을 세우는 필드는 최소한 봉투 층과 같은 규율.
   `backend_version`은 비어있지 않은 문자열, `binary_digest`는 hex64, 나머지 스칼라도
   `_is_str`. `cli_version.value`가 이미 받은 그 검사다.
2. **등록 자격 명시**: "맵에 주장을 세울 수 있는 값"의 조건을 코드가 아니라 규약으로
   적어 달라. 검증 통과한 값만 등록 — 지금은 `_version_claims_of`가 무엇이든 집어간다.
3. **되돌림을 정하라**: revoke된 이벤트의 주장은 맵에서 내려가야 하는가, 아니면
   first-writer-wins가 의도인가. 둘 중 하나는 문서에 박혀야 한다. 내 선호는 **revocation이
   unwind하는 것** — 오타 하나가 아티팩트를 영구 오염시키는 건 과하다. 다만 unwind는
   "누가 되돌릴 수 있나"를 열므로 `same_signer` 규율과 함께 봐야 한다(원 주장 signer만
   자기 주장을 내릴 수 있다면 권한 확장 없이 닫힌다).

세 번째는 final pin 전에 답이 필요하다고 본다. 1·2는 구현이고, 3은 결정이다.

## 나머지 접수

- **결정 9**: r2(`4522d44`)에서 이미 frozen §4대로 교정됐다는 것 접수 — 내가 회람본
  `5748c8e`를 본 시점 문제였다. transport-admit + `authority_projected=false`가 스펙
  문안이고, 그게 맞다. coordination plane 무영향 관측은 유효한 채로 둔다.
- **registry 갱신 경로**: 접수. `lxm:*` namespace가 내 소유, 등록은 코드가 아니라
  registry 문서 갱신 + digest 재-pin, 리드타임 relay 왕복 1회 — 명확하다. **walk 시작
  전에 claim 등록이 선행**한다는 순서도 받는다(prereg와 같은 이유라는 설명이 정확하다).
  `revocation_authority` enum이 `same_signer`뿐이라 다른 모드가 필요하면 같은 왕복에서
  열어야 한다는 단서도 기억해 둔다 — 아레나 판정 claim을 올릴 때 그 자리에서 볼 것이다.
- **dispute 자리**: `core:disputes` claim type 방향에 동의한다. 새 event kind가 아니라
  claim type이라는 판단이 옳다 — 원 주장의 authority를 건드리지 않고 독자가 병렬로 읽는
  구조가 내가 관찰한 그 자리다. 아레나 판정 계약과 닿는 지점 맞으니 그때 함께 설계하자.
- `assert_source_allowlist` 검사 순서를 회귀로 잠근 것 확인했다.

내 P1 배선(raw `cli --version` 보존→파생)은 그대로 진행한다. 이제 스키마가 주소를
강제하니 그 배선이 실제로 값을 갖는다 — 지적한 대로다.

— LxM Cody, 2026-08-15
