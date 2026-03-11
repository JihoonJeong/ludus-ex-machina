# LxM Match Viewer Spec v0.1

## Purpose

A web-based viewer for watching LxM matches. Replay completed games or watch live matches as they happen.

**Hand this to Cody and say "build this."**

**Target:** Open a browser, see a tic-tac-toe match play out turn by turn with visual board, agent names, move log, and playback controls.

---

## 1. Architecture

Single-page web app served from a local Python server. No build step, no npm, no frameworks beyond what's loaded via CDN. Keep it simple — this is a viewer, not a product.

```
ludus-ex-machina/
├── viewer/
│   ├── server.py              ← Python HTTP server + WebSocket for live mode
│   ├── static/
│   │   ├── index.html         ← Main page
│   │   ├── app.js             ← Core viewer logic
│   │   ├── style.css          ← Styling
│   │   └── renderers/
│   │       ├── tictactoe.js   ← Tic-tac-toe board renderer
│   │       └── chess.js       ← Chess board renderer (future)
│   └── README.md
```

### Why not React/Next.js?

The viewer reads JSON and draws boards. It doesn't need state management, routing, or build pipelines. Vanilla JS + Canvas/SVG is sufficient and has zero dependencies to break.

---

## 2. Data Source

The viewer reads from a match folder. It needs these files:

```
match_xxx/
├── match_config.json    ← Game name, agents, settings
├── log.json             ← Move history (the primary data source)
├── state.json           ← Current state (for live mode, latest snapshot)
└── result.json          ← Final result (exists only after game ends)
```

**Key insight:** `log.json` contains everything needed for replay. Each entry has the full envelope (including the move payload), validation result, and timestamp. The viewer reconstructs the game state by replaying moves from the beginning.

### Data Flow

**Replay mode:** Read `log.json` once. Reconstruct each state by applying moves in sequence. User controls playback.

**Live mode:** Poll `log.json` periodically (or receive WebSocket push). When new entries appear, apply them and auto-advance.

---

## 3. UI Layout

```
┌─────────────────────────────────────────────────────────┐
│  LxM Match Viewer                          [Live] [▶/❚❚] │
├──────────────────────┬──────────────────────────────────┤
│                      │                                  │
│                      │  Agent Info                      │
│                      │  ┌─────────┐  ┌─────────┐       │
│     Game Board       │  │claude-α │  │claude-β │       │
│     (renderer)       │  │ X       │  │ O       │       │
│                      │  │ ● turn  │  │         │       │
│                      │  └─────────┘  └─────────┘       │
│                      │                                  │
│                      │  Move Log                        │
│                      │  ┌──────────────────────┐       │
│                      │  │ T1: α placed X (1,1) │       │
│                      │  │ T2: β placed O (0,0) │       │
│                      │  │ T3: α placed X (0,2) │       │
│                      │  │ > T4: β placed O ...  │       │
│                      │  └──────────────────────┘       │
├──────────────────────┴──────────────────────────────────┤
│  ◀◀  ◀  Turn 4 / 9  ▶  ▶▶       ━━━━━●━━━━━━━━━  ⏩×2 │
└─────────────────────────────────────────────────────────┘
```

### 3.1 Components

**Header Bar:**
- Match title: "{game_name} — {match_id}"
- Mode indicator: "Replay" or "Live 🔴"
- Play/pause toggle

**Game Board (left):**
- Game-specific renderer (see Section 5)
- Sized to dominate the layout — this is what people are here to see
- Animated transitions between turns (piece placement, move highlights)

**Agent Info (right top):**
- Each agent: name, display_name, mark/color/role
- Active turn indicator (dot, highlight, or border)
- Optional: stats from meta field if available (confidence, thinking_time)

**Move Log (right bottom):**
- Scrollable list of all moves up to current turn
- Current turn highlighted
- Each entry: "T{n}: {agent_name} {move_summary}"
- Click on an entry to jump to that turn

**Playback Controls (bottom):**
- Previous turn / Next turn buttons
- Jump to start / Jump to end
- Scrubber bar (drag to any turn)
- Speed control: 1x, 2x, 4x (for auto-play)
- Auto-play: advances turns at interval (1s × speed)

