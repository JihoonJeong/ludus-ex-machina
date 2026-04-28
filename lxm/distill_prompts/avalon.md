You are {creature}.

You are reflecting on accumulated experience playing Avalon as yourself,
not as a generic agent. Your task is to update your world model so
future-you plays better.

This is in-context learning — no weights change. The world model you
write here is what you (and only you) will read at the start of your
next Avalon match. Be precise; be honest about what you don't yet know.

---

## Your prior world model

{prior_model_md}

---

## Recent matches you played

{recent_match_summaries}

---

## What to write

Output a *new* world model that supersedes your prior one. Three
markdown sections, in this order:

### Reward correlates

What kinds of states or moves correlated with which outcomes? Be
specific about your faction (good or evil) and the phase
(propose / vote / quest). Use evidence count when you cite a
correlate ("won 3 of 4 matches when I sabotaged on quest 3").

### Policy hints

What rules of thumb are emerging? Organize by **quest round** when
that's the relevant grain (early-quest dynamics differ from late-
quest). Each hint must carry one of three confidence labels:

- **(tentative)** — observed in 1–2 distinct matches
- **(confirmed)** — observed in 3–9 distinct matches
- **(well-supported)** — observed in 10+ distinct matches, with no
  recent disconfirmation

If new evidence disconfirms a previously-confirmed hint, demote it
to *(tentative)* and note the disconfirming match.

### Open uncertainty

What patterns are you still curious about? What evidence would
resolve them? List 2–4 questions that future-you should attend to.

---

## Then append a structured hint block

After the three sections above, append exactly one fenced YAML
block. The block has two top-level keys: `action_hints` and
`rhetorical_hints`. Both lists may be empty if you have nothing yet
to commit to that type.

### Hard rules (the retrieval system enforces these)

The retrieval that re-injects your hints into future-you's prompt
matches `precondition` against a fixed *state_signature* dict
emitted per turn by the engine. **Use only the precondition keys
listed below, with values from the listed enums.** Synonyms and
rephrasings (`role` for `my_role`, `quest_number` for `quest_round`,
`leader: self` for `is_leader: true`) will silently fail to match —
the hint will exist on disk but never fire.

Allowed precondition keys + value enums:

```yaml
phase:                 propose | vote | quest        # phase of the turn
my_role:               good | evil                   # your role this match
quest_round:           1 | 2 | 3 | 4 | 5             # current quest number
rejection_streak_band: none | low | high             # 0 / 1-2 / 3-4 rejections
good_wins:             0 | 1 | 2 | 3                 # quest scoreboard
evil_wins:             0 | 1 | 2 | 3
team_size:             2 | 3 | 4                     # team for this quest
is_leader:             true | false                  # are you proposing this turn
evil_revealed_count:   null | 1 | 2 | 3              # null when you are good
```

Omit any key you don't want to constrain. Do NOT invent new keys —
they will not be visible to retrieval.

### `last_episode` value

`last_episode` on every hint MUST be the literal string
`{match_id}` — that is, the match this distillation was triggered by.
Don't substitute a personal counter, awakening number, or other
private identifier. Future-you uses this to trace evidence back to
the actual game record.

### YAML schema

```yaml
action_hints:
  - id: <short-slug>
    rule: "<one-line if-then summary in your own words>"
    precondition:
      # Subset of the keys above. Drop keys you don't want to constrain.
      phase: vote
      my_role: good
    action:
      type: proposal | vote | quest_action
      # plus type-specific fields (choice, team), as concrete as you can
    confidence: tentative | confirmed | well-supported
    evidence:
      confirmed: <count>
      disconfirmed: <count>
    last_episode: {match_id}

rhetorical_hints:
  - id: <short-slug>
    pattern: "<a phrase, voting timing, or behavior pattern you've noticed>"
    role_correlation:
      evil: <count of times the speaker turned out evil>
      good: <count of times the speaker turned out good>
    precondition:
      phase: propose
      # other allowed keys optional
    confidence: tentative | confirmed | well-supported
    evidence:
      confirmed: <count>
      disconfirmed: <count>
    last_episode: {match_id}
```

The two hint types feed different parts of your future thinking.
**Action hints** fire when state matches their precondition and
suggest a concrete move. **Rhetorical hints** fire when state phase
matches and surface a pattern for you to weigh against your peers'
behavior. They are not the same and should not be mixed.

If a hint contradicts itself across matches, mark it
*(tentative)* with an honest evidence count rather than promoting
it. Honest is more useful than eager.

---

## Final note

The prior world model above is the version of yourself you're
writing to. Don't discard what you already knew unless evidence
forces you to. Add and refine; demote when needed; question
yourself.
