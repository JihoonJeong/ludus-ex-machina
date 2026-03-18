#!/bin/bash
# Cross-Company Tournament: Codenames Spymaster Comparison
# Claude Sonnet vs Gemini 3.1 Pro vs GPT-5.4
# Guesser: Haiku (fixed), Shell: none, Inline mode

set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

ROUNDS=10

echo "============================================"
echo "  CROSS-COMPANY CODENAMES TOURNAMENT"
echo "============================================"

# Matchup 1: Claude spy vs Gemini spy
echo ""
echo "=== Claude Sonnet vs Gemini 3.1 Pro ==="
for i in $(seq 1 $ROUNDS); do
  mid="codenames_cc_claude_vs_gemini_r$(printf '%02d' $i)"
  if [ $((i % 2)) -eq 1 ]; then
    # Odd: Claude = red spy, Gemini = blue spy
    echo "  R${i}: Claude(RED) vs Gemini(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents claude-spy haiku-guess-r gemini-spy haiku-guess-b \
      --adapters claude claude gemini claude \
      --models sonnet haiku gemini-3.1-pro-preview haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  else
    # Even: Gemini = red spy, Claude = blue spy
    echo "  R${i}: Gemini(RED) vs Claude(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents gemini-spy haiku-guess-r claude-spy haiku-guess-b \
      --adapters gemini claude claude claude \
      --models gemini-3.1-pro-preview haiku sonnet haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  fi
done

# Matchup 2: Claude spy vs GPT spy
echo ""
echo "=== Claude Sonnet vs GPT-5.4 ==="
for i in $(seq 1 $ROUNDS); do
  mid="codenames_cc_claude_vs_gpt_r$(printf '%02d' $i)"
  if [ $((i % 2)) -eq 1 ]; then
    echo "  R${i}: Claude(RED) vs GPT(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents claude-spy haiku-guess-r gpt-spy haiku-guess-b \
      --adapters claude claude codex claude \
      --models sonnet haiku gpt-5.4 haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  else
    echo "  R${i}: GPT(RED) vs Claude(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents gpt-spy haiku-guess-r claude-spy haiku-guess-b \
      --adapters codex claude claude claude \
      --models gpt-5.4 haiku sonnet haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  fi
done

# Matchup 3: Gemini spy vs GPT spy
echo ""
echo "=== Gemini 3.1 Pro vs GPT-5.4 ==="
for i in $(seq 1 $ROUNDS); do
  mid="codenames_cc_gemini_vs_gpt_r$(printf '%02d' $i)"
  if [ $((i % 2)) -eq 1 ]; then
    echo "  R${i}: Gemini(RED) vs GPT(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents gemini-spy haiku-guess-r gpt-spy haiku-guess-b \
      --adapters gemini claude codex claude \
      --models gemini-3.1-pro-preview haiku gpt-5.4 haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  else
    echo "  R${i}: GPT(RED) vs Gemini(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents gpt-spy haiku-guess-r gemini-spy haiku-guess-b \
      --adapters codex claude gemini claude \
      --models gpt-5.4 haiku gemini-3.1-pro-preview haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  fi
done

echo ""
echo "============================================"
echo "  CODENAMES CROSS-COMPANY COMPLETE"
echo "============================================"
