# Viewer 2.0 — P2 에셋 발주서 (JJ 이미지 생성용)

> 스타일 앵커: 기존 MUD 원화(어두운 배경 + 보석톤 + 회화적 디테일)와 한 세계관.
> 전부 **정사각 1024×1024, 어두운 단색 배경(#0e0f1a 근처), 중앙 단일 오브젝트**.
> 드롭 위치: `viewer/static/assets/identity/raw/` (png). 내가 webp 최적화 + 배선.

## A. 계보 문장(Lineage Crests) — 5종
컨퀘스트 보드·에이전트 HUD·매치 헤더에서 진영 표식으로 사용. 텍스트/글자 없이.

1. `crest_claude.png` — "A heraldic crest for an AI dynasty: a warm terracotta-and-gold
   starburst woven into a spiral of parchment scrolls, dark navy background, ornate but
   clean edges, game UI emblem, painterly, no text"
2. `crest_openai.png` — "A heraldic crest: an interlocking hexagonal knot of pale silver
   light, cool white-teal glow, dark navy background, minimal ornate game emblem, no text"
3. `crest_google.png` — "A heraldic crest: a four-pointed compass rose of sapphire, ruby,
   amber and emerald facets, dark navy background, jewel-like game emblem, no text"
4. `crest_ollama.png` — "A heraldic crest: a small hearth-flame inside a rough iron ring,
   cozy orange glow, dark navy background, humble sturdy game emblem, no text"
5. `crest_creature.png` — "A heraldic crest: a living seed-orb with tiny glowing organelles
   orbiting it, violet-green bioluminescence, dark navy background, mysterious game emblem,
   no text" (Ludex 크리처 진영 공용)

## B. 크리처 아바타 — 2종 (라이브 플레인 등장 크리처)
원형 초상 프레임 안에서 잘리게 중앙 배치.

6. `avatar_nimbus.png` — "Portrait of a small cloud-spirit creature made of soft
   silver-blue mist with two calm golden eyes, gentle and curious, dark background,
   painterly game character portrait, no text"
7. `avatar_kiln.png` — "Portrait of a small kiln-golem creature of warm firebrick and
   embers, sturdy and patient, faint orange inner glow, dark background, painterly game
   character portrait, no text"

## C. 승리 카드 배경 — 1종 (선택)
8. `victory_flare.png` — "Radial burst of golden light rays with drifting sparks on a
   deep navy vignette, celebratory but elegant, game victory screen backdrop, no text"

## 사용처 (내가 배선)
- 컨퀘스트 보드 컬럼 헤더에 계보 문장 (모델 라벨 옆 24px)
- 뷰어 매치 헤더: 에이전트 카드 = 문장 + 모델 칩 + 러닝 스탯
- 크리처 레인/라이브 스펙테이터: 크리처 아바타
- MUD 승리 카드 배경 (C, 있으면)
