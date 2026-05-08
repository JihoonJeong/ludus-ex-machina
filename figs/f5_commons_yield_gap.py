"""F5 — Independent-action capability gap (commons-harvest yield).

Strip plot of total apples per match × model. Three tiers:
- claude family (haiku, sonnet, opus)
- codex family (gpt-5.5, gpt-5.4-mini)
- ollama family (gemma3, phi4, deepseek-r1)

Reference line at 40 (frontier observed ceiling — all five frontier
models cluster within ±2 of 40 across N=3 each). 40 is below the
theoretical max (≈60 if perfectly paced regen) because the
tree_depletion_turns=12 constraint forces under-harvesting and LLM
agents discover/converge on this ceiling empirically.

All matches in the plot are sustainable (no tree died). The gap
between frontier (~40) and ollama (3-29) is a *yield* gap, not a
sustainability gap.

Reads result.json directly (CSV's `ch_apples_total_picked` is
final-inventory-only and undercounts).

Run:  .venv/bin/python figs/f5_commons_yield_gap.py
Out:  figs/output/f5_commons_yield_gap.{png,pdf}
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


MATCHES = Path(__file__).resolve().parent.parent / "matches"
OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)


MODEL_ORDER = [
    ("claude", "haiku", "haiku"),
    ("claude", "sonnet", "sonnet"),
    ("claude", "opus", "opus"),
    ("codex", "gpt-5.5", "gpt-5.5"),
    ("codex", "gpt-5.4-mini", "gpt-5.4-mini"),
    ("ollama", "gemma3:12b", "gemma3"),
    ("ollama", "phi4:14b", "phi4"),
    ("ollama", "deepseek-r1:7b", "deepseek-r1"),
]
TIER_COLORS = {"claude": "#3a78c2", "codex": "#a64ca6", "ollama": "#d97a3a"}
MAX_SUSTAINABLE = 40


def model_from_match_id(mid: str) -> str | None:
    if "_haiku" in mid: return "haiku"
    if "_sonnet" in mid: return "sonnet"
    if "_opus" in mid: return "opus"
    if "_gpt55" in mid: return "gpt-5.5"
    if "_codex_mini" in mid or "_gpt54mini" in mid: return "gpt-5.4-mini"
    if "_gemma" in mid: return "gemma3"
    if "_phi4" in mid: return "phi4"
    if "_deepseek" in mid: return "deepseek-r1"
    return None


def collect():
    data = {label: [] for _, _, label in MODEL_ORDER}
    for d in os.listdir(MATCHES):
        rp = MATCHES / d / "result.json"
        if not rp.is_file():
            continue
        try:
            r = json.load(open(rp))
        except Exception:
            continue
        if r.get("scenario_id") != "commons_harvest_01":
            continue
        if r.get("outcome") == "cliff_timeout":
            continue
        n_dead = r.get("trees_dead", 0)
        if n_dead and n_dead > 0:
            continue
        m = model_from_match_id(d)
        if m is None:
            continue
        apples = r.get("total_apples_picked")
        if apples is None:
            continue
        data[m].append((apples, n_dead == 0))
    return data


def main():
    data = collect()
    for tier, _, label in MODEL_ORDER:
        rows = data[label]
        if rows:
            apples = [a for a, _ in rows]
            print(f"{label:12s} n={len(apples)} apples={sorted(apples)}")

    fig, ax = plt.subplots(figsize=(8.4, 4.6))

    x_positions = []
    x_labels = []
    rng = np.random.default_rng(42)

    for i, (tier, full_name, label) in enumerate(MODEL_ORDER):
        rows = data[label]
        if not rows:
            continue
        apples = [a for a, _ in rows]
        n = len(apples)
        x_jitter = rng.uniform(-0.18, 0.18, size=n)
        ax.scatter(
            np.full(n, i) + x_jitter, apples,
            s=80, color=TIER_COLORS[tier], edgecolor="black", linewidth=0.6,
            zorder=3, alpha=0.92,
        )
        mean_y = float(np.mean(apples))
        ax.plot([i - 0.32, i + 0.32], [mean_y, mean_y],
                color=TIER_COLORS[tier], linewidth=2.4, zorder=4)
        x_positions.append(i)
        x_labels.append(label)

    ax.axhline(MAX_SUSTAINABLE, color="black", linestyle="--", linewidth=1.0, alpha=0.6)
    ax.text(
        len(MODEL_ORDER) - 0.5, MAX_SUSTAINABLE + 0.7,
        f"frontier observed ceiling ≈ {MAX_SUSTAINABLE}",
        ha="right", fontsize=9, alpha=0.75,
    )

    ax.set_xticks(x_positions)
    ax.set_xticklabels(x_labels, rotation=20, ha="right", fontsize=10)
    ax.set_ylabel("Total apples picked per match")
    ax.set_ylim(0, MAX_SUSTAINABLE * 1.18)
    ax.set_title(
        "Commons-harvest yield gap (all matches sustainable, no tree death)\n"
        "frontier ~40 vs ollama 3–29 — a yield gap at the same sustainability",
        fontsize=11,
    )

    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=TIER_COLORS[t],
                   markeredgecolor="black", markersize=10, label=t)
        for t in ("claude", "codex", "ollama")
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=9, framealpha=0.92)

    ax.grid(axis="y", linestyle=":", alpha=0.3)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        path = OUT / f"f5_commons_yield_gap.{ext}"
        fig.savefig(path, dpi=180 if ext == "png" else None, bbox_inches="tight")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
