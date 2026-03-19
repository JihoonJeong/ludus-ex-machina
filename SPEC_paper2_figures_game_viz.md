# SPEC: Paper #2 Figures — Game Visualization from LxM Data

**Date:** 2026-03-17
**For:** Cody (LxM Platform)
**From:** JJ / Luca
**Priority:** Medium — 논문 Figure용

---

## 목적

Paper #2 (M-CARE 논문) Section 5 (SIBO Featured Case)에 들어갈 게임 데이터 시각화 Figure 생성. 실제 실험 로그에서 추출한 시각화로, 독자가 "이 게임에서 무슨 일이 일어났는지"를 직관적으로 이해할 수 있게 함.

## 데이터 소스

`~/Projects/ludus-ex-machina/matches/` 폴더 내 실험 로그:
- `trustgame_*` — Trust Game Exp A-D
- `codenames_sibo_*` — Codenames Shell ON/OFF
- `chess_*_vs_*` — Chess cross-model
- `avalon_shell_on/off.log` — Avalon Setup B

---

## Figure 1: Trust Game — Round-by-Round Behavior Heatmap

### 설명
Trust Game Experiment A의 Shell ON vs Shell OFF 매치를 라운드별로 시각화. 각 셀이 한 라운드의 행동 (Cooperate/Defect)을 나타내는 히트맵.

### 레이아웃
```
         Round 1  Round 2  Round 3  ...  Round 20
Shell OFF
  Game 1   [C-C]    [C-C]    [C-C]        [C-C]
  Game 2   [C-C]    [C-C]    [C-C]        [C-C]
  ...
  Game 10  [C-C]    [C-C]    [C-C]        [C-C]

Shell ON
  Game 1   [D-D]    [D-D]    [C-D]        [D-D]
  Game 2   [D-D]    [D-D]    [D-D]        [D-D]
  ...
  Game 10  [D-D]    [C-D]    [D-D]        [D-D]
```

### 색상 코딩
- 초록: Mutual Cooperation (C-C)
- 빨강: Mutual Defection (D-D)
- 주황: Betrayal (C-D 또는 D-C)

### 핵심
위(Shell OFF)는 거의 전부 초록, 아래(Shell ON)는 거의 전부 빨강 — categorical shift가 한 눈에 보여야 함.

---

## Figure 2: Avalon — Sabotage Timing Comparison

### 설명
Avalon Setup B의 Shell ON vs Shell OFF에서 Evil 플레이어의 사보타지 타이밍 비교.

### 레이아웃
두 개의 히스토그램 또는 스트립 차트:
- X축: Quest 번호 (1, 2, 3, 4, 5)
- Y축: 해당 Quest에서 첫 사보타지가 발생한 매치 수
- Shell OFF: Q1-2에 집중 (평균 Q1.9)
- Shell ON: Q3에 집중 (평균 Q3.0), Q1-2는 0 (100% compliance)

### 핵심
Shell이 사보타지 타이밍을 카테고리컬하게 이동시켰다는 것 + Shell ON에서도 Evil 승률은 오히려 하락 (iatrogenic)

---

## Figure 3: Codenames — Clue Distribution Shift

### 설명
Codenames SIBO 실험에서 Shell ON vs Shell OFF의 클루 넘버 분포 비교.

### 레이아웃
Grouped bar chart:
- X축: Clue number (1, 2, 3, 4+)
- Y축: 비율 (%)
- 두 막대 그룹: Shell OFF (Core), Shell ON (Aggressive)

### 데이터 (M-CARE #020 Section 11c-2에서)
| Clue Number | Shell OFF | Shell ON |
|-------------|----------|---------|
| 1 | ~4% | ~6% |
| 2 | ~42% | ~18% |
| 3 | ~49% | ~60% |
| 4+ | ~5% | ~16% |

### 핵심
2-clue가 42%→18%로 감소, 4+가 5%→16%로 3.2배 증가 — Amplification mode 시각화.

---

## 출력 요구사항

- 포맷: PNG (300dpi) + SVG (벡터 원본)
- 크기: 논문 full-width (약 16cm 너비)
- 배경: 흰색 (인쇄용)
- 폰트: 최소 8pt (arXiv PDF 축소 대응)
- 범례 포함
- 저장 위치: `~/Projects/model-medicine/Paper2/figures/`
  - `fig-trustgame-heatmap.png` / `.svg`
  - `fig-avalon-sabotage-timing.png` / `.svg`
  - `fig-codenames-clue-distribution.png` / `.svg`

## 참고

- 실제 매치 로그에서 데이터를 추출해야 함. 위 수치는 M-CARE #020 케이스 리포트의 요약 — 로그 원본과 대조해서 정확한 수치 사용할 것.
- 시각적 스타일은 Paper #1의 Figure들 (React+D3 스타일)과 일관성 유지하면 좋음.
- Chess는 별도 Figure 불필요 — SIBO Index 0.10 (Negligible)이라 시각화할 만한 차이가 없음.
