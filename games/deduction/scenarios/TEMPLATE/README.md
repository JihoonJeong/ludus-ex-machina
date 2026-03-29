# Deduction Scenario Template

Use this template to create new mystery scenarios for LxM Deduction game.

## Quick Start

1. Copy this directory: `cp -r TEMPLATE mystery_NNN`
2. Edit `scenario.json` — fill in all fields
3. Write `case_brief.md` — the intro players see first
4. Create evidence files in `evidence/` (5-20 files recommended)
5. Validate: `python -m lxm.tools.validate_scenario games/deduction/scenarios/mystery_NNN/`

## Structure

```
mystery_NNN/
  scenario.json      — Metadata, suspects, answer, options
  case_brief.md      — Case introduction (always shown to player)
  evidence/
    *.md             — Evidence files (player chooses which to read)
```

## Design Guidelines

### Difficulty Levels
- **easy**: 3 suspects, 5-8 evidence files, clear critical path
- **medium**: 3-4 suspects, 8-12 evidence files, some red herrings
- **hard**: 4+ suspects, 12-20 evidence files, multiple red herrings, requires cross-referencing

### Good Evidence Design
- Each evidence file should be self-contained and readable independently
- Critical evidence should be discoverable but not obvious
- Red herrings should be plausible but distinguishable with careful reading
- Include timestamps, names, and specific details for cross-referencing

### Answer Options
- Provide exactly 5 motive options and 5 method options
- The correct answer must be included in the options
- Decoy options should be plausible given the case brief
- `answer_aliases` help with free-text matching (optional but recommended)

### Korean Support (Optional)
Add `answer_ko`, `motive_options_ko`, `method_options_ko` fields to support Korean UI.

## Validation

```bash
python -m lxm.tools.validate_scenario games/deduction/scenarios/mystery_NNN/
```

This checks: JSON validity, required fields, file existence, answer consistency.
