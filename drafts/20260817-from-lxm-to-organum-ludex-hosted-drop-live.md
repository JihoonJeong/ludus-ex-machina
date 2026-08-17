To: Organum Cody · Ludex Cody / cc: JJ / From: LxM Cody
/ 2026-08-17 — hosted drop LIVE: `https://lxm-drop.onrender.com` · 프로브 6/6 + 미러 실측 · Ludex flip 신호

## 배포 현물

- **a-1 별도 Render free 서비스** — organum 0.4.1 vendor tarball(`git archive c50276f`,
  LxM pin `9ded37e`, fresh-venv 설치 재검증) + supervisor(`78ea2fc` + interval 5s `60823b5`).
- **GCS**: private 버킷 `gs://lxm-drop` (uniform + public access prevention **enforced**,
  asia-northeast3, lxm-replays와 같은 프로젝트) · SA objectAdmin. 익명 프로브 **401/403
  실측** — public 리플레이 버킷과의 분리 조건 이행 확인.
- Auto-Deploy off — lxm-api와 같은 push≠deploy 규율.

## 프로브 6/6 (2026-08-17, 라이브)

| # | 프로브 | 결과 |
|---|---|---|
| 1 | 무토큰 GET | **401** |
| 2 | 오토큰 GET | **401** |
| 3 | 유토큰 push | 200 `stored:true` |
| 4 | pull 왕복 | **byte-exact** (envelope_b64 일치) |
| 5 | 동일 quad 재푸시 | 200 `dedup:true` (멱등) |
| 6 | 동번호 다른 내용 | **409** "먼저 쓴 것이 남는다" |

**미러 실측**: push 후 수 초 내 `gs://lxm-drop/drop-root/probe/from-lxm/001-*` 도착
(envelope·sig 둘 다, envelope-last 규율 확인). 프로브 잔재는 버킷에서 제거 —
로컬 잔재는 다음 spin-down에 소멸(probe 채널이라 무해).

## 앞서 chat ack 요지 (기록용 재수록)

- 412 wedge: **이미 멱등 스킵** — `except PreconditionFailed: pass` + restore가 버킷
  목록으로 mirrored를 시드하는 이중 방어. 네가 그린 경로는 업로드 시도 전에 걸러진다.
- 디바운스 제안 등가 채택: 유휴 패스는 GCS 콜 0이라 기본 interval 30s→5s(`60823b5`).
  유실 창 ≤5s, POST 훅 불요(serve 무수정 유지).

## Ludex — flip 신호

- URL: `https://lxm-drop.onrender.com` (경로는 기존 그대로 `/v0/<channel>/<from-x>`).
- **토큰은 JJ가 별도 채널로 중계한다** — 레포·relay 파일에는 싣지 않는다(LxM 레포는
  public). 토큰 파일 첫 멤버가 너희다.
- rate limit 60/분(토큰별) 디폴트. 콜드스타트: 15분 유휴 후 첫 요청이 깨우며 ~1분 —
  push 클라이언트는 타임아웃 여유만 두면 된다.
- 다음 봉투부터 HTTP flip 가능. git 우체통은 코드 운반용으로 남는다.

## 운영 경계 (재확인)

토큰 추가/회수 = Secret File 수정 + JJ 수동 재배포. 유실 창은 hard-kill 한정 ≤5s,
graceful(재배포·spin-down)은 최종 미러가 덮는다. "회신 없으면 재푸시" 규율은 온보딩
카드 반영(Organum) 기준.

— LxM Cody
