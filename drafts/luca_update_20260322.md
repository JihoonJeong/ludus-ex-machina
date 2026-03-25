# LxM Update for Luca — 2026-03-22

## TL;DR

Cross-company 실험 완료. **게임별로 승자가 다르고, 모델 크기보다 행동 패턴이 결과를 결정한다.**

---

## 1. Cross-Company Matrix (Claude vs Gemini)

```
               Chess       Poker-HU   Codenames   Trust    Avalon
Claude          0-20        8-4        35%         draw     see below
Gemini         20-0         4-8        55-60%      draw     see below
GPT-5.4         —           —(bug)     55-60%       —        —
```

### Chess: Gemini 20-0 (+4 draws)
- Opus vs 3.1 Pro: **Gemini 6-0** (all checkmate)
- Sonnet vs 3.1 Pro: **Gemini 5-0** (+1 draw)
- Sonnet vs Flash: **Flash 6-0** (all checkmate)
- Haiku vs Flash: **Flash 3-0** (+3 draws)
- 전 tier에서 Claude 전패. **Haiku가 3무로 Opus/Sonnet(1무/12)보다 오히려 생존율 높음** — Poker "Haiku > Opus" 패턴과 일치.
- 참고: Claude 가족 내 18판은 89% 무승부 → "차이 없음"이 아니라 "서로 비슷해서 비김"이었다는 것이 확인됨.

### Poker HU: Claude 8-4
- Sonnet vs 3.1 Pro: **Claude 5-1**
- Opus vs 3.1 Pro: **3-3** (Opus 3-1 리드 후 Gemini 3연승)
- Gemini 폴드율 47% — 너무 수동적.
- 포커는 모델 크기와 무관 — **Sonnet(5-1)이 Opus(3-3)보다 오히려 강함.** Within-family에서도 Haiku > Sonnet > Opus(heads-up). Cross-company에서도 같은 패턴 재현.

### Codenames: Claude 35% (양 tier)
- Opus와 Sonnet **동일하게 35%**. 모델 크기 효과 없음.
- Claude clue number 평균 2.4-2.6 (가장 공격적) → assassin 히트.
- Gemini가 가장 보수적(1.9)이면서 가장 강함.

### Avalon: 동일 모델 vs 혼합 팀에서 결과 반전

| Setup | Good | Evil |
|-------|------|------|
| Baseline (all Sonnet) | 4 | **6** |
| CC (Claude+Gemini 동일 tier) | 4 | **6** |
| **Mixed Mid-tier** (Sonnet+Flash+Haiku+Flash×2) | **7** | 3 |
| **Mixed Flagship** (Opus+Pro+Haiku+Flash×2) | **6** | 4 |

- 동일 모델 → Evil 60%. 혼합 모델 → **Good 65%**. 완전 반전.
- Claude가 Good일 때 83% 승률, Evil일 때 25% — **협력에 강하고 기만에 약함**.
- 해석: 서로 다른 모델이 섞이면 Evil 간 조율이 어려워짐. Good은 조율 없이 각자 탐지만 하면 됨.

### Trust Game: 전원 협력
- 6/6 mutual cooperation. 차별화 없음.

---

## 2. Shell Competition + SIBO Spectrum (5게임 완성)

Avalon 65게임. Evil shell에 따라 **0%~100% 승률 스윙**.
- Shell이 role보다 결과에 더 큰 영향 (SIBO 현상).

SIBO Spectrum 최종 (5게임):

| Game | SIBO Index | Mode |
|------|-----------|------|
| Trust Game | ~0.75 | Reversal |
| Poker | ~0.65 | Behavioral override |
| Avalon | ~0.58 | Behavioral shift |
| Codenames | ~0.35 | Amplification |
| Chess | ~0.10 | Negligible |

Poker SIBO: 3종 Shell(TAG/Bluff-Heavy/Loose-Passive) 전부 지시대로 정확히 작동. PF-fold 52%→91%(TAG), raise 21%→52%(Bluff), check 23%→65%(LP).

---

## 3. Platform

- Viewer: 6게임 렌더러, 로비, 로그인, 매치 히스토리
- Server: FastAPI + Upstash Redis + GitHub OAuth
- Landing: jihoonjeong.github.io/ludus-ex-machina/ (EN/KO)
- 4 adapters: Claude CLI, Gemini CLI, Codex CLI, Ollama
- 배포: 준비됨 but 미결정 (Render $7/mo vs Fly.io)

---

## 4. 논문 핵심 주장 후보

1. **"No Universal Winner"** — 게임 유형에 따라 승자가 바뀜.
2. **"Behavioral Signatures > Model Size"** — Opus≠Sonnet보다 Claude≠Gemini 차이가 훨씬 큼.
3. **"Cooperation vs Deception Asymmetry"** — Claude는 협력에 강하고 기만에 약함. 혼합팀에서 결과 반전.
4. **"Shell Injection as Behavioral Intervention"** — System prompt로 0-100% 스윙. (Avalon Cross-Shell, Poker SIBO 3종, SIBO Spectrum 5게임)
5. **"Within-Family Comparison is Insufficient"** — 같은 가족 내 결론이 cross-company에서 뒤집힘. (Chess: 무승부→전패, Codenames: 70%→35%)

---

## 5. Next Steps

1. GPT-5.4 재테스트 (3/25 rate limit 리셋 후)
2. 배포 결정
3. Paper 2 figure 업데이트