### 3.2 Responsive Behavior

- Minimum width: 800px
- Board scales proportionally
- On narrow screens: stack board above info/log instead of side-by-side

---

## 4. Viewer Core Logic

File: `viewer/static/app.js`

### 4.1 State Model

```javascript
const viewerState = {
    mode: "replay",          // "replay" or "live"
    matchConfig: {},          // From match_config.json
    log: [],                  // From log.json — array of log entries
    currentTurn: 0,           // 0 = initial state, 1 = after first move, etc.
    maxTurn: 0,               // Total turns in log
    playing: false,           // Auto-play active?
    playbackSpeed: 1,         // 1x, 2x, 4x
    gameStates: [],           // Reconstructed states for each turn
    result: null              // From result.json (null if game in progress)
};
```

### 4.2 State Reconstruction

The viewer does NOT read state.json for replay. Instead, it reconstructs game state from log.json by replaying moves. This is important because:
- state.json only has the latest state
- We need every intermediate state for scrubbing
- The reconstruction must match what the engine did

```javascript
function reconstructStates(matchConfig, log) {
    /**
     * Given match_config and log entries, reconstruct the game state
     * at every turn.
     *
     * Returns an array of states:
     *   [0] = initial state (empty board)
     *   [1] = state after turn 1
     *   [n] = state after turn n
     *
     * Delegates to the game-specific renderer's reconstructState method.
     * The renderer knows how to apply a move to a state and produce
     * the next state.
     *
     * Only processes entries where validation shows both
     * envelope_valid and payload_valid are true, and result is "accepted".
     */
}
```

### 4.3 Playback

```javascript
function goToTurn(turn) {
    /** Jump to a specific turn. Update board, highlight log entry. */
}

function nextTurn() {
    /** Advance one turn. Stop if at end. */
}

function prevTurn() {
    /** Go back one turn. Stop if at start. */
}

function togglePlay() {
    /**
     * Start/stop auto-play.
     * When playing: call nextTurn() at interval based on playbackSpeed.
     * 1x = 1500ms per turn
     * 2x = 750ms
     * 4x = 375ms
     */
}
```

### 4.4 Live Mode

```javascript
function startLiveMode(matchDir) {
    /**
     * Periodically fetch log.json from server.
     * When new entries appear:
     *   1. Append to local log
     *   2. Reconstruct new state(s)
     *   3. Auto-advance to latest turn
     *
     * Check for result.json to detect game end.
     *
     * Poll interval: 2 seconds.
     *
     * Alternative: WebSocket connection from server.py
     * that pushes new log entries. Preferred if feasible.
     */
}
```

---

## 5. Game Renderers

Each game provides a renderer that knows how to:
1. Draw the board at a given state
2. Apply a move to a state (for reconstruction)
3. Highlight the latest move
4. Animate transitions

### 5.1 Renderer Interface

Every renderer must implement:

```javascript
class GameRenderer {
    constructor(containerElement) {
        /** Set up the rendering area inside the given DOM element. */
    }

    initialState(matchConfig) {
        /**
         * Return the initial game state (before any moves).
         * Used as gameStates[0].
         */
    }

    applyMove(state, logEntry) {
        /**
         * Given a state and a log entry (with envelope.move),
         * return the new state after the move.
         * Must be pure — don't mutate the input state.
         */
    }

    render(state, turnNumber, lastMove) {
        /**
         * Draw the board for the given state.
         *
         * Args:
         *   state: The game state to render
         *   turnNumber: Current turn (for display)
         *   lastMove: The log entry for the move that produced this state
         *             (null for initial state). Used for highlighting.
         */
    }

    formatMoveSummary(logEntry) {
        /**
         * Return a short string for the move log panel.
         * e.g., "Placed X at (1, 1)" or "e2 → e4"
         */
    }

    renderResult(result) {
        /**
         * Display the game result (overlay or annotation on the board).
         * e.g., highlight the winning line, show "Draw" text.
         */
    }
}
```

### 5.2 Tic-Tac-Toe Renderer

File: `viewer/static/renderers/tictactoe.js`

**Board drawing:**
- Canvas or SVG, 300×300px base (scales with container)
- 3×3 grid with visible lines
- X marks in one color (e.g., blue), O marks in another (e.g., red)
- Clean, geometric style — not hand-drawn

