"""Build docs/data/conquest.json from the public replay bundles.

The landing's Conquest Board renders from this file (docs/conquest.js), so a
new model attempt = run match -> export replay -> rerun this script; no more
hand-editing table rows. Scans docs/data/replays/*.json for conquest-eligible
games (mud worlds + three_kingdoms), keys attempts by (world, adapter:model),
and keeps the best attempt per key: solved (fewest turns) beats unsolved;
infra aborts (cliff_timeout) are ignored.

Curated tombstone notes (EN/KO) live in NOTES below; anything uncurated gets an
auto-generated note ("✦ N turns" / "✕ unsolved").

Usage: python scripts/build_conquest.py   (then commit docs/data/conquest.json)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPLAYS = ROOT / "docs" / "data" / "replays"
OUT = ROOT / "docs" / "data" / "conquest.json"

WORLDS = [
    {"id": "astronomer_tower", "game": "mud",
     "name": {"en": "The Astronomer's Tower", "ko": "천문학자의 탑"}},
    {"id": "grimhold_keep", "game": "mud",
     "name": {"en": "Grimhold Keep", "ko": "그림홀드 성채"}},
    {"id": "ss_erebus", "game": "mud",
     "name": {"en": "Derelict: SS Erebus", "ko": "표류선 SS 에레보스"}},
    {"id": "critter_cove", "game": "mud",
     "name": {"en": "Critter Cove", "ko": "크리터 코브"}},
    {"id": "red_cliffs", "game": "three_kingdoms",
     "name": {"en": "Three Kingdoms: Red Cliffs", "ko": "삼국지: 적벽대전"}},
]

MODEL_LABELS = {  # adapter:model -> column label; dict order = column order
    # frontier tier, per company (capability-descending within claude)
    "claude:fable": "claude · fable-5",  # CLI alias; resolves to claude-fable-5 (probe 2026-07-04)
    "claude:opus": "claude · opus-4.8",  # resolves to claude-opus-4-8
    "claude:sonnet": "claude · sonnet-5",  # resolves to claude-sonnet-5
    "codex:gpt-5.6-sol": "openai · gpt-5.6-sol",  # ChatGPT-acct 5.6 variant (probe 2026-07-11)
    "codex:gpt-5.6": "openai · gpt-5.6",  # plain 5.6 still API-key-only
    "codex:gpt-5.5": "openai · gpt-5.5",
    "gemini:gemini-3.1-pro": "google · gemini-3.1-pro",  # via agy CLI
    # light tier, per company
    "claude:haiku": "claude · haiku-4.5",
    "codex:gpt-5.6-mini": "openai · gpt-5.6-mini",  # X.5-mini was API-only on ChatGPT acct; probe first
    "codex:gpt-5.4-mini": "openai · gpt-5.4-mini",  # 5.5-mini needs API key (ChatGPT acct: 400)
    "gemini:gemini-3.5-flash": "google · gemini-3.5-flash",
    "ollama:gemma4:e4b": "ollama · gemma4",
}
_ORDER = {k: i for i, k in enumerate(MODEL_LABELS)}

# Curated per-cell notes; fall back to auto-generated text.
NOTES = {
    ("grimhold_keep", "claude:sonnet"): {
        "en": "✕ took the key, died at the gate (t40/50)",
        "ko": "✕ 열쇠는 얻었으나 성문 앞에서 사망 (t40/50)"},
    ("ss_erebus", "claude:sonnet"): {
        "en": "✕ loaded coolant, never ignited (0/55)",
        "ko": "✕ 냉각제는 넣었으나 점화 못 함 (0/55)"},
    ("critter_cove", "claude:sonnet"): {
        "en": "✕ questioned the ranger 30×, never left the beach (0/60)",
        "ko": "✕ 레인저를 30번 심문, 해변을 떠나지 않음 (0/60)"},
    ("red_cliffs", "claude:sonnet"): {
        "en": "✦ 13 turns · grade S (first try)",
        "ko": "✦ 13턴 · 그레이드 S (첫 도전)"},
}


def scan() -> dict:
    attempts: dict[tuple[str, str], dict] = {}
    for f in sorted(REPLAYS.glob("*.json")):
        try:
            b = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        cfg = b.get("config") or {}
        game = (cfg.get("game") or {}).get("name")
        if game not in ("mud", "three_kingdoms"):
            continue
        log = b.get("log") or []
        ctx = (log[0].get("post_move_context") or {}) if log else {}
        world = ctx.get("scenario_id")
        if world not in {w["id"] for w in WORLDS}:
            continue
        result = b.get("result") or {}
        outcome = result.get("outcome")
        if outcome in (None, "cliff_timeout"):        # infra abort, not a datum
            continue
        a0 = (cfg.get("agents") or [{}])[0]
        key = f"{a0.get('adapter', 'claude')}:{a0.get('model', 'sonnet')}"
        turns = len([e for e in log if e.get("result") == "accepted"])
        m = re.search(r"grade (\w)", result.get("summary", ""))
        att = {
            "model_key": key,
            "model_label": MODEL_LABELS.get(key, key),
            "outcome": "solved" if outcome == "solved" else "unsolved",
            "turns": turns,
            "grade": m.group(1) if m else None,
            "match_id": cfg.get("match_id", f.stem),
        }
        cur = attempts.get((world, key))
        better = (cur is None
                  or (att["outcome"] == "solved" and (cur["outcome"] != "solved" or att["turns"] < cur["turns"])))
        if better:
            attempts[(world, key)] = att

    for cell, att in MANUAL_ATTEMPTS.items():
        attempts.setdefault(cell, dict(att))  # scanned results always win

    model_keys = sorted({k for (_, k) in attempts},
                        key=lambda k: (_ORDER.get(k, len(_ORDER)), k))  # label order, unknowns last
    worlds_out = []
    for w in WORLDS:
        row = {"id": w["id"], "game": w["game"], "name": w["name"], "attempts": {}}
        solved_by = None
        for mk in model_keys:
            att = attempts.get((w["id"], mk))
            if not att:
                continue
            note = NOTES.get((w["id"], mk)) or att.get("note")
            if note is None:
                if att["outcome"] == "solved":
                    g = f" · grade {att['grade']}" if att["grade"] else ""
                    note = {"en": f"✦ {att['turns']} turns{g}", "ko": f"✦ {att['turns']}턴{g}"}
                else:
                    note = {"en": f"✕ unsolved ({att['turns']}t)", "ko": f"✕ 미해결 ({att['turns']}t)"}
            row["attempts"][mk] = {**att, "note": note}
            if att["outcome"] == "solved" and solved_by is None:
                solved_by = mk
        row["status"] = "solved" if any(a["outcome"] == "solved" for a in row["attempts"].values()) else "unconquered"
        worlds_out.append(row)

    return {"models": [{"key": mk, "label": MODEL_LABELS.get(mk, mk)} for mk in model_keys],
            "worlds": worlds_out,
            "creatures": CREATURES}


# Owner-judged cells the scan can't produce (e.g. an infra-aborted run whose
# clean prefix is decisive enough to judge). Merged only where no scanned
# attempt exists. No match_id -> the board cell renders without a replay link.
MANUAL_ATTEMPTS = {
    ("grimhold_keep", "claude:fable"): {
        "outcome": "unsolved",
        "turns": 42,
        "grade": None,
        "match_id": None,
        "note": {
            "en": "✕ 42 clean turns, 0/5 gates, moved twice — judged unsolved (run infra-aborted at t48)",
            "ko": "✕ 42턴 클린, 관문 0/5, 이동 2회 — 실패 판정 (t48 인프라 abort)",
        },
    },
}


# Creature lane — plane-verified runs (cross-machine, model + cognitive organs).
# Kept apart from the bare-model board: an organ-augmented run is a different
# category, so entries require (1) a clean plane record, (2) disclosed config
# (brain + organs), (3) owner approval. Curated by hand — the plane cannot
# see organ manifests (payload is 4-field+prompt by design).
CREATURES = [
    {
        "world": "critter_cove",
        "name": "Nimbus",
        "match_id": "live_5656b4eaeab8",  # Redis plane record; no static replay yet
        "note": {
            "en": "◆ solved in 33 turns — brain claude-haiku-4-5 (effort medium) + 13 organs incl. topos live-map & memory (Ludex, 2026-07-04)",
            "ko": "◆ 33턴 함락 — brain claude-haiku-4-5 (effort medium) + organ 13종 (topos live-map·memory 포함) (Ludex, 2026-07-04)",
        },
    },
]


def main():
    data = scan()
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    n_att = sum(len(w["attempts"]) for w in data["worlds"])
    print(f"conquest.json: {len(data['worlds'])} worlds x {len(data['models'])} models, {n_att} cells")
    for w in data["worlds"]:
        cells = ", ".join(f"{k}={a['outcome']}" for k, a in w["attempts"].items()) or "(no attempts)"
        print(f"  {w['id']:18} [{w['status']:11}] {cells}")


if __name__ == "__main__":
    main()
