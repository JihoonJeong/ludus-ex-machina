"""Generate Paper #2 figures from LxM match data.

Outputs:
  - fig-trustgame-heatmap.png/.svg
  - fig-avalon-sabotage-timing.png/.svg
  - fig-codenames-clue-distribution.png/.svg
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

MATCHES = Path(__file__).parent.parent / "matches"
OUTPUT = Path.home() / "Projects" / "model-medicine" / "Paper2" / "figures"
OUTPUT.mkdir(parents=True, exist_ok=True)

# Paper style
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Helvetica', 'Arial', 'DejaVu Sans'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
})

# Colors
C_GREEN = '#2ecc71'
C_RED = '#e74c3c'
C_ORANGE = '#f39c12'
C_BLUE = '#3498db'
C_GRAY = '#95a5a6'


# ── Figure 1: Trust Game Heatmap ─────────────────────────

def load_trust_game_data():
    """Load Shell OFF and Shell ON trust game histories."""
    # Shell OFF: trustgame_noshell_v1 or trustgame_sonnet_noshell_v1
    shell_off = []
    for prefix in ['trustgame_noshell_v1', 'trustgame_sonnet_noshell_v1']:
        for i in range(1, 11):
            sp = MATCHES / f"{prefix}_r{i:02d}" / "state.json"
            if sp.exists():
                s = json.loads(sp.read_text())
                hist = s['game']['context'].get('history', [])
                shell_off.append(hist)
        if shell_off:
            break

    # Shell ON: trustgame_sibo_crossmodel_v1
    shell_on = []
    for i in range(1, 11):
        sp = MATCHES / f"trustgame_sibo_crossmodel_v1_r{i:02d}" / "state.json"
        if sp.exists():
            s = json.loads(sp.read_text())
            hist = s['game']['context'].get('history', [])
            shell_on.append(hist)

    return shell_off, shell_on


def classify_round(rnd):
    """Classify a round as CC, DD, or CD/DC."""
    agents = [k for k in rnd.keys() if k not in ('round', 'payoffs')]
    if len(agents) < 2:
        return 'unknown'
    a0, a1 = rnd[agents[0]], rnd[agents[1]]
    if a0 == 'cooperate' and a1 == 'cooperate':
        return 'CC'
    elif a0 == 'defect' and a1 == 'defect':
        return 'DD'
    else:
        return 'CD'


def fig_trustgame_heatmap():
    shell_off, shell_on = load_trust_game_data()

    if not shell_off or not shell_on:
        print("Warning: Missing trust game data, skipping Figure 1")
        return

    # Determine max rounds
    max_rounds = max(
        max(len(h) for h in shell_off) if shell_off else 0,
        max(len(h) for h in shell_on) if shell_on else 0,
    )
    max_rounds = min(max_rounds, 25)  # Cap for readability

    n_off = len(shell_off)
    n_on = len(shell_on)
    total_rows = n_off + n_on + 1  # +1 for separator

    # Build color matrix
    color_map = {'CC': C_GREEN, 'DD': C_RED, 'CD': C_ORANGE, 'unknown': '#cccccc'}

    fig, ax = plt.subplots(figsize=(16 / 2.54 * 1.2, total_rows * 0.35 + 1.5))

    for group_idx, (games, label, y_offset) in enumerate([
        (shell_off, 'Shell OFF', 0),
        (shell_on, 'Shell ON', n_off + 1),
    ]):
        for game_idx, hist in enumerate(games):
            y = y_offset + game_idx
            for rnd_idx in range(max_rounds):
                if rnd_idx < len(hist):
                    cat = classify_round(hist[rnd_idx])
                    color = color_map[cat]
                else:
                    color = '#f0f0f0'
                rect = mpatches.FancyBboxPatch(
                    (rnd_idx, total_rows - 1 - y - 0.9), 0.85, 0.75,
                    boxstyle="round,pad=0.05",
                    facecolor=color, edgecolor='white', linewidth=0.5,
                )
                ax.add_patch(rect)

    # Labels
    ax.set_xlim(-0.5, max_rounds + 0.5)
    ax.set_ylim(-0.5, total_rows)
    ax.set_xlabel('Round')
    ax.set_xticks(np.arange(0, max_rounds, 2) + 0.4)
    ax.set_xticklabels([str(i + 1) for i in range(0, max_rounds, 2)])

    # Y-axis: group labels
    ax.set_yticks([])
    mid_off = total_rows - 1 - (n_off / 2)
    mid_on = total_rows - 1 - (n_off + 1 + n_on / 2)
    ax.text(-1.5, mid_off, 'Shell OFF\n(Core only)', ha='right', va='center', fontsize=10, fontweight='bold')
    ax.text(-1.5, mid_on, 'Shell ON\n(Aggressive)', ha='right', va='center', fontsize=10, fontweight='bold')

    # Separator line
    sep_y = total_rows - 1 - n_off - 0.1
    ax.axhline(y=sep_y, color='#333333', linewidth=1, linestyle='--', alpha=0.5)

    # Legend
    legend_patches = [
        mpatches.Patch(color=C_GREEN, label='Mutual Cooperation (C-C)'),
        mpatches.Patch(color=C_RED, label='Mutual Defection (D-D)'),
        mpatches.Patch(color=C_ORANGE, label='Betrayal (C-D / D-C)'),
    ]
    ax.legend(handles=legend_patches, loc='upper right', framealpha=0.9)

    ax.set_title('Trust Game: Shell OFF vs Shell ON — Round-by-Round Behavior', fontsize=13, pad=12)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_visible(True)

    for fmt in ['png', 'svg']:
        fig.savefig(OUTPUT / f'fig-trustgame-heatmap.{fmt}', facecolor='white')
    plt.close(fig)
    print(f"  Figure 1 saved: {OUTPUT / 'fig-trustgame-heatmap.png'}")


# ── Figure 2: Avalon Sabotage Timing ─────────────────────

def fig_avalon_sabotage_timing():
    shell_off_sab = []
    shell_on_sab = []

    for i in range(1, 11):
        for prefix, target in [('avalon_shell_off', shell_off_sab), ('avalon_shell_on', shell_on_sab)]:
            sp = MATCHES / f"{prefix}_r{i:02d}" / "state.json"
            if sp.exists():
                s = json.loads(sp.read_text())
                ctx = s['game']['context']
                for q in ctx.get('all_quests', []):
                    if not q['success']:
                        target.append(q['quest'])
                        break

    if not shell_off_sab and not shell_on_sab:
        print("Warning: Missing Avalon data, skipping Figure 2")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16 / 2.54 * 1.2, 5), sharey=True)

    quests = [1, 2, 3, 4, 5]

    for ax, data, label, color in [
        (ax1, shell_off_sab, 'Shell OFF', C_RED),
        (ax2, shell_on_sab, 'Shell ON\n(Deep Cover)', C_BLUE),
    ]:
        counts = [data.count(q) for q in quests]
        bars = ax.bar(quests, counts, color=color, alpha=0.8, edgecolor='white', linewidth=1)
        ax.set_xlabel('Quest Number')
        ax.set_xticks(quests)
        ax.set_title(label, fontsize=11, fontweight='bold')

        # Annotate bars
        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15,
                        str(count), ha='center', va='bottom', fontsize=10, fontweight='bold')

        # Mean line
        if data:
            mean = sum(data) / len(data)
            ax.axvline(x=mean, color='#333333', linestyle='--', linewidth=1.5, alpha=0.7)
            ax.text(mean + 0.15, ax.get_ylim()[1] * 0.85, f'μ={mean:.1f}',
                    fontsize=9, fontstyle='italic')

    ax1.set_ylabel('Number of Games')
    fig.suptitle('Avalon: First Sabotage Timing — Shell OFF vs Shell ON',
                 fontsize=13, y=1.02)
    fig.tight_layout()

    for fmt in ['png', 'svg']:
        fig.savefig(OUTPUT / f'fig-avalon-sabotage-timing.{fmt}', facecolor='white')
    plt.close(fig)
    print(f"  Figure 2 saved: {OUTPUT / 'fig-avalon-sabotage-timing.png'}")


# ── Figure 3: Codenames Clue Distribution ─────────────────

def fig_codenames_clue_distribution():
    noshell_clues = []
    shell_clues = []

    for i in range(1, 11):
        for prefix, target in [('codenames_sibo_noshell', noshell_clues), ('codenames_sibo_shell', shell_clues)]:
            sp = MATCHES / f"{prefix}_r{i:02d}" / "state.json"
            if sp.exists():
                s = json.loads(sp.read_text())
                ctx = s['game']['context']
                for clue in ctx.get('clue_history', []):
                    target.append(clue.get('number', 1))

    if not noshell_clues and not shell_clues:
        print("Warning: Missing Codenames data, skipping Figure 3")
        return

    # Bin into 1, 2, 3, 4+
    categories = ['1', '2', '3', '4+']

    def bin_clues(clues):
        bins = [0, 0, 0, 0]
        for n in clues:
            if n <= 0:
                continue
            elif n == 1:
                bins[0] += 1
            elif n == 2:
                bins[1] += 1
            elif n == 3:
                bins[2] += 1
            else:
                bins[3] += 1
        total = sum(bins)
        return [b / total * 100 if total else 0 for b in bins]

    off_pct = bin_clues(noshell_clues)
    on_pct = bin_clues(shell_clues)

    fig, ax = plt.subplots(figsize=(16 / 2.54, 5))

    x = np.arange(len(categories))
    width = 0.35

    bars1 = ax.bar(x - width / 2, off_pct, width, label='Shell OFF (Core)', color=C_GRAY, edgecolor='white')
    bars2 = ax.bar(x + width / 2, on_pct, width, label='Shell ON (Aggressive)', color=C_RED, alpha=0.8, edgecolor='white')

    ax.set_xlabel('Clue Number')
    ax.set_ylabel('Proportion (%)')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.set_title('Codenames: Clue Number Distribution — Shell OFF vs Shell ON', fontsize=13, pad=12)

    # Annotate
    for bars in [bars1, bars2]:
        for bar in bars:
            h = bar.get_height()
            if h > 2:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 1,
                        f'{h:.0f}%', ha='center', va='bottom', fontsize=8)

    ax.set_ylim(0, max(max(off_pct), max(on_pct)) * 1.2)

    for fmt in ['png', 'svg']:
        fig.savefig(OUTPUT / f'fig-codenames-clue-distribution.{fmt}', facecolor='white')
    plt.close(fig)
    print(f"  Figure 3 saved: {OUTPUT / 'fig-codenames-clue-distribution.png'}")


# ── Main ──────────────────────────────────────────────────

if __name__ == '__main__':
    print("Generating Paper #2 figures...\n")
    fig_trustgame_heatmap()
    fig_avalon_sabotage_timing()
    fig_codenames_clue_distribution()
    print(f"\nAll figures saved to: {OUTPUT}")