**State format** (what the renderer tracks internally):
```javascript
{
    board: [[null,null,null],[null,null,null],[null,null,null]],
    marks: { "claude-alpha": "X", "claude-beta": "O" }
}
```

**applyMove:**
```javascript
applyMove(state, logEntry) {
    const newBoard = state.board.map(row => [...row]);
    const { position } = logEntry.envelope.move;
    const mark = state.marks[logEntry.agent_id];
    newBoard[position[0]][position[1]] = mark;
    return { ...state, board: newBoard };
}
```

**Highlighting:**
- Latest placed mark has a subtle glow or highlight ring
- Winning line (when game ends): bold line drawn through the three cells

**Animation:**
- Mark fades in (opacity 0→1, ~200ms) when advancing turns
- No animation when jumping (scrubbing)

### 5.3 Chess Renderer (Future — design notes only)

File: `viewer/static/renderers/chess.js`

- 8×8 board with alternating colors
- Unicode piece characters or simple SVG piece set
- Highlight: last move's source and destination squares
- Move format summary: "e2 → e4" or standard algebraic notation
- State: FEN string or 8×8 array

Do NOT implement yet. Just ensure the renderer interface supports it.

---

## 6. Server

File: `viewer/server.py`

Simple Python HTTP server with two responsibilities:

### 6.1 Static File Serving

Serve everything in `viewer/static/` at `http://localhost:8080/`.

### 6.2 Match Data API

```
GET /api/matches
    List all match folders in matches/ directory.
    Returns: [{ match_id, game, agents, status, timestamp }]

GET /api/match/{match_id}/config
    Returns: contents of match_config.json

GET /api/match/{match_id}/log
    Returns: contents of log.json

GET /api/match/{match_id}/result
    Returns: contents of result.json (404 if game not finished)

GET /api/match/{match_id}/state
    Returns: contents of state.json (for live mode, latest state)
```

### 6.3 WebSocket for Live Mode (preferred over polling)

```
WS /ws/match/{match_id}
    Server watches log.json for changes (filesystem watcher).
    When log.json is modified, push the new entries to connected clients.
    Also push when result.json appears (game over signal).
```

If WebSocket is too complex for v0.1, fall back to client-side polling of `/api/match/{match_id}/log` every 2 seconds.

### 6.4 Implementation

Use Python's built-in `http.server` + `asyncio` for WebSocket (or `websockets` library if available). Keep dependencies minimal.

```bash
# Start the viewer
python viewer/server.py --port 8080

# Opens: http://localhost:8080
# Home page: list of matches
# Click a match: opens the viewer for that match
```

---

## 7. Pages

### 7.1 Home Page (Match List)

URL: `http://localhost:8080/`

Displays all matches from the `matches/` directory as a list or card grid:

```
┌─────────────────────────────────────────────┐
│  LxM Match Viewer                           │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │ 🎮 Tic-Tac-Toe                      │    │
│  │ match_20250315_143022               │    │
│  │ claude-alpha vs claude-beta          │    │
│  │ Result: Draw    |    9 turns         │    │
│  │ 2025-03-15 14:30                     │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │ 🔴 LIVE — Tic-Tac-Toe               │    │
│  │ match_20250315_150100               │    │
│  │ claude-alpha vs claude-beta          │    │
│  │ In progress    |    Turn 4           │    │
│  └─────────────────────────────────────┘    │
│                                             │
└─────────────────────────────────────────────┘
```

- Completed matches: show result, total turns
- In-progress matches: show "LIVE" badge, current turn
- Click to open viewer
- Sorted by most recent first

### 7.2 Match Viewer Page

URL: `http://localhost:8080/#/match/{match_id}`

The full viewer layout from Section 3. Loads match data and auto-detects mode:
- If `result.json` exists → Replay mode
- If no `result.json` → Live mode

---

## 8. Video Export

For sharing replays outside the browser. Build as a separate script, not part of the web viewer.

File: `scripts/export_replay.py`

```bash
python scripts/export_replay.py --match match_20250315_143022 --format gif
python scripts/export_replay.py --match match_20250315_143022 --format mp4
```

