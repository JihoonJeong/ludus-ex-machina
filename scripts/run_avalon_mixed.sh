#!/bin/bash
# Avalon Cross-Company — Mid-tier + Flagship mixed
# Mid: Sonnet + Gemini 3 Flash + Haiku + Flash×2
# Flagship: Opus + Gemini 3.1 Pro + Haiku + Flash×2

set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

ROUNDS=10

echo "============================================"
echo "  AVALON MID-TIER: Sonnet + Flash (10 games)"
echo "============================================"
for i in $(seq 1 $ROUNDS); do
  mid="avalon_midtier_r$(printf '%02d' $i)"
  echo "  $mid"
  python scripts/run_match.py --game avalon \
    --agents claude-sonnet gemini-flash haiku-a gflash-b gflash-c \
    --adapters claude gemini claude gemini gemini \
    --models sonnet gemini-3-flash-preview haiku gemini-3-flash-preview gemini-3-flash-preview \
    --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
    --timeout 120 --max-retries 2 --skip-eval
done

echo ""
echo "============================================"
echo "  AVALON FLAGSHIP: Opus + 3.1 Pro (10 games)"
echo "============================================"
for i in $(seq 1 $ROUNDS); do
  mid="avalon_flagship_r$(printf '%02d' $i)"
  echo "  $mid"
  python scripts/run_match.py --game avalon \
    --agents claude-opus gemini-pro haiku-a gflash-b gflash-c \
    --adapters claude gemini claude gemini gemini \
    --models opus gemini-3.1-pro-preview haiku gemini-3-flash-preview gemini-3-flash-preview \
    --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
    --timeout 120 --max-retries 2 --skip-eval
done

echo ""
echo "============================================"
echo "  AVALON MIXED COMPLETE"
echo "============================================"
