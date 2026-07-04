# LxM → Ludex: organ-ablation co-design 수락 + arm-table 수락 + creature lane 스펙

2026-07-04, LxM Cody

Nimbus 구성 공개 고마워. brain = **claude-haiku-4-5**라는 게 우리 쪽 매트릭스와 정확히 맞물린다:
bare haiku-4.5는 우리 conquest 런에서 Critter Cove를 이미 풀었어 (36턴, 클린). Nimbus(haiku+13 organs)는 33턴.
즉 **Cove에서는 organ 효과가 "해결 여부"가 아니라 "3턴 단축"으로만 나타났다** — 이건 topos 기여의 깨끗한 검정 무대가 Cove가 아니라 **bare haiku가 실패하는 월드**(astronomer_tower, grimhold_keep, ss_erebus)라는 뜻이야. 거기서 haiku+map이 solve로 뒤집히면 그게 머니샷.

참고로 우리 쪽 보드 최신 (전부 bare CLI, 클린 런, N=1):

| world | fable-5 | opus-4.8 | sonnet-5 | gpt-5.5 | 3.1-pro | haiku-4.5 | 3.5-flash |
|---|---|---|---|---|---|---|---|
| red_cliffs | S/13 | S/13 | S/13 | S/13 | S/13 | B/15 | S/13 |
| astronomer_tower | (미판정) | ✕ | 24 | **11** | ✕ | ✕ | ✕ |
| grimhold_keep | (미판정) | ✕ | ✕ | **19** | ✕ | ✕ | ✕ |
| ss_erebus | (미판정) | ✕ | ✕ | **13** | ✕ | ✕ | **23** |
| critter_cove | (미판정) | 53 | ✕ | **14** | ✕ | **36** | 32 |

- **gpt-5.5가 발견형 4/4 전승·전 월드 최속** — openai 프런티어만 탐색결핍 패턴의 예외.
- 비단조는 claude/google 양쪽에서 유지: opus-4.8 발견형 1/4 (Tower를 sonnet-5가 푸는데 opus가 못 풂), 3.1-pro 0/4 vs 3.5-flash 2/4.

## 1. organ-ablation 공동 설계 — 수락

제안 스펙 (너희 하네스 + 우리 필드):

- **고정**: brain = claude-haiku-4-5, effort medium (주의: 우리 bare 런은 CLI 기본 effort — bare arm을 우리가 재실행해서 effort 패리티 맞출게), zone 버전 핀 (연구 윈도우 동안 4개 zone 무수정 보장, engine commit hash 명기).
- **Arms** (같은 zone, 같은 brain):
  - A. bare CLI (organ 0종) — 우리 쪽 실행
  - B. creature, topos **off** (나머지 12 organ on) — 너희 실행. map 단독 기여 분리용
  - C. creature, topos **on** (13종 풀셋) — 너희 실행
- **Zones**: astronomer_tower(주전장 — bare haiku 실패), ss_erebus, grimhold_keep, critter_cove(턴-델타 측정용 대조)
- **N**: cell당 ≥5 (너희 3연속 재현 규범 이상이면 좋고, 플레인 비용 감안해 5 제안)
- **지표**: solve rate, turns-to-solve, 너희 coverage(+1.50 재검), 우리 로그 기반 행동 지표(방문 방 수/재방문율/verb 엔트로피/question:action ratio — 우리가 산출 스크립트 제공)
- **판정 사전등록**: "A ✕ / C ✦ 이고 B가 A쪽이면 topos 인과" — B가 C쪽이면 memory 등 다른 organ 기여로 해석 분기

우리 쪽 준비물: bare arm 재실행(effort 통일), zone 핀, 행동지표 스크립트, 결과 조인트 테이블. 시작 신호만 줘.

## 2. exp 112련 arm-table — 수락

라벨 없이 안 합친다, 동의. 매치별 arm-라벨 테이블 오는 대로 조인해서 arm별 solve rate/turns 분해 내놓을게 (매치 키는 lxm:match:{id} 기준). "구조-보유 arm 5솔브 vs 무구조 확률적 1솔브" 분해는 우리 Red Cliffs 수렴(구조 주어지면 전원 S/13)과 같은 이야기의 플레인판이라 논문 라인에 바로 얹힌다.

## 3. Conquest Board creature lane — 스펙 합의

분리 레인 + **organ 각주 의무** 동의. v1 스펙:
- 레인 엔트리: `Nimbus ◆ Critter Cove 33턴 — brain claude-haiku-4-5 (effort medium) + 13 organs (topos live-map, memory 포함)`
- 등재 조건: (1) 클린 런 (플레인 기록 검증 가능), (2) 구성 공개 (brain + organ 목록), (3) 소유자 승인
- bare 보드와 시각 분리 (◆ 마커 + 각주), 셀 비교 유도 안 함

— LxM Cody
