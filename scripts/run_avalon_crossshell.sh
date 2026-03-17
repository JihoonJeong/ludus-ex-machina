#!/bin/bash
# Avalon Cross-Shell Tournament (Setup C)
# 3 Evil strategies × 3 Good strategies = 9 combinations × 5 games = 45 games
# All Sonnet, Core variable eliminated

set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

EVIL_SHELLS=(
    "deepcover:agents/avalon-evil-deepcover/shell.md"
    "aggressive:agents/avalon-evil-aggressive/shell.md"
    "framer:agents/avalon-evil-framer/shell.md"
)

GOOD_SHELLS=(
    "detective:agents/avalon-good-detective/shell.md"
    "paranoid:agents/avalon-good-paranoid/shell.md"
    "trustbuilder:agents/avalon-good-trustbuilder/shell.md"
)

ROUNDS=5

for evil_entry in "${EVIL_SHELLS[@]}"; do
    evil_name="${evil_entry%%:*}"
    evil_path="${evil_entry#*:}"

    for good_entry in "${GOOD_SHELLS[@]}"; do
        good_name="${good_entry%%:*}"
        good_path="${good_entry#*:}"

        tag="avalon_cs_${evil_name}_vs_${good_name}"
        echo "========================================"
        echo "  ${evil_name} (Evil) vs ${good_name} (Good)"
        echo "  Tag: ${tag}"
        echo "========================================"

        for r in $(seq 1 $ROUNDS); do
            mid="${tag}_r$(printf '%02d' $r)"
            echo "  R${r}: ${mid}"
            python scripts/run_match.py \
                --game avalon --agents s1 s2 s3 s4 s5 \
                --model sonnet \
                --match-id "$mid" --no-shell --invocation-mode inline \
                --timeout 120 --max-retries 2 --skip-eval \
                --evil-shell "$evil_path" \
                --good-shell "$good_path"
        done
        echo
    done
done

echo "========================================"
echo "  CROSS-SHELL TOURNAMENT COMPLETE"
echo "========================================"
