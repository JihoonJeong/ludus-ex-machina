#!/bin/bash
# Cross-Company Flagship: Opus vs Gemini 3.1 Pro
# Chess (6 games) + Poker HU (6 games)

set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

echo "=== FLAGSHIP: Chess — Opus vs Gemini 3.1 Pro (6 games) ==="
for i in $(seq 1 6); do
  mid="chess_flagship_opus_vs_gemini_r$(printf '%02d' $i)"
  if [ $((i % 2)) -eq 1 ]; then
    echo "  R${i}: Opus(W) vs Gemini(B)"
    python scripts/run_match.py --game chess \
      --agents opus-s gemini-s \
      --adapters claude gemini \
      --models opus gemini-3.1-pro-preview \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 180 --max-retries 2 --skip-eval
  else
    echo "  R${i}: Gemini(W) vs Opus(B)"
    python scripts/run_match.py --game chess \
      --agents gemini-s opus-s \
      --adapters gemini claude \
      --models gemini-3.1-pro-preview opus \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 180 --max-retries 2 --skip-eval
  fi
done

echo ""
echo "=== FLAGSHIP: Poker HU — Opus vs Gemini 3.1 Pro (6 games) ==="
for i in $(seq 1 6); do
  mid="poker_flagship_opus_vs_gemini_r$(printf '%02d' $i)"
  if [ $((i % 2)) -eq 1 ]; then
    echo "  R${i}: Opus first"
    python scripts/run_match.py --game poker \
      --agents opus-s gemini-s \
      --adapters claude gemini \
      --models opus gemini-3.1-pro-preview \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 180 --max-retries 2 --skip-eval
  else
    echo "  R${i}: Gemini first"
    python scripts/run_match.py --game poker \
      --agents gemini-s opus-s \
      --adapters gemini claude \
      --models gemini-3.1-pro-preview opus \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 180 --max-retries 2 --skip-eval
  fi
done

echo ""
echo "=== FLAGSHIP CHESS + POKER COMPLETE ==="
