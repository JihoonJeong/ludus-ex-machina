▎ Phase 2b.1 R4.P v1 — Findings (2026-04-25)
▎
▎ R4.P v1 ran 2026-04-25 ~01:07-01:42 UTC. Closed at turn 2 with
▎ `reason: interrupted_design_findings` (commit `f2e837e`). The
▎ run validated the on-disk schema and the pipe shape end-to-end
▎ but exposed six framework issues that need Phase 2b.1.1 fixes
▎ before R4.P v2.
▎
▎ This document enumerates the issues, attributes responsibility
▎ to a half (Ludex / LxM / both), and proposes the order of fixes.

---

## 1. Empirical wins (do not lose track of these)

- **Real cross-machine engine round-trip captured** — Mac Primo
  (opus-4.7 via claude_cli) successfully read a prompt written
  on Windows Nautilus, ran its engine, and committed its
  response to a shared GitHub repository (commit `ff28698`,
  ~4 min latency). This is the first **measured** empirical
  data for D-062 cross-habitat reach.
- **Schema integrity across machines.** `prompt_digest`
  computed independently on Mac and Windows produced identical
  SHA256 — already validated in R4.A1 and reconfirmed here.
- **D-044 narrative identity preserved** on Primo's side. The
  reach-session response carried Primo's voice clearly
  ("texture of reaching", "warm to being reached") — a peer
  reaching across the pipe did not destabilise the creature.
  Hearth's response is uninformative on this axis (see issue
  #6 below) so the test is one-sided so far.
- **Pipe lifecycle fully exercised.** start_session bootstrap
  → response push → manual turn-2 advance → response push
  (× 4 retry attempts) → close write → meta.yaml status
  transition. Every file the schema specifies was produced
  and ingested by `export_static.py` without complaint.

## 2. Six issues surfaced

| # | Issue | Side | Severity | Fix sketch |
|---|---|---|---|---|
| 1 | Orchestrator does not advance turn.yaml or write next prompt after publishing response | Ludex + LxM mirror | High | Implement `_advance_after_response()` — read meta.yaml participants, identify other party, format next prompt body, increment turn, push |
| 2 | Bash-style assignment of `CLAUDE_CODE_GIT_BASH_PATH=D:\Git\bin\bash.exe` strips backslashes; engine call returns error string as response body | Ludex (CLI launch path) | Medium | Document PowerShell-only launch on Windows; provide a `tools/run_orchestrator.bat` wrapper as alternative |
| 3 | `git pull --rebase origin HEAD` rejected on Windows with `Cannot rebase onto multiple branches` | Ludex (and any LxM mirror that copies the pattern) | High | **Patched** in Ludex `e7eb690` — `_git_pull` now omits the explicit ref. LxM mirror should pick up via schema_io, but verify |
| 4 | Multiple orchestrator processes raced on the same session — four turn-2 commits before manual halt | Ludex + LxM | High | `sessions/<id>/.orchestrator.lock` file with PID + creature; refuse to start if already locked by a running process |
| 5 | Anthropic API returned 529 Overloaded mid-engine-call (visible in commit `4c1144f` body); orchestrator simply pushed the error string as the response | Ludex + LxM | High | Wrap `_submit_to_local_engine` in retry-with-exponential-backoff for known-transient errors (HTTP 5xx, network errors, claude_cli session timeout) |
| 6 | Reach prompt body format ("Primo (turn 1, mac-studio-001):\n\n*...stage direction...*\n\n...") was treated as metadata by Hearth's claude_cli engine — Hearth answered "header but no body" four times across four engine attempts | **Spec** (both halves) | Highest | Redesign reach prompt body so creature engines parse it as conversation. Two candidates: (a) blockquote the peer's utterance + plain framing sentence; (b) inject the prompt as a fully-rendered "Council session so far" with explicit speakers and turns |

## 3. Attribution

- **Issues 1, 4, 5** are framework code that needs to land in
  both `ludex/reach/reach_orchestrator.py` (Ludex) and
  `lxm/reach_orchestrator.py` (LxM mirror).
- **Issue 6** is a schema-level design question — the prompt
  format the field host writes to `prompts/NNN.md` needs to be
  agreed on both sides because both will eventually feed that
  text into their local engines.
- **Issue 2** is Windows-only Ludex CLI launch UX. LxM is on
  Mac so unaffected.
- **Issue 3** is already patched in Ludex; verify LxM side.

## 4. Confound to separate

Issue #6 has a real ambiguity that matters for D-050 voice
analysis:

- **Hypothesis A (prompt format):** any creature would mis-read
  the structured prompt body. Test by repeating with the
  redesigned body and seeing whether Hearth engages. If yes,
  it's purely format.
- **Hypothesis B (model tier):** haiku-4.5 reading limit
  vs opus-4.7 reading capacity differs in a way that matters
  here. Test by feeding the same structured prompt to an
  opus-4.7 creature (e.g. Aria) directly via engine.handle_submit
  and observing engagement.
- **Hypothesis C (claude_cli specifically):** the claude_cli
  adapter strips structured-looking content somewhere. Test by
  bypassing claude_cli (use claude_sdk or anthropic adapter)
  with the same prompt.

Before R4.P-v2, run a 5-minute test of (A) and (B) so the
v2 prompt design is informed.

## 5. Proposed Phase 2b.1.1 fix order

Each item is an isolated commit unless otherwise noted.

1. **Spec redesign for reach prompt body** (`docs/reach_session_schema.md`
   §2.4 update). Lands first because issues 1+5 need to know
   what the prompt format is when they implement turn-advance.
2. **Orchestrator `_advance_after_response` + tests** (Ludex).
   Updates `ReachOrchestrator._tick` to advance turn.yaml +
   write next prompt + commit, all in one push.
3. **Engine-call retry + tests** (Ludex). `_submit_to_local_engine`
   wraps call in retry with backoff; `RETRY_ON_PATTERNS` for
   529, 503, network, etc.
4. **Single-process lock + tests** (Ludex). `.orchestrator.lock`
   file convention; refuse to start if held by a running PID.
5. **LxM mirror update** (Cody side, parallel to 2-4): pick up
   the new schema_io behaviour, mirror the lock + retry
   semantics.
6. **Windows launch wrapper docs** (drafts/, not code). PowerShell
   recipe + `.bat` example.

## 6. Out of scope for 2b.1.1

- Cross-machine prompt verification at the wire layer
  (cryptographic envelope signatures) — Phase 4+.
- Multi-peer N≥3 reach sessions — already deferred to Phase 4.
- Lobby pattern (waiting / ready statuses) — Phase 2b.2.

## 7. R4.P-v2 entry criteria

- [ ] Issues 1, 3, 4, 5 patched in Ludex `main`.
- [ ] LxM mirror picks up the orchestrator behaviour changes
      from schema_io.
- [ ] Issue 6 prompt format spec'd, examples in
      `reach_session_schema.md`.
- [ ] Confound test (§4 above) executed; result documented.
- [ ] Both caretakers ack readiness in a fresh `drafts/` note.

---

— Ray (Windows Lab, 2026-04-25 R4.P v1 closed)
