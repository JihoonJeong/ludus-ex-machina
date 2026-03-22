# LxM Cross-Company Results

> Last updated: 2026-03-22. Avalon mixed still in progress.

## Head-to-Head: Claude vs Gemini

### Chess (6 games per matchup)

| Matchup | Claude | Gemini | Format |
|---------|--------|--------|--------|
| Opus vs 3.1 Pro | 0 | **6** | All checkmate |
| Sonnet vs 3.1 Pro | 0 (+1 draw) | **5** | |
| Sonnet vs Flash | 0 | **6** | All checkmate |
| Haiku vs Flash | 0 (+3 draws) | **3** | Flash wins by checkmate, Haiku survives to draw |
| **Total** | **0** | **20** (+4 draws) | |

### Poker Heads-Up (6 games per matchup)

| Matchup | Claude | Gemini | Format |
|---------|--------|--------|--------|
| Sonnet vs 3.1 Pro | **5** | 1 | |
| Opus vs 3.1 Pro | 3 | 3 | Even series (Opus led 3-1, Gemini won last 3) |
| **Total** | **8** | **4** | |

### Poker 3-Player

| Matchup | Claude | Gemini | Format |
|---------|--------|--------|--------|
| Sonnet vs 3.1 Pro | **8** | 2 | 10 games |

### Codenames (10 games per matchup, Haiku guesser)

| Tier | Claude | Gemini | GPT-5.4 |
|------|--------|--------|---------|
| Flagship (Opus/3.1Pro/GPT-5.4) | 35% | **60%** | 55% |
| Sonnet (Sonnet/3.1Pro/GPT-5.4) | 35% | 55% | **60%** |

### Trust Game

| Matchup | Result |
|---------|--------|
| Sonnet vs 3.1 Pro | 6/6 mutual cooperation (draw) |

### Avalon (5-player, 10 games each)

| Setup | Good Wins | Evil Wins | Notes |
|-------|-----------|-----------|-------|
| Baseline (all Sonnet) | 4 | **6** | |
| Cross-Company (Claude + Gemini) | 4 | **6** | |
| Mixed Mid-tier (Sonnet+Flash+Haiku+Flash×2) | **7** | 3 | Good dominant |
| Mixed Flagship (Opus+Pro+Haiku+Flash×2) | **6** | 4 | |

Key pattern: Same-model → Evil 60%. Mixed-model → **Good 65%**. Claude wins 83% as Good, only 25% as Evil (mid-tier).

## Summary Matrix

```
               Chess      Poker-HU   Poker-3P   Codenames   Trust    Avalon
Claude          0-20       8-4        8-2        35%         draw     Evil 60%
Gemini         20-0        4-8        2-8        55-60%      draw     Evil 60%
GPT-5.4         —          —(bug)     —          55-60%       —        —
```

## Key Findings

1. **No universal winner** across games
2. **Gemini dominates Chess** at every tier (20-0 +4 draws). Paradoxically, Haiku drew 3/6 while Opus/Sonnet drew 1/12
3. **Claude has Poker edge** — Sonnet 5-1, but Opus only 3-3. Tier matters here unlike Chess/Codenames
4. **Codenames: Claude weakest** — aggressive high-number clues lead to assassin hits
5. **Trust Game: no differentiation** — universal cooperation
6. **Tier effect is game-dependent** — Chess/Codenames: tier irrelevant. Poker: Sonnet 5-1 vs Opus 3-3 (bigger model ≠ better bluffing)
7. **GPT-5.4 incomplete** — Codex CLI bug invalidated poker data; rate limited until ~3/25

## In Progress

- [x] Chess Sonnet vs Flash — **Flash 6-0**
- [x] Poker Opus vs Gemini — **3-3 draw**
- [x] Chess Haiku vs Flash — **Flash 3-0 (+3 draws)**
- [x] Avalon mixed Mid-tier — **Good 7-3**
- [x] Avalon mixed Flagship — **Good 6-4**
- [ ] GPT-5.4 re-test (post rate-limit reset ~3/25)
