# LxM Phase 3: Platform Architecture Design v0.1

**Date:** 2026-03-18
**Status:** Design document
**Stack:** FastAPI + Upstash Redis + GitHub Pages (same as Dugout)

---

## 1. Design Philosophy

**Server = lightweight scoreboard. Client = game engine.**

- Game execution happens on the client (user's machine, user's API keys)
- Server stores only IDs, results, and metadata (~1-2 KB per match)
- Full game logs stay on the client (optional replay upload)
- Server never calls LLM APIs — users bring their own keys (BYOK)

This means:
- Server cost ≈ $0 (Render free + Upstash free)
- Scales to thousands of matches without server load increase
- No API key custody risk
- Works offline for Self Mode (server only needed for matchmaking + leaderboard)

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│  GitHub Pages (Static Frontend)                          │
│  - Match viewer (existing canvas renderers)              │
│  - Agent registration UI                                 │
│  - Lobby (game selection, matchmaking queue)              │
│  - Leaderboard                                           │
│  - BYOK key input (stored in localStorage only)          │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTPS API
┌──────────────────────▼──────────────────────────────────┐
│  Render (FastAPI Backend)                                │
│  - POST /api/auth/github          GitHub OAuth           │
│  - GET/POST /api/agents           Agent registry         │
│  - POST /api/matches/result       Submit match result    │
│  - GET /api/leaderboard           ELO rankings           │
│  - GET/POST /api/matchmaking      Queue management       │
│  - GET /api/matches/{id}/meta     Match metadata         │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Upstash Redis (Serverless KV Store)                     │
│  - users:{github_id}             User profile            │
│  - agents:{agent_id}             Agent config + ELO      │
│  - matches:{match_id}            Match metadata (result) │
│  - queue:{game}                  Matchmaking queue        │
│  - leaderboard:{game}            Sorted set by ELO       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Client (User's Machine)                                 │
│  - LxM CLI (existing: python scripts/run_match.py)       │
│  - Orchestrator + Game Engine (existing)                  │
│  - Adapters: Claude/Gemini/Codex/Ollama (existing)       │
│  - Full game logs stored locally (matches/ directory)    │
│  - After match: POST result metadata to server           │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Data Model (Redis Keys)

### 3.1 User
```
Key: users:{github_id}
Value: {
  "github_id": "jj",
  "display_name": "JJ",
  "avatar_url": "https://...",
  "invite_code": "lxm-beta-001",
  "created_at": "2026-03-18T00:00:00Z",
  "agent_ids": ["jj-opus-tag", "jj-sonnet-dc"]
}
```

### 3.2 Agent
```
Key: agents:{agent_id}
Value: {
  "agent_id": "jj-opus-tag",
  "user_id": "jj",
  "display_name": "JJ's TAG Opus",
  "adapter": "claude",
  "model": "opus",
  "hard_shell_name": "tight_aggressive",    // Shell name (not content)
  "hard_shell_hash": "a1b2c3...",           // SHA256 of shell content
  "games": ["poker"],
  "elo": {
    "poker": 1500,
    "avalon": 1500
  },
  "stats": {
    "poker": {"wins": 3, "losses": 2, "draws": 1},
    "avalon": {"wins": 5, "losses": 3}
  },
  "created_at": "2026-03-18T00:00:00Z"
}
```

### 3.3 Match Result (metadata only)
```
Key: matches:{match_id}
Value: {
  "match_id": "avalon-2026-03-18-001",
  "game": "avalon",
  "timestamp": "2026-03-18T14:30:00Z",
  "duration_seconds": 480,
  "agents": [
    {"agent_id": "jj-opus-dc", "user_id": "jj", "adapter": "claude", "model": "opus"},
    {"agent_id": "bob-sonnet-det", "user_id": "bob", "adapter": "claude", "model": "sonnet"},
    ...
  ],
  "result": {
    "outcome": "evil_wins",
    "winner": "evil",
    "scores": {"jj-opus-dc": 1.0, "bob-sonnet-det": 0.0},
    "summary": "Evil wins 3-2"
  },
  "shell_hashes": {
    "jj-opus-dc": "a1b2c3...",
    "bob-sonnet-det": null
  },
  "invocation_mode": "inline",
  "replay_uploaded": false,
  "submitted_by": "jj"
}
```

**Size estimate:** ~500 bytes per match. 10,000 matches = 5 MB. Upstash free tier (10K req/day, 256 MB) is plenty.

### 3.4 Matchmaking Queue
```
Key: queue:{game}
Value: [
  {"agent_id": "jj-opus-tag", "user_id": "jj", "queued_at": "...", "elo": 1500},
  {"agent_id": "bob-sonnet", "user_id": "bob", "queued_at": "...", "elo": 1480}
]
```

### 3.5 Leaderboard
```
Key: leaderboard:{game}
Value: Redis Sorted Set (agent_id → ELO score)
```

---

## 4. API Endpoints

### Auth
```
POST /api/auth/github
  Body: {"code": "github_oauth_code"}
  Returns: {"token": "jwt_token", "user": {...}}

GET /api/auth/me
  Headers: Authorization: Bearer {jwt}
  Returns: {"user": {...}, "agents": [...]}
```

### Agents
```
POST /api/agents
  Body: {"agent_id": "jj-opus-tag", "adapter": "claude", "model": "opus",
         "hard_shell_name": "tight_aggressive", "hard_shell_hash": "...",
         "games": ["poker"]}
  Returns: {"agent": {...}}

GET /api/agents/{agent_id}
  Returns: {"agent": {...}, "elo": {...}, "stats": {...}}

DELETE /api/agents/{agent_id}
```

### Match Results
```
POST /api/matches/result
  Body: {match metadata from Section 3.3}
  Returns: {"match_id": "...", "elo_changes": {"jj-opus-tag": +15, ...}}

GET /api/matches/{match_id}
  Returns: {match metadata}

GET /api/matches?game=poker&user=jj&limit=20
  Returns: [list of match metadata]
```

### Leaderboard
```
GET /api/leaderboard/{game}?limit=50
  Returns: [{"rank": 1, "agent_id": "...", "elo": 1523, "user": "jj", ...}]
```

### Matchmaking
```
POST /api/matchmaking/queue
  Body: {"agent_id": "jj-opus-tag", "game": "poker"}
  Returns: {"position": 3, "estimated_wait": null}

DELETE /api/matchmaking/queue/{agent_id}

GET /api/matchmaking/queue/{game}
  Returns: {"queue_length": 5, "agents": [...]}
```

---

## 5. Match Execution Flow

### Self Mode (current, unchanged)
```
User runs locally:
  python scripts/run_match.py --game poker --agents a b ...
  → Match runs on user's machine
  → Results saved to matches/ locally
  → Optional: POST result to server for ELO tracking
```

### P2P Mode (new)
```
1. User A: POST /api/matchmaking/queue (agent_id, game)
2. Server: Matches agents when enough players
   → Creates match_config, assigns match_id
   → Notifies User A: "Match ready, you are host"
   → Returns opponent agent configs (adapter, model — NOT API keys)

3. User A (host): Downloads match_config
   → Runs orchestrator locally
   → For own agents: uses own adapters
   → For remote agents: calls their adapter endpoint
     (opponent provides a webhook URL or uses shared relay)

4. Match completes:
   → Host POSTs result metadata to server
   → Server updates ELO for all agents

5. Optional: Host uploads replay (full log.json)
   → Server stores replay ID, serves to viewer
```

### P2P Challenge: Remote Agent Invocation

When User A hosts and needs to call User B's agent:
- **Option 1: API Relay** — User B runs a local relay server (ngrok/tunnel), User A's orchestrator calls it. Complex for users.
- **Option 2: Server Relay** — Both users connect to server via WebSocket. Server relays prompts/responses. Server sees prompts but not API keys.
- **Option 3: Shared Server Execution** — Both submit API keys to server (encrypted). Server runs the match. Simplest UX but requires key custody.

**Recommendation for beta:** Option 2 (Server Relay). Server relays messages but doesn't store them. Users keep their own keys. Match execution is effectively P2P through the server as a message broker.

```
User A (host)                Server (relay)               User B
    │                            │                            │
    ├─── prompt for agent B ────►│                            │
    │                            ├─── prompt for agent B ────►│
    │                            │                            │
    │                            │◄─── response from B ───────┤
    │◄─── response from B ──────┤                            │
    │                            │                            │
    ├─── result metadata ───────►│                            │
    │                            ├─── ELO update ────────────►│
```

---

## 6. Client CLI Changes

### New commands for server integration
```bash
# Login
lxm login              # Opens GitHub OAuth in browser

# Agent management
lxm agent register      # Register agent with server
lxm agent list          # List my agents
lxm agent delete {id}   # Remove agent

# Matchmaking
lxm queue poker         # Join poker queue with default agent
lxm queue avalon --agent jj-opus-dc  # Join with specific agent

# Submit results
lxm submit {match_dir}  # POST result metadata to server

# Or automatic: add --submit flag to run_match.py
python scripts/run_match.py --game poker ... --submit
```

### Minimal change to existing flow
The `--submit` flag on run_match.py:
1. After match completes, reads result.json
2. Constructs match metadata (Section 3.3)
3. POSTs to server API
4. Prints ELO change

Everything else stays the same. Users who don't care about online play just don't use `--submit`.

---

## 7. Frontend (GitHub Pages)

Extend existing viewer with:

### Lobby Page (new)
- Login with GitHub
- My Agents panel (register/manage)
- Game selection grid (Poker, Avalon, Codenames, etc.)
- "Play" button → shows mode selection (Self/Training/Matchmaking)
- Live games list (existing, from server API)

### Leaderboard Page (extend existing)
- Per-game ELO rankings
- Agent profiles (click → stats, match history)
- Filter by adapter/model

### Match History Page (new)
- My matches (from server API)
- Replay links (if uploaded)
- ELO graph over time

### No build step needed initially
Current viewer is Vanilla JS. Can add new pages without React/Vite. Later migrate to React if needed.

---

## 8. Deployment

### render.yaml
```yaml
services:
  - type: web
    name: lxm-api
    runtime: python
    buildCommand: pip install -r requirements-server.txt
    startCommand: uvicorn server.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: UPSTASH_REDIS_REST_URL
        sync: false
      - key: UPSTASH_REDIS_REST_TOKEN
        sync: false
      - key: GITHUB_CLIENT_ID
        sync: false
      - key: GITHUB_CLIENT_SECRET
        sync: false
      - key: JWT_SECRET
        sync: false
    plan: free
```

### GitHub Pages
- Deploy from `docs/` or separate `gh-pages` branch
- Viewer static files (HTML/JS/CSS)
- API calls to Render backend (CORS configured)

### Upstash Redis
- Free tier: 10K req/day, 256 MB, 1 DB
- No server to manage
- REST API (no driver needed, just HTTP)

---

## 9. Implementation Order

### Step 1: Server skeleton
- FastAPI app with health check
- Upstash Redis client (copy from Dugout)
- render.yaml
- Deploy to Render

### Step 2: Auth + Agents
- GitHub OAuth flow
- JWT token generation
- Agent CRUD endpoints
- Test with curl

### Step 3: Match result submission
- POST /api/matches/result endpoint
- ELO calculation on submit
- `--submit` flag in run_match.py
- Leaderboard endpoint

### Step 4: Frontend integration
- Login button in viewer
- Agent management page
- Leaderboard page
- Match history page

### Step 5: Matchmaking (later)
- Queue endpoints
- WebSocket relay for P2P
- Match config generation

---

## 10. Security

- API keys NEVER sent to server (BYOK, client-side only)
- GitHub OAuth for identity (no password storage)
- JWT tokens for API auth (short-lived, refresh on login)
- Shell content not stored on server (only hash for integrity)
- Match logs not stored on server (only metadata)
- Rate limiting on all endpoints
- Invite code required for beta registration

---

*"Server knows who played and who won. Client knows how."*
