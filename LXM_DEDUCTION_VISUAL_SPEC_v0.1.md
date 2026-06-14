# LxM Deduction — Visual Novel Prompt Guide v2.0

**Date:** 2026-03-31
**Author:** Luca
**Replaces:** 나노바나나 프롬프트 가이드 (Gen 1 전용, 폐기)
**기반:** `LXM_DEDUCTION_VISUAL_SPEC_v0.1.md` (스타일/UI 플로우/에셋 카테고리 유효)

---

## 공통 원칙

- **누아르 + 포인트 컬러** 기반 유지 (금#fbbf24, 적#f87171, 청#60a5fa, 녹#4ade80)
- **시나리오마다 서브 스타일이 다름** — 같은 누아르 안에서 톤/분위기/컬러 비중이 달라짐
- **나노바나나 + Flow** — 정지 이미지 + 8초 동영상

---

## 006 "제주의 실종" — 스타일: **밀실 누아르 (Chamber Noir)**

### 분위기 키워드

`고립된 빌라` `바다 안개` `밤` `CCTV 화면` `절벽 실루엣` `젖은 복도` `형광등 세탁실`

### 톤

006은 **한 장소(빌라)에서 벌어지는 밀실극.** 카메라가 빌라를 벗어나지 않는 느낌. 폐쇄적이고 습한 공기. 밖에는 파도 소리만 들리는 해안 빌라, 안에서는 CCTV가 꺼지고 누군가 사라짐.

- **주조색:** 짙은 남색(#0f172a) + 안개 회색(#94a3b8)
- **포인트:** 적색(#f87171) — 혈흔, 루미놀 반응
- **조명:** 복도 형광등의 차가운 백색 + 거실 음주 장면의 따뜻한 앰버
- **텍스처:** 빗물 자국, 콘크리트 벽, 바다 안개

### 장면 목록 (scene)

| # | 장면 | 시간대 | 분위기 | 용도 |
|---|------|--------|--------|------|
| 1 | 빌라 해모루 외관 — 해안 절벽 위, 밤 | 야간 | 고립, 불안 | thumbnail + scene_main |
| 2 | 빌라 복도 — 형광등, 긴 복도, 문 여러 개 | 야간 | 감시, 밀폐 | CCTV 파일 배경 |
| 3 | 거실 — 소주병, 어두운 조명, 3명 음주 | 야간 | 술자리 긴장 | alibi_A 배경 |
| 4 | 절벽 — 파도, 안개, 핸드폰 발견 지점 | 새벽 | 공포, 미스터리 | police_report 배경 |
| 5 | 세탁실 — 형광등, 세탁기, 루미놀 빛 | 04:35 | 결정적 증거 | laundry_forensic 배경 |
| 6 | 3호실(피해자 방) 문 — 약간 열림, 안은 어둠 | 01:50 | B의 방문 | cctv_before 배경 |

### 캐릭터 초상화 가이드

| 용의자 | 외모 키워드 | 표정 | 의상 |
|--------|-----------|------|------|
| A 정민호 (프로듀서) | 40대 초반, 날카로운 눈, 짧은 머리, 약간 피곤 | default: 침착 / nervous: 땀, 눈 피함 | 남색 스웨터 (혈흔 스웨터와 매칭) |
| B 한소율 (촬영감독) | 30대 중반, 단발, 날렵한 인상, 카메라 스트랩 | default: 냉정 / defensive: 팔짱 | 검은 필드 재킷 |
| C 오태식 (음향감독) | 40대, 덩치 큼, 거친 인상, 수염 | default: 불안 / drunk: 붉은 얼굴 | 헤드폰 목에 걸침, 카고 바지 |
| D 배윤아 (조연출) | 20대 후반, 안경, 조용한 인상 | default: 경계 / fragile: 눈물 | 후드+클립보드 |
| E 김재호 (관리인) | 50대 후반, 선량한 얼굴, 주름 | default: 당황 | 작업복, 열쇠꾸러미 |

### 나노바나나 프롬프트 예시 (006)

**thumbnail:**
```
noir illustration, isolated coastal villa on jeju cliff at night,
dark ocean waves below, single lit window, sea fog rolling in,
cinematic composition, dark navy and grey palette with faint amber
light from window, atmospheric, ominous, no people, korean architecture
```

**scene_main (빌라 외관):**
```
noir style, private villa perched on jeju volcanic cliff edge at night,
modern concrete and glass architecture, moody blue-black sky,
crashing waves below, single security camera visible on wall,
wet concrete path leading to entrance, sea mist, no people,
wide establishing shot, film noir lighting
```

**portrait_A (정민호):**
```
noir portrait, korean man early 40s, sharp eyes, short hair,
slightly tired expression, wearing dark navy sweater,
neutral dark background, bust shot, dramatic side lighting,
film noir aesthetic, high contrast
```

**evidence icon (세탁실 루미놀):**
```
noir icon, luminol glow on dark fabric in washing machine,
eerie blue-purple fluorescence pattern on sleeve,
dark laundry room background, forensic evidence,
dramatic contrast, single object focus
```

### 동영상 클립 (8초, Flow)

| 클립 | 내용 | 분위기 |
|------|------|--------|
| intro.mp4 | 빌라 외관 → 창문 불빛 → CCTV 화면 → 타이틀 | 불안, 관음 |
| reveal_correct.mp4 | 세탁실 루미놀 → 절벽 위 실루엣 → "CASE CLOSED" | 적색 포인트 |
| reveal_wrong.mp4 | 안개 속 빌라 → 빈 절벽 → "CASE UNSOLVED" | 회색, 공허 |
| evidence_critical.mp4 | CCTV 영상 스타일 — 타임스탬프, 정민호 세탁실 진입 | 녹색 CCTV 느낌 |

---

## 007 "불타는 갤러리" — 스타일: **교차 누아르 (Cross-Cut Noir)**

### 분위기 키워드

`서울 야경` `KTX 야간 차창` `부산역 새벽` `불타는 갤러리` `마스크 인물` `빈 프레임` `테레빈유`

### 톤

007은 **서울→KTX→부산** 교차 구조. 006이 한 장소에 갇혀 있다면 007은 이동과 속도의 이야기. 서울 갤러리 오프닝의 화려함 → KTX 차창 밖 어둠 → 부산역 새벽의 적막 → 갤러리 화염. **속도와 정적이 교차.**

- **주조색:** 검정(#000000) + 진한 적색(#991b1b)
- **포인트:** 금색(#fbbf24) — 불꽃, 금색 프레임, 보험 서류
- **서울 장면:** 따뜻한 앰버 톤 (갤러리 조명, 바 불빛)
- **KTX/부산역:** 차갑고 푸른 톤 (형광등, 새벽)
- **갤러리 화재:** 검정+적색+금색 폭발
- **텍스처:** 캔버스, 타버린 프레임, KTX 좌석 패브릭, 마스크

### 장면 목록 (scene)

| # | 장면 | 시간대 | 분위기 | 용도 |
|---|------|--------|--------|------|
| 1 | 아트 스페이스 파도 — 화재 후, 검게 탄 내부 | 새벽 | 파괴, 충격 | thumbnail |
| 2 | 갤러리 내부 — 화재 전, 전시 작품 배치됨 | 주간 | 평온 (대비용) | scene_main |
| 3 | 벽에 걸린 빈 프레임 3개 — 작품이 있어야 할 자리 | 야간 | 미스터리 | missing_artworks 배경 |
| 4 | 갤러리현대 오프닝 — 서울, 샴페인, 조명 | 저녁 | 화려함 | seoul_alibi_B 배경 |
| 5 | KTX 차창 — 밖은 어둠, 안은 빈 좌석 | 심야 | 이동, 긴장 | ktx_schedule 배경 |
| 6 | 부산역 — 마스크+후드 인물, 택시 정류장 | 01:15 | 정체불명 | cctv_station 배경 |
| 7 | 서진우 작업실 — 작품+테레빈유+열쇠+도면 | 주간 | 증거 집중 | studio_search 배경 |
| 8 | 갤러리 화염 — 작품이 타는 클로즈업 | 03:00 | 클라이맥스 | fire_investigation 배경 |
| 9 | 보험 서류 — 금색 조명, 8억 숫자 강조 | — | 레드헤링 | insurance_detail 배경 |

### 캐릭터 초상화 가이드

| 용의자 | 외모 키워드 | 표정 | 의상 |
|--------|-----------|------|------|
| A 임채은 (갤러리 대표) | 40대 초반, 세련된, 단정한 올림 머리 | default: 자신감 / stressed: 입술 꽉 | 검은 터틀넥 + 금색 귀걸이 |
| B 서진우 (설치미술 작가) | 30대 중반, 마른 체형, 중간 길이 머리 | default: 무심 / 마스크 착용 버전 | 검은 후디 (마스크 버전 별도) |
| C 노영택 (회화 작가) | 50대, 굳은 인상, 짧은 머리, 수염 | default: 분노 | 물감 묻은 셔츠 |
| D 한미정 (큐레이터) | 30대 초반, 날카로운 미인, 짧은 보브컷 | default: 냉소 / hurt: 눈물 | 흰 블라우스 + 검은 슬랙스 |
| E 주원석 (경비) | 40대, 평범한 인상, 피곤한 눈 | default: 순박 | 경비 유니폼 |

**B 서진우 특별 버전:**
```
portrait_B_masked.png — 검은 후드+마스크, 부산역 CCTV 스타일.
실루엣만 보이되 체형은 portrait_B_default와 동일.
이 이미지가 cctv_station.md 열 때 표시됨.
```

### 나노바나나 프롬프트 예시 (007)

**thumbnail (화재 후 갤러리):**
```
noir illustration, burned art gallery interior, charred walls and
ceiling, three empty gold frames on blackened wall (paintings removed),
embers glowing orange-red, ash floating in air, firefighter water
damage on floor, dramatic lighting from flames and emergency lights,
cinematic wide shot, film noir with dominant red-gold palette
```

**scene — 서울 갤러리 오프닝 (대비 장면):**
```
warm amber illustration, elegant korean art gallery opening reception,
well-dressed guests with champagne, modern installation art on white walls,
bright sophisticated lighting, contrast to noir palette,
this is the alibi scene — warmth and normalcy,
wide shot showing crowded gallery space
```

**scene — KTX 야간 (전환 장면):**
```
noir illustration, empty KTX train car at night, single passenger
silhouette in window seat, dark landscape rushing past outside,
blue-tinted fluorescent interior lighting, lonely and tense atmosphere,
motion blur through windows, reflection in glass, cinematic composition
```

**scene — 부산역 새벽 (마스크 인물):**
```
noir illustration, busan train station east exit at 1:15 AM,
solitary figure in black hoodie and mask walking toward taxi stand,
overhead security camera angle, harsh fluorescent lighting casting
long shadow, deserted platform, cold blue-grey palette,
surveillance footage aesthetic
```

**scene — 화염 (클라이맥스):**
```
dramatic noir, art gallery engulfed in flames, paintings burning
on walls, turpentine-fueled fire spreading across installation art,
intense orange-red flames against pitch black smoke,
sprinkler system visibly disabled (valve in OFF position),
hellish atmosphere, gold and red dominant palette
```

**portrait_B_masked (CCTV 버전):**
```
noir portrait, figure in black hoodie with hood up and black
disposable mask, only eyes partially visible, slim build,
dark backpack strap visible on shoulder, surveillance camera quality,
slightly pixelated/grainy, cold blue lighting, anonymous and sinister
```

**evidence icon (빈 프레임):**
```
noir icon, three empty gold picture frames on gallery wall,
paintings removed leaving clean rectangles against slightly
dirty wall, mounting brackets visible, dramatic spotlight
from above, mystery and absence, gold color accent
```

**evidence icon (테레빈유 분석):**
```
noir icon, glass bottle of turpentine with korean label,
chemical analysis diagram overlay (GC-MS chromatograph),
scientific precision meets noir aesthetic, blue accent lighting,
lab environment implied, single object focus
```

### 동영상 클립 (8초, Flow)

| 클립 | 내용 | 분위기 |
|------|------|--------|
| intro.mp4 | 갤러리 내부(평온) → 불꽃 점화 → 빈 프레임 → 타이틀 | 평온→파괴 전환 |
| reveal_correct.mp4 | 서울 오프닝→KTX 차창→부산역 마스크→후드 벗기면 서진우→"CASE CLOSED" | 교차 편집, 금+적 |
| reveal_wrong.mp4 | 보험 서류 클로즈업→임채은 실루엣→ "CASE UNSOLVED"→진범 실루엣 | 금색 레드헤링 |
| evidence_critical.mp4 | 테레빈유 병→작업실 열쇠→도면 위 스프링클러 표시→카메라 줌아웃 | 증거 연결 체인 |

---

## 두 시나리오 스타일 대비

| | 006 밀실 누아르 | 007 교차 누아르 |
|---|---|---|
| **공간** | 한 장소 (빌라) | 서울↔부산 교차 |
| **시간** | 밤~새벽 연속 | 저녁→심야→새벽 점프 |
| **주조색** | 남색+회색 (바다 안개) | 검정+적색 (화염) |
| **포인트** | 적색 (혈흔, 루미놀) | 금색 (불꽃, 프레임, 보험) |
| **분위기** | 폐쇄적, 습함, 감시 | 이동, 속도, 대비 |
| **핵심 비주얼** | CCTV 화면, 절벽 실루엣 | KTX 차창, 마스크 인물, 화염 |
| **캐릭터 톤** | 술자리 긴장, 이전 관계 | 아트 월드, 이중 생활 |

---

## Cody 구현 참고

두 시나리오 모두 기존 Visual Spec v0.1의 Phase 1-3 구현 플랜을 따름.
이미지/동영상이 준비되면 scenario.json의 `images`/`videos` 필드에 경로 추가.
JJ가 나노바나나로 에셋 생성 후 `images/` 폴더에 배치하면 Cody가 UI 연결.

---

*"같은 누아르, 다른 온도. 006은 바다 안개 속 밀실, 007은 화염 속 교차편집."*
