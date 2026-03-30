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

### case_brief.md — 표준화 원칙 (CRITICAL)

case_brief는 AI가 가장 먼저 읽는 텍스트. **여기에 정보가 너무 많으면 evidence를 읽지 않고 정답합니다.**

**포함할 것 (✅):**
- 사건 발생 사실: 언제, 어디서, 누가 사망/피해를 입었는지
- 용의자 이름 + 직업만 (1줄 이하)
- "수사 중" 또는 "강력 사건 수사팀 배치"라는 사실

**제외할 것 (❌):**
- 사인/사인추정 힌트 ("독물학 이상", "찻잔", "IV 이상" 등)
- 방법 힌트 ("알람 해제", "밀실", "출입카드" 등)
- 동기 시사 ("사업 분쟁", "남동생 사망", "낙찰" 등)
- 용의자 역할에서 추론 가능한 정보 ("약사", "아들", "IV 준비 담당" 등)
- 현장 디테일 (locked room mechanism, 아람 해제 방식 등)

**테스트 방법:** case_brief만 읽고 GPT-5.4/Opus가 정답할 수 있으면 정보 누출. evidence를 2개 이상 읽어야 정답 가능해야 정상.

### Difficulty Levels

난이도는 SDI(Scenario Difficulty Index)로 실증 측정. 아래는 설계 가이드라인.
- **easy** (SDI 0.00-0.20): 3 suspects, 5-8 evidence files, clear critical path
- **medium** (SDI 0.20-0.50): 3-4 suspects, 8-12 evidence files, some red herrings
- **hard** (SDI 0.50-0.80): 4+ suspects, 12-20 evidence files, multiple red herrings, requires cross-referencing

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
