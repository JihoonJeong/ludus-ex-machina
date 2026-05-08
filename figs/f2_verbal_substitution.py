"""F2 — Verbal-commitment-substitution (claude family, pc01/02/03).

Bar chart of meet-rate (left axis) + mean messages-per-match (right
axis) across silent/chat/attached variants. The headline visual:
same volume of communication (pc02 ~13/agent vs pc03 ~16/agent),
opposite outcomes (0/3 vs 3/3).

Filters to claude family v3 matches only; codex pc02/pc03 fill is
pending so it is intentionally excluded from the headline plot.

Run:  .venv/bin/python figs/f2_verbal_substitution.py
Out:  figs/output/f2_verbal_substitution.{png,pdf}
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


CSV = Path(__file__).resolve().parent.parent / "blockworld_metrics.csv"
OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)


CLAUDE_MODELS = ("haiku", "sonnet", "opus")
SCENARIOS = ("pure_coord_01", "pure_coord_02", "pure_coord_03")
LABELS = {
    "pure_coord_01": "pc01 silent",
    "pure_coord_02": "pc02 chat\n(standalone say)",
    "pure_coord_03": "pc03 attached\n(message + action)",
}


def is_v3_claude(row: dict) -> bool:
    if row["a_adapter"] != "claude":
        return False
    if row["a_model"] not in CLAUDE_MODELS:
        return False
    sid = row["scenario_id"]
    mid = row["match_id"]
    # pc01: v3-suffixed matches only (exclude pre-v3 + _patched intermediate).
    if sid == "pure_coord_01":
        return "_v3_" in mid
    # pc02: all matches are v3-suffixed.
    if sid == "pure_coord_02":
        return "_v3_" in mid
    # pc03: matches have no v3 suffix (just `_<model>_001`); engine uses
    # v3 prompt for all pc03 since the scenario was added post-patch.
    if sid == "pure_coord_03":
        return mid.startswith("pure_coord_03_")
    return False


def collect():
    rows_per_sid = defaultdict(list)
    for row in csv.DictReader(open(CSV)):
        sid = row["scenario_id"]
        if sid not in SCENARIOS:
            continue
        if not is_v3_claude(row):
            continue
        if row["outcome"] == "cliff_timeout":
            continue
        rows_per_sid[sid].append(row)
    return rows_per_sid


def main():
    data = collect()

    met_rate = []
    mean_msgs = []
    n_per = []
    for sid in SCENARIOS:
        rows = data[sid]
        n = len(rows)
        met = sum(1 for r in rows if r.get("pc_met") == "True")
        # pc01/pc02 use say_count; pc03 uses attached_message_count.
        if sid == "pure_coord_03":
            msg_field = "attached_message_count"
        else:
            msg_field = "say_count"
        msgs_per_match = []
        for r in rows:
            a = int(r.get(f"a_{msg_field}") or 0)
            b = int(r.get(f"b_{msg_field}") or 0)
            msgs_per_match.append(a + b)
        met_rate.append(100 * met / n if n else 0)
        mean_msgs.append(np.mean(msgs_per_match) if msgs_per_match else 0)
        n_per.append(n)
        print(f"{sid}: n={n}, met={met}/{n} ({met_rate[-1]:.0f}%), mean_msgs/match={mean_msgs[-1]:.1f}")

    fig, ax_left = plt.subplots(figsize=(7.0, 4.4))
    ax_right = ax_left.twinx()

    x = np.arange(len(SCENARIOS))
    bar_w = 0.36

    bars_met = ax_left.bar(
        x - bar_w / 2, met_rate, width=bar_w,
        color="#3a78c2", edgecolor="black", label="meet rate (%)",
    )
    bars_msg = ax_right.bar(
        x + bar_w / 2, mean_msgs, width=bar_w,
        color="#d97a3a", edgecolor="black", alpha=0.85,
        label="mean messages / match",
    )

    for bar, val, n in zip(bars_met, met_rate, n_per):
        ax_left.text(
            bar.get_x() + bar.get_width() / 2,
            val + 2.0, f"{val:.0f}%\n(n={n})",
            ha="center", va="bottom", fontsize=9,
        )
    for bar, val in zip(bars_msg, mean_msgs):
        ax_right.text(
            bar.get_x() + bar.get_width() / 2,
            val + 0.6, f"{val:.0f}",
            ha="center", va="bottom", fontsize=9,
        )

    ax_left.set_xticks(x)
    ax_left.set_xticklabels([LABELS[s] for s in SCENARIOS])
    ax_left.set_ylabel("Meet rate (%)")
    ax_left.set_ylim(0, 115)
    ax_right.set_ylabel("Mean messages per match")
    ax_right.set_ylim(0, max(mean_msgs) * 1.5 + 5)

    ax_left.set_title(
        "Same communication volume, opposite outcomes\n"
        "claude haiku/sonnet/opus × pure_coord variants (v3-patched)",
        fontsize=11,
    )

    ax_left.annotate(
        "", xy=(2, 102), xytext=(1, 102),
        arrowprops=dict(arrowstyle="->", color="black", lw=1.5),
    )
    ax_left.text(
        1.5, 108, "0% → 100%\nat constant message volume",
        ha="center", fontsize=9, fontweight="bold",
    )

    handles = [bars_met, bars_msg]
    ax_left.legend(handles=handles, loc="upper left", fontsize=9)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        path = OUT / f"f2_verbal_substitution.{ext}"
        fig.savefig(path, dpi=180 if ext == "png" else None, bbox_inches="tight")
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
