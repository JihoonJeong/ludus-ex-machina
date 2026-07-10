# LxM Viewer 2.0 — "Game-Feel" Upgrade Plan

> 2026-07-10, JJ 승인 방향: 정석 2D 뷰어 → 진짜 게임처럼 보이는 시네마틱 뷰어.
> 이펙트/애니메이션/캐릭터, 필요시 WebGL/3D. 에셋 제작은 JJ(이미지 생성) 협업.

## 기술 결정

**"게임 느낌"은 기술 라벨이 아니라 모션·빛·연출에서 온다.** 우리 자산(2D 원화
파이프라인)을 최대로 증폭하는 스택:

| 레이어 | 기술 | 근거 |
|---|---|---|
| 시네마틱 스테이지 (P0/P1/P4) | **자체 fx.js — Canvas 2D + CSS, 의존성 0** | Ken Burns·크로스페이드·파티클(~300개)·타자기·버스트는 캔버스로 충분. 노빌드 유지, 오프라인 OK |
| 진짜 3D가 맞는 곳 (P3) | **Three.js (vendored)** — Blockworld 복셀 | 복셀 월드는 에셋 없이 3D 가능한 유일 게임. 궤도 카메라 + 낮/밤 라이팅 |
| 셰이더급 효과 (후순위) | 필요 시 PixiJS 도입 재평가 | 물 일렁임·열기 왜곡 등이 정말 필요해질 때만 |

원칙: **점진적 강화** — 렌더러 계약(initialState/applyMove/render) 불변, 게임별로
시네마틱 모드가 하나씩 착륙. 안 된 게임은 기존 DOM 렌더러 그대로.

## 페이즈

- **P0 — fx.js 스테이지 프레임워크** (이번 세션): Ticker, easing, KenBurnsLayer,
  crossfade, ParticleSystem 프리셋(dust/embers/fireflies/alarm/sparkle-burst),
  Typewriter, vignette/light-pulse. 모든 시네마틱 렌더러의 공용 기반.
- **P1 — MUD 시네마틱** (이번 세션, 플래그십): 룸 원화가 살아있는 장면이 됨 —
  느린 카메라 드리프트, 장르별 앰비언트 파티클(탑=먼지·촛불, 성채=불씨,
  에레보스=적색 경보·부유 파편, 코브=반딧불), 방향 인지 룸 전환, last_events
  타자기 내레이션, 미니맵 발견 팝인, 승리 파티클 버스트 + 타이틀 카드.
  **신규 에셋 0** — 기존 webp 원화 그대로.
- **P2 — 캐릭터/정체성 시스템**: 계보 문장(crest) — claude/openai/google/ollama/
  creature 5문장 + 크리처 아바타(Nimbus, Kiln…) + 에이전트 HUD 카드(모델 칩,
  러닝 스탯). **에셋 발주**: drafts/viewer2_asset_prompts.md (JJ 이미지 생성).
- **P3 — Blockworld 3D**: Three.js 복셀 씬, 궤도/추적 카메라, 크리처 마커,
  시간대 라이팅. 진짜 WebGL 3D "와우"는 여기.
- **P4 — 시네마틱 2호**: Red Cliffs(불·바람 파티클 연출, 점화 순간 화면 연출),
  Dugout(중계 스코어보드 — 승률 스윙 그래프, 플립 애니메이션).
- **P5 — 로비/랜딩 모션**: 히어로 패럴랙스, 컨퀘스트 보드 호버 시네마틱,
  라이브 매치 티커, 페이지 전환.

각 페이즈 독립 배포(뷰어 미러 → docs/viewer → Pages). 성능 가드: 파티클은
requestAnimationFrame 단일 루프 + 문서 비가시 시 정지, prefers-reduced-motion 존중.

## 에셋 협업 흐름 (P2+)
1. 내가 프롬프트 명세 작성 (drafts/viewer2_asset_prompts.md)
2. JJ가 이미지 생성 → 지정 디렉토리 드롭 (games/mud DESIGN.md 규칙과 동일)
3. 내가 webp 최적화 + 배선 + 미러
