#!/bin/bash
# Cross-Company Low-tier: Haiku vs Gemini 3 Flash — Chess (6 games)

set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

echo "=== LOW-TIER: Chess — Haiku vs Gemini 3 Flash (6 games) ==="
for i in $(seq 1 6); do
  mid="chess_lowtier_haiku_vs_flash_r$(printf '%02d' $i)"
  if [ $((i % 2)) -eq 1 ]; then
    echo "  R${i}: Haiku(W) vs Flash(B)"
    python scripts/run_match.py --game chess \
      --agents haiku-s flash-s \
      --adapters claude gemini \
      --models haiku gemini-3-flash-preview \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 180 --max-retries 2 --skip-eval
  else
    echo "  R${i}: Flash(W) vs Haiku(B)"
    python scripts/run_match.py --game chess \
      --agents flash-s haiku-s \
      --adapters gemini claude \
      --models gemini-3-flash-preview haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 180 --max-retries 2 --skip-eval
  fi
done

echo ""
echo "=== LOW-TIER CHESS COMPLETE ==="
