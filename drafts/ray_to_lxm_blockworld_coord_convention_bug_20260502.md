# Ray (Cody, Windows-side) → LxM Cody: Blockworld 좌표 convention 누락 — confound risk

**날짜:** 2026-05-02
**보낸이:** Ray (Windows-side, ollama 매치 caretaker)
**주제:** `games/blockworld/rules.md` 좌표 convention 미명시 → spatial-convergence finding confound 가능성

---

## 한 줄

`rules.md`가 north/south가 y축 어느 방향인지 명시 안 함. ollama 4모델 (exaone3.5/gemma3:12b/phi4:14b/deepseek-r1:7b) 전부 잘못된 방향으로 갔고, 이건 paper의 0/16 spatial-convergence 결과에 confound로 작용할 수 있음. 패치 + 재run 권장.

## 발견 경위

오늘 ollama 매치 시작 — qwen3.5:4b는 schema fail, 그 다음 exaone3.5:7.8b부터 schema 통과했지만 single_navigate (4,4)→(12,12)에서 0/4 모델 모두 nav fail. 종료 위치가 일관되게:

| 모델 | smoke 종료 | 패턴 |
|---|---|---|
| exaone3.5:7.8b | (23, 0) | east edge + north edge |
| gemma3:12b | (12, 0) | x정확, y=0 (target y=12) |
| phi4:14b | (12, 1) | x정확, y=1 (target y=12) |
| deepseek-r1:7b | (12, 0) | x정확, y=0 (target y=12) |

**3개 모델이 x는 12로 잡았지만 y는 정반대 방향으로 갔음.** JJ가 "게임 규칙이나 설정이 잘못된 것 아닌가" 의심해서 조사.

## 원인

`games/blockworld/world.py:56-63`:
```python
DIRECTIONS = {
    "north": (0, -1, 0),  # north = y 감소 (screen convention)
    "south": (0, 1, 0),   # south = y 증가
    ...
}
```

**Screen convention** (y=0이 화면 상단=north). 하지만:
- `rules.md`에 이 매핑 명시 안 됨
- Agent prompt에 `Position: (4, 4, 1) facing north` + `Goal: Reach the target cell (12,12,1)`만 제공
- `last_events: ["moved north to (4,3)"]` feedback이 indirect 힌트는 주지만, 명시적 convention 안내는 없음

**모델 prior는 보통 수학 convention (north=y증가).** 그래서 (4,4)에서 y=12로 가려고 north 방향을 택함. 결과: y=0 코너에 박힘.

claude family는 feedback에서 빠르게 학습해서 통과. 작은 ollama 모델은 prior가 강해서 update 안 됨.

## 우려 (paper-grade)

이건 **단지 ollama 한정 문제가 아닐 수도** 있어요. claude/codex의 0/16 spatial-convergence failure도 일부는 이 좌표 ambiguity 때문일 가능성 있음:

- claude는 single_navigate를 통과했지만, pure_coord에서 두 agent가 서로의 위치를 추론할 때 좌표축 prior가 미세하게 영향 줄 수 있음
- "north로 와줘"라는 chat 메시지가 협력 파트너에게 어느 y 방향으로 해석될지 ambiguous
- 4-agent commons_harvest, multi-agent coord 매치 등 더 복잡한 곳에서도 영향 가능

**즉, 현재의 0/16 결과는 partner-coupling specific failure + coord-convention friction이 섞여 있을 수 있음.** 명시적으로 분리하지 않으면 paper claim의 robustness가 약해짐.

## 수정한 것 (Windows-side에서 이미 commit)

`games/blockworld/rules.md`에 `### Coordinate convention (IMPORTANT)` 섹션 추가. North/south/east/west와 x/y 매핑 명시 + "screen convention, not math convention" 명시.

```markdown
| `move north` | y decreases by 1 (toward y=0) |
| `move south` | y increases by 1 (toward y=max) |
| `move east`  | x increases by 1 (toward x=max) |
| `move west`  | x decreases by 1 (toward x=0) |
| `move up`    | z increases by 1 (next layer up) |
| `move down`  | z decreases by 1 (next layer down) |
```

## 부탁 / 제안

1. **claude family 매치 재run 검토.** 기존 0/16 데이터는 "with coord convention ambiguity" 단서를 달거나, 패치 후 재run으로 clean 데이터 확보. 후자가 paper에 강함.
2. **Codex/Gemini 매치도 마찬가지.** Cross-substrate 6개 다 영향.
3. **gemini-cli adapter 호환성 별개 이슈는 그대로 한계로 유지** — coord 패치로 해결되는 게 아님.
4. 이미 commit 한 패치 위에서 결정해주세요. 추가 wording 조정 필요하면 ping 부탁.

## Windows-side에서 다음

- ollama 4모델 (exaone3.5/gemma3:12b/phi4:14b/deepseek-r1:7b) 패치된 rules로 smoke + pure_coord ×4 재run
- 끝나면 결과 push + 비교 (pre-patch vs post-patch ollama 데이터 모두 보존)
- claude/codex 재run은 Mac-side 결정 따름 (resource 부담 큼)

— Ray
