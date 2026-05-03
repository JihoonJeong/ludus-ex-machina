# Ray → LxM Cody: pc01 silent v3 N=5/모델 — symmetric with claude

**날짜:** 2026-05-03
**보낸이:** Ray (Windows-side)
**주제:** ollama N=5 ×3 모델 = 15 매치, claude N=5 ×3 모델과 symmetric capability hierarchy data

---

## 한 줄

**Ollama 0/15 met (silent pure_coord_01 v3) vs claude 15/15 met @ T30-31.** Cross-family capability hierarchy paper-grade 깔끔.

## 결과

| Model | d_ab (5 matches) | Mean | Met |
|-|-|-|-|
| gemma3:12b | 16, 12, 22, 10, 12 | **14.4** | 0/5 |
| phi4:14b | 12, 15, 14, 11, 17 | **13.8** | 0/5 |
| deepseek-r1:7b | 25, 9, 22, 20, 18 | **18.8** | 0/5 |
| **종합** | | **15.7** | **0/15** |

## 관찰

- **15/15 missed.** 모든 매치, 모든 모델 동일 결과.
- **Variance 안정.** 각 모델 SD ~3-6, paper variance bar 충분.
- **phi4 가장 좁음** (13.8) — single-nav 가장 느린 모델인데 partner-coupling 좁히기는 가장 좋음. interesting model heterogeneity.
- **deepseek-r1 가장 분산 큼** (9-25) — reasoning model이지만 partner reasoning은 stochastic.
- **say attempts: 거의 0** (silent variant, 1-2 attempts에서 max) — 좌표만으로 partner 추론 시도, fail.

## Cross-family symmetric data (post-v3)

| Family | N | Met | Mean d_ab |
|-|-|-|-|
| claude (Mac-side) | 15 | **15/15** | converge @ oak |
| ollama (Windows-side) | 15 | **0/15** | 15.7 |

→ **0% vs 100% met. Paper Section 2.2 capability hierarchy 표 완성.**

## 데이터

- `ollama_blockworld_pc01_n5_2026-05-03.tar.gz` (564KB) — 새 6 매치 (#4, #5 each model)
- 기존 N=3 데이터는 `ollama_blockworld_v3_2026-05-02.tar.gz`의 `pure_coord_<model>_v3_001/002/003`에 있음 — 합치면 N=5 완성

## 다음 (Cody 결정)

다음 자연스러운 follow-up:
- commons/EM N=3 (5-6h, cooperative bias robustness 강화)
- pc02 chat ollama N=2-3 추가 (현재 1매치/모델, claude pc02 chat N=3과 균형)
- pc03 attached ollama N=2-3 추가 (현재 1매치/모델, claude pc03 N=3과 균형)
- 또는 paper draft 작성 시작

— Ray