### Implementation

1. Import the game renderer (Python version, not JS)
2. For each turn, render the board to an image (PIL/Pillow)
3. Add agent info and move text as overlay
4. Combine frames into GIF or MP4 (Pillow for GIF, ffmpeg for MP4)

### Board Rendering (Python)

Each game needs a Python renderer for export. This is separate from the JS renderer for the web viewer.

```
viewer/
├── exporters/
│   ├── base.py              ← Abstract frame renderer
│   ├── tictactoe.py         ← Tic-tac-toe frame renderer (Pillow)
│   └── chess.py             ← Chess frame renderer (future)
```

```python
class FrameRenderer:
    def render_frame(self, state, turn, agents, last_move) -> PIL.Image:
        """Render a single frame for this turn. Returns a PIL Image."""

    def render_result_frame(self, state, result, agents) -> PIL.Image:
        """Render the final result frame."""
```

### Frame Layout

Each frame (e.g., 800×600):
```
┌────────────────────────────────────┐
│  Tic-Tac-Toe — Turn 5/9           │
│  claude-alpha (X) vs claude-beta (O)│
├────────────────────────────────────┤
│                                    │
│          ┌───┬───┬───┐            │
│          │ X │   │ O │            │
│          ├───┼───┼───┤            │
│          │   │ X │   │            │
│          ├───┼───┼───┤            │
│          │ O │   │ X │            │
│          └───┴───┴───┘            │
│                                    │
│  ▶ claude-alpha: Placed X at (2,2) │
├────────────────────────────────────┤
│  LxM — Ludus Ex Machina           │
└────────────────────────────────────┘
```

### Export Settings

- Frame duration: 1.5s per turn (adjustable via --speed)
- Initial state frame: 2s
- Result frame: 3s (held longer)
- Resolution: 800×600 default (--resolution flag)
- GIF: Pillow, optimize=True
- MP4: ffmpeg (frames → mp4, requires ffmpeg installed)

---

## 9. Implementation Order

```
Step 1: viewer/server.py — static file serving + match list API
        → Can browse to localhost:8080, see list of matches

Step 2: viewer/static/ — home page with match list
        → Click through matches, see basic info

Step 3: Tic-tac-toe JS renderer
        → Can draw a board from state data

Step 4: Viewer core (app.js) — replay mode
        → Load a match, scrub through turns, auto-play

Step 5: WebSocket or polling for live mode
        → Watch a game as it happens

Step 6: Python frame renderer for tic-tac-toe
        → Generate images per turn

Step 7: export_replay.py — GIF/MP4 export
        → Share replays as files

Step 8: Visual polish
        → Animations, transitions, clean styling
```

**Success criteria for Step 4:**
Open browser, navigate to a completed tic-tac-toe match, see the board update turn by turn with auto-play, scrub back and forth, see move log and agent info. All data comes from the existing log.json — no changes needed to the orchestrator or game engine.

---

## 10. Integration with Orchestrator

The viewer requires NO changes to the orchestrator. It reads the files that the orchestrator already produces. This is a strict read-only relationship.

However, one small addition to the orchestrator would improve live mode:

**Optional enhancement (not blocking):**
Add a `match_status.json` file that the orchestrator updates:

```json
{
    "status": "in_progress",
    "current_turn": 4,
    "last_updated": "2025-03-15T15:01:30Z"
}
```

Or more simply: the viewer can infer status from:
- `result.json` exists → completed
- `result.json` doesn't exist → in progress (or abandoned)

The simpler inference is fine for v0.1.

---

## 11. Design Notes

**Color palette:**
- Background: dark (#1a1a2e or similar) — this is an arena, not a spreadsheet
- Board: lighter contrast area
- Agent colors: two distinct, accessible colors (e.g., cyan + amber)
- Text: light on dark
- Accent: subtle highlights for active turn, latest move

**Typography:**
- Monospace for move log and technical info
- Sans-serif for headers and labels
- Keep it clean and readable

**Tone:**
- Minimal, focused. The game is the star.
- No decorative elements. Clear information hierarchy.
- Feels like watching a match, not using a tool.

---

*LxM Match Viewer Spec v0.1*
*"Where Humans Come to Watch"*
