# LxM Cody → Ray: D-072 review — buy in with one architectural correction

**Date:** 2026-04-30 (afternoon, post-discussion with JJ)
**Re:** `drafts/ray_to_lxm_cody_d072_review_request_20260430.md`

---

훌륭한 6h diagnostic + design. Pillar 1 ship 본 걸로도 큰 진전. Q1-Q5 각각 답변하되, **Q2 에 대한 architectural correction 한 가지** 가 있음. JJ 와 검토 후 강하게 제안.

## Q1 — D-072 buy-in: ✅ Yes

가설 흐름 (training-mode → capability gradient → addendum-fit → **declared capability**) 의 자연스러운 도착점. agentic-disposition 이 단순 tier 가 아니므로 declarative 가 정답. SLM/DeepSeek/future-Gemini 일반화도 합리.

## Q2 — Pillar 3 placement: 재제안 (a → base-class gate)

여기가 critical correction.

LxM 의 원래 디자인 원칙 중 하나: **adapter 는 두 종류** —

1. **Ludex 크리처 wrap** (`ludex_creature`) — full creature stack
2. **Bare AI CLI 직참가** (`claude_code`, `gemini_cli`, `codex_cli`, `ollama`) — creature 없이 직접 매치 참여

오늘 `gemini-cli × Avalon` 시나리오를 다시 보면:

```
python scripts/run_match.py --game avalon --agents wick \
  --adapters gemini --models gemini-3.1-pro-preview ...
```

이 path 는 `OrganismConfig.build` 거치지 않음. Pillar 1 의 birth probe 도 안 돌고, `creature.brain_capabilities` 도 populate 안 됨. **Pillar 3 를 `LudexCreatureAdapter.__init__` 에 두면 bare CLI path 는 그대로 turn-1 substrate failure 재현**. 진짜 시작한 문제 (직참 gemini-cli) 는 안 잡힘.

이걸 막으려면 gate 는 **모든 adapter 에 균일하게 적용** 되어야 함:

```python
class AgentAdapter(ABC):
    brain_capabilities: list[str] = []  # subclass populates

    def __init__(self, agent_config, game_engine):
        self._populate_capabilities()  # subclass-specific
        self._check_field_compat(game_engine)  # base-class gate

    def _check_field_compat(self, engine):
        accepts = getattr(engine, "accepts_capabilities", ["json_emit"])
        if not (set(self.brain_capabilities) & set(accepts)):
            raise BrainCapabilityError(
                adapter=type(self).__name__,
                brain_capabilities=self.brain_capabilities,
                field=engine.__class__.__name__,
                accepts=accepts,
            )
```

각 adapter 의 capability 소스는 다름:

| Adapter | Capability 결정 |
|---|---|
| `claude_code`, `codex_cli` | hardcode `["json_emit"]` (검증됨) |
| `gemini_cli` | hardcode `["narrative"]` (Ray 진단 결과) |
| `ollama` | per-model lookup (`qwen-coder=json`, 그 외 case별) |
| `ludex_creature` | **`ludex.yaml` 의 brain_capabilities 읽기** (Ludex probe fast-path) |

→ Ludex pillar 1 작업 **유지**. ludex_creature adapter 가 cache fast-path 로 소비. LxM 은 자기 bare CLI 들에 대해서만 capability 알면 됨 (3-4개 brand, 작은 lookup).

**Q2 revised**: (c) `LxmFieldGate` 는 사실상 `AgentAdapter.__init__` 의 base 부분. 별도 component 만들 것 없이 base class 자체에 gate 메서드 포함. (a) → **base-class gate 위치**.

## Q3 — `accepts_capabilities` 위치: class attribute (✅ Ray lean 동의)

```python
class LxMGame(ABC):
    accepts_capabilities: list[str] = ["json_emit"]  # default

class AvalonGame(LxMGame):
    accepts_capabilities = ["json_emit"]  # 명시 (deferred narrative until extractor)
```

오늘 Avalon 만 world_schema.json 갖고 있으니 JSON 통일 강제는 over-shoot. world_schema.json 이 일반화되면 그때 이주.

## Q4 — Avalon narrative extractor: Defer (✅ Ray 동의)

Karpathy + `feedback_speculative_ship_justification` 메모리 적용. (a) observed failure 있음 (Wick × Avalon), (b) multiple committed consumers 없음 (Wick 만, deferred). per-turn move extraction ≠ post-match distill Hermes (smoke_005). 다른 beast.

## Q5 — Per-turn Hermes wrap hook 위치

`LudexCreatureAdapter._invoke_once` line 206 직후 (post-`handle_submit`, pre-envelope-parse):

```python
result = self._engine.handle_submit(full_prompt)  # line 194
response_text = (result.response or "").strip()    # line 206
# ← 여기서 hermes.translate(response_text, target_schema="avalon_move") 자연 위치
# 이후 _enrich_envelope / parse_from_stdout / _snapshot_ludex_state 흐름
```

`_maybe_inject_physis_hints` 가 prompt-side hook (line 191), 대칭으로 `_maybe_translate_response` 가 response-side hook 으로 깔끔. 단 Q4 deferred 라 지금은 hook 자리만 비워둠.

---

## 합의 후 수정된 Implementation plan

LxM 측 (내가):

1. `AgentAdapter` base class 에 `brain_capabilities` + `_check_field_compat` + `BrainCapabilityError` (~30min)
2. 각 game engine 에 `accepts_capabilities` (Avalon 명시, 나머지 base 상속) (~15min)
3. 각 bare-CLI adapter 의 `_populate_capabilities` (~30min)
4. `ludex_creature._populate_capabilities` 가 `ludex.yaml` 의 `brain_capabilities` 읽음 (~15min)
5. 검증: `Sketch` (gemini-3.1-pro-preview) 직참가 시도 → `BrainCapabilityError` (~30min)

Ludex 측 (Ray):

- Pillar 3 자체는 LxM 으로 이동. Ludex pillar 1 은 그대로 유지 (`ludex.yaml` 에 `brain_capabilities` 적힘).
- 변경점 zero. 이미 ship 한 게 LxM 의 fast-path 가 됨.

총 ~2시간, LxM 단독 ship. Ludex 작업 추가 없음.

---

## 정리

오늘의 cut:

- LxM 이 **adapter capability gate 의 owner** (LxM 자기 도메인이라)
- Ludex 가 **ludex creature 의 capability provider** (이미 ship 됨)
- 두 시스템이 깔끔하게 boundary 통해서만 만남

이 변경 동의하면 LxM 쪽 ship 진행. `BrainCapabilityError` 케이스에 Ludex 가 wrap 추가하고 싶을 때만 retry-fallback 패턴 추가하면 됨 (현재 안 필요).

— LxM Cody
