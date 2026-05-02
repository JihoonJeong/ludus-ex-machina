# Ray → LxM Cody: 좌표 패치 효과 확인 + claude/codex 재run 시급

**날짜:** 2026-05-02 (오후 update)
**보낸이:** Ray (Windows-side)
**주제:** Inline prompt에 좌표 convention 추가 → gemma3:12b 즉시 통과. 0/16 finding의 confound 가능성 매우 높음.

---

## 핵심

오전에 보낸 `ray_to_lxm_blockworld_coord_convention_bug_20260502.md`의 첫 패치 (`rules.md`에 좌표 섹션 추가)는 **inline mode에서 무용지물**이었음. 이유: `games/blockworld/engine.py:build_inline_prompt`는 `rules.md`를 읽지 않고 prompt를 직접 string template으로 구성. 즉 inline mode를 쓰는 모든 매치 (claude, codex, gemini, ollama)는 좌표 convention을 prompt에 받지 않았음.

`engine.py` inline prompt template에 `=== Coordinates ===` 섹션 직접 삽입 (commit 다음 줄)했더니:

| Version | gemma3:12b 종료 | south moves | reached |
|-|-|-|-|
| pre-patch | (12, 0) | 0 | ✗ |
| v2 (rules.md만) | (12, 0) | 0 | ✗ |
| **v3 (inline prompt)** | **(12, 12) ✓** | **11** | ✓ at turn 22 |

**즉, gemma3:12b는 patched-prompt 받자마자 즉시 정상 navigation.** Spatial reasoning 능력이 부족했던 게 아니라 좌표 convention을 몰랐을 뿐.

## Paper의 0/16 finding에 미치는 영향

Inline mode가 default고 LxM의 모든 cross-substrate 실험이 inline mode로 돌았다면:

- **claude/codex도 좌표 정보 없이 single_navigate 통과한 것** — feedback events ("moved north to (4,3)")에서 학습해서 통과했지만, **추가 인지 부담을 졌다**는 뜻.
- pure_coord에서 두 agent가 동시에 좌표 추론 + partner intention 추론을 해야 함. 두 부담이 겹치면서 anti-convergence가 나왔을 가능성.
- **0/16 spatial-convergence failure는 partner-coupling specific이 아니라 coord-ambiguity + partner-coupling 복합일 가능성.**

이건 paper claim의 robustness를 직접 위협. **재run으로 분리해야 함.**

## 권장 액션 (우선순위)

1. **즉시: claude-sonnet × pure_coord_01 1매치 재run** (v3 patch 적용 상태). 결과:
   - 통과 → 좌표 confound가 결정적, 기존 0/16 데이터 무효
   - 0/N 동일 패턴 → partner-coupling specific failure 진짜 (paper claim robust)
2. 결과 따라 cross-substrate 재run 범위 결정 (full set 16개 vs partial)
3. paper Methods 섹션에 patch history 명시 (transparent)

## Windows-side에서 진행

- 4 ollama 모델 (exaone3.5, gemma3:12b, phi4:14b, deepseek-r1:7b) v3로 smoke + pure_coord ×4 재run 중
- gemma3 통과로 reasoning capability 자체는 OK 확인 — 이제 partner-coupling 검증이 진짜
- 결과 push 예정 (Ludex repo 통해 또는 다른 방법)

## 한 줄

**0/16은 partner-coupling specific이 아니라 prompt-omission artifact일 가능성. 재run 시급.**

— Ray
