/**
 * LxM Match Viewer — Core application logic.
 */

const viewer = {
    mode: 'replay',
    matchConfig: null,
    log: [],
    currentTurn: 0,
    maxTurn: 0,
    playing: false,
    playbackSpeed: 1,
    gameStates: [],
    result: null,
    renderer: null,
    playInterval: null,
    acceptedLog: [],   // Only accepted moves
    liveSource: null,  // SSE EventSource for live mode
    lobbyRefresh: null, // Auto-refresh interval for lobby
    handBoundaries: [], // [{hand: N, turnIndex: T}] for poker hand-jump
};

// ─── API ───

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json();
}

// ─── Home Page ───

// Lobby state
const lobby = {
    allMatches: [],
    gameFilter: 'all',
};

async function loadMatchList() {
    const matches = await fetchJSON('/api/matches');
    const liveSection = document.getElementById('live-section');
    const recentSection = document.getElementById('recent-section');
    const liveList = document.getElementById('live-list');
    const empty = document.getElementById('no-matches');

    if (!matches || matches.length === 0) {
        empty.style.display = '';
        liveSection.style.display = 'none';
        recentSection.style.display = 'none';
        return;
    }
    empty.style.display = 'none';

    const live = matches.filter(m => m.status !== 'completed');
    const recent = matches.filter(m => m.status === 'completed');
    lobby.allMatches = recent;

    // Live matches (selectable for multi-view)
    if (live.length > 0) {
        liveSection.style.display = '';
        document.getElementById('live-count').textContent = live.length;
        liveList.innerHTML = live.map(m => `
            <div class="match-card live-card" data-match-id="${m.match_id}">
                <label class="select-check" onclick="event.stopPropagation()">
                    <input type="checkbox" class="live-select" value="${m.match_id}" onchange="updateWatchButton()">
                </label>
                <div class="live-card-body" onclick="navigateTo('${m.match_id}')">
                    <div class="live-indicator"><span class="live-dot"></span> LIVE</div>
                    <div class="game-name">${m.game}</div>
                    <div class="agents-names">${m.agents.join(' vs ')}</div>
                    <div class="match-meta">
                        <span>Turn ${m.turn_count}</span>
                    </div>
                </div>
            </div>
        `).join('');
        document.getElementById('btn-watch-selected').style.display = 'none';
    } else {
        liveSection.style.display = 'none';
    }

    // Build game tabs
    buildGameTabs(recent);

    // Render filtered list
    applyFilters();

    // Leaderboard
    loadLeaderboard();

    // Auto-refresh lobby every 10s if there are live games
    if (live.length > 0 && !viewer.lobbyRefresh) {
        viewer.lobbyRefresh = setInterval(() => {
            const homePage = document.getElementById('home-page');
            if (homePage.style.display !== 'none') loadMatchList();
        }, 10000);
    } else if (live.length === 0 && viewer.lobbyRefresh) {
        clearInterval(viewer.lobbyRefresh);
        viewer.lobbyRefresh = null;
    }
}

const GAME_LABELS = {
    chess: 'Chess',
    trustgame: 'Trust Game',
    codenames: 'Codenames',
    poker: 'Poker',
    avalon: 'Avalon',
};

function buildGameTabs(matches) {
    const tabsEl = document.getElementById('game-tabs');
    const games = [...new Set(matches.map(m => m.game))].sort();

    tabsEl.innerHTML = `<button class="game-tab ${lobby.gameFilter === 'all' ? 'active' : ''}"
        onclick="setGameFilter('all')">All</button>` +
        games.map(g => `<button class="game-tab ${lobby.gameFilter === g ? 'active' : ''}"
            onclick="setGameFilter('${g}')">${GAME_LABELS[g] || g}</button>`
        ).join('');
}

function setGameFilter(game) {
    lobby.gameFilter = game;
    // Update tab active state
    document.querySelectorAll('.game-tab').forEach(t => {
        t.classList.toggle('active', t.textContent === (GAME_LABELS[game] || game) || (game === 'all' && t.textContent === 'All'));
    });
    applyFilters();
}

function applyFilters() {
    const recentSection = document.getElementById('recent-section');
    const recentList = document.getElementById('recent-list');
    let filtered = lobby.allMatches;

    // Game filter
    if (lobby.gameFilter !== 'all') {
        filtered = filtered.filter(m => m.game === lobby.gameFilter);
    }

    // Sort
    const sort = document.getElementById('sort-select')?.value || 'newest';
    if (sort === 'newest') {
        filtered.sort((a, b) => b.timestamp - a.timestamp);
    } else if (sort === 'oldest') {
        filtered.sort((a, b) => a.timestamp - b.timestamp);
    } else if (sort === 'name') {
        filtered.sort((a, b) => a.match_id.localeCompare(b.match_id));
    } else if (sort === 'turns') {
        filtered.sort((a, b) => b.turn_count - a.turn_count);
    }

    if (filtered.length > 0) {
        recentSection.style.display = '';
        recentList.innerHTML = filtered.map(m => `
            <div class="match-card" onclick="navigateTo('${m.match_id}')">
                <div class="game-name">${GAME_LABELS[m.game] || m.game}</div>
                <div class="match-id">${m.match_id}</div>
                <div class="agents-names">${m.agents.join(' vs ')}</div>
                <div class="match-meta">
                    <span class="result-text">${m.result?.summary || m.result?.outcome || 'Completed'}</span>
                    <span>${m.turn_count}t</span>
                </div>
            </div>
        `).join('');
    } else {
        recentSection.style.display = 'none';
    }
}

let leaderboardData = null;
let leaderboardTab = 'overall';

async function loadLeaderboard() {
    // Try API server first (has ELO from --submit matches)
    let apiLeaderboard = null;
    if (typeof LXM_API !== 'undefined') {
        try {
            const games = ['chess', 'poker', 'avalon', 'codenames', 'trustgame', 'tictactoe'];
            const apiAgents = {};
            for (const game of games) {
                const res = await fetch(`${LXM_API}/api/leaderboard/${game}`);
                if (res.ok) {
                    const entries = await res.json();
                    for (const e of entries) {
                        if (!apiAgents[e.agent_id]) {
                            apiAgents[e.agent_id] = {
                                display_name: e.display_name,
                                elo: 1500, wins: 0, losses: 0, draws: 0, games: 0,
                                by_game: {},
                            };
                        }
                        apiAgents[e.agent_id].by_game[game] = {
                            elo: e.elo, wins: e.wins, losses: e.losses, draws: e.draws,
                            games: e.wins + e.losses + e.draws,
                        };
                        apiAgents[e.agent_id].wins += e.wins;
                        apiAgents[e.agent_id].losses += e.losses;
                        apiAgents[e.agent_id].draws += e.draws;
                        apiAgents[e.agent_id].games += e.wins + e.losses + e.draws;
                    }
                }
            }
            // Calculate overall ELO as average of game ELOs
            for (const [id, a] of Object.entries(apiAgents)) {
                const elos = Object.values(a.by_game).map(g => g.elo);
                a.elo = elos.length ? Math.round(elos.reduce((s, e) => s + e, 0) / elos.length) : 1500;
            }
            if (Object.keys(apiAgents).length > 0) {
                const apiGames = [...new Set(Object.values(apiAgents).flatMap(a => Object.keys(a.by_game)))];
                apiLeaderboard = { agents: apiAgents, games: apiGames, game_weights: {} };
            }
        } catch (e) {
            // API server not available
        }
    }

    // Fall back to local viewer leaderboard
    leaderboardData = apiLeaderboard || await fetchJSON('/api/leaderboard');

    const section = document.getElementById('leaderboard-section');
    const board = document.getElementById('leaderboard');

    if (!leaderboardData || !leaderboardData.agents || Object.keys(leaderboardData.agents).length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = '';
    leaderboardTab = 'overall';
    renderLeaderboard();
}

function renderLeaderboard() {
    const data = leaderboardData;
    const board = document.getElementById('leaderboard');
    const games = data.games || [];
    const weights = data.game_weights || {};

    // Build tabs
    const tabs = ['overall', ...games];
    const tabsHtml = tabs.map(t => {
        const active = t === leaderboardTab ? 'active' : '';
        const label = t === 'overall' ? 'Overall' : t;
        const weightLabel = t !== 'overall' && weights[t] !== undefined ? ` (×${weights[t]})` : '';
        return `<button class="lb-tab ${active}" onclick="switchLeaderboardTab('${t}')">${label}${weightLabel}</button>`;
    }).join('');

    // Get sorted agents for current tab
    let sorted;
    if (leaderboardTab === 'overall') {
        sorted = Object.entries(data.agents)
            .sort((a, b) => b[1].elo - a[1].elo);
    } else {
        sorted = Object.entries(data.agents)
            .filter(([, a]) => a.by_game[leaderboardTab] && a.by_game[leaderboardTab].games > 0)
            .sort((a, b) => {
                const eloA = a[1].by_game[leaderboardTab]?.elo || 1200;
                const eloB = b[1].by_game[leaderboardTab]?.elo || 1200;
                return eloB - eloA;
            });
    }

    const rowsHtml = sorted.map(([id, a], i) => {
        let elo, wins, losses, draws, gameCount;
        if (leaderboardTab === 'overall') {
            elo = a.elo; wins = a.wins; losses = a.losses; draws = a.draws; gameCount = a.games;
        } else {
            const gs = a.by_game[leaderboardTab];
            elo = gs.elo; wins = gs.wins; losses = gs.losses; draws = gs.draws; gameCount = gs.games;
        }
        const eloClass = elo >= 1200 ? 'elo-up' : 'elo-down';
        return `
            <div class="lb-row">
                <span class="lb-rank">${i + 1}</span>
                <span class="lb-name">
                    <span class="lb-display">${a.display_name}</span>
                    <span class="lb-id">${id}</span>
                </span>
                <span class="lb-elo ${eloClass}">${elo}</span>
                <span class="lb-record">${wins} / ${losses} / ${draws}</span>
                <span class="lb-games">${gameCount}</span>
            </div>
        `;
    }).join('');

    board.innerHTML = `
        <div class="lb-tabs">${tabsHtml}</div>
        <div class="lb-header">
            <span class="lb-rank">#</span>
            <span class="lb-name">Agent</span>
            <span class="lb-elo">ELO</span>
            <span class="lb-record">W / L / D</span>
            <span class="lb-games">Games</span>
        </div>
        ${rowsHtml}
    `;
}

function switchLeaderboardTab(tab) {
    leaderboardTab = tab;
    renderLeaderboard();
}

// ─── Navigation ───

function navigateTo(matchId) {
    window.location.hash = matchId ? `/match/${matchId}` : '/';
}

function handleRoute() {
    const hash = window.location.hash.slice(1) || '/';

    // Cleanup
    stopPlay();
    if (viewer.liveSource) {
        viewer.liveSource.close();
        viewer.liveSource = null;
    }

    // Cleanup multi-view on navigate away
    cleanupMultiView();

    if (hash.startsWith('/multi/')) {
        const ids = hash.replace('/multi/', '').split(',').filter(Boolean);
        showPage('multi-page');
        loadMultiView(ids);
    } else if (hash.startsWith('/match/')) {
        const matchId = hash.replace('/match/', '');
        showPage('viewer-page');
        loadMatch(matchId);
    } else {
        showPage('home-page');
        loadMatchList();
    }
}

function showPage(id) {
    document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
    document.getElementById(id).style.display = '';
}

// ─── Match Viewer ───

async function loadMatch(matchId) {
    const [config, log, result] = await Promise.all([
        fetchJSON(`/api/match/${matchId}/config`),
        fetchJSON(`/api/match/${matchId}/log`),
        fetchJSON(`/api/match/${matchId}/result`),
    ]);

    if (!config || !log) {
        alert('Failed to load match data');
        navigateTo(null);
        return;
    }

    viewer.matchConfig = config;
    viewer.log = log;
    viewer.result = result;
    viewer.mode = result ? 'replay' : 'live';

    // Filter moves that changed game state (accepted + timeout with auto-move)
    viewer.acceptedLog = log.filter(e => e.result === 'accepted' || (e.result === 'timeout' && e.post_move_state));
    viewer.maxTurn = viewer.acceptedLog.length;
    viewer.currentTurn = 0;

    // Update UI
    const gameName = config.game?.name || 'Unknown';
    document.getElementById('match-title').textContent = `${gameName} — ${matchId}`;
    const badge = document.getElementById('mode-badge');
    badge.textContent = viewer.mode === 'live' ? 'Live' : 'Replay';
    badge.className = 'badge' + (viewer.mode === 'live' ? ' live' : '');

    // Update export button label
    updateExportButton();

    // Setup renderer
    const RendererClass = window.LxMRenderers?.[gameName];
    if (!RendererClass) {
        alert(`No renderer for game: ${gameName}`);
        return;
    }
    const container = document.getElementById('board-container');
    container.innerHTML = '';
    viewer.renderer = new RendererClass(container);

    // Adjust container aspect ratio to match canvas
    const canvas = container.querySelector('canvas');
    if (canvas) {
        container.style.aspectRatio = `${canvas.width} / ${canvas.height}`;
    }

    // Reconstruct states
    reconstructStates();

    // Hand navigation (poker)
    buildHandBoundaries();
    setupHandNav();

    // Setup agents UI
    setupAgents();

    // Setup scrubber
    const scrubber = document.getElementById('scrubber');
    scrubber.max = viewer.maxTurn;
    scrubber.value = 0;

    // Render initial state
    // Live mode and completed replays jump to latest turn;
    // in-progress replays start at turn 0
    if (viewer.mode === 'live' || viewer.result) {
        goToTurn(viewer.maxTurn);
    } else {
        goToTurn(0);
    }

    // Setup move log
    renderMoveLog();

    // Live mode polling
    if (viewer.mode === 'live') {
        startLiveMode(matchId);
    }
}

function reconstructStates() {
    const states = [];
    const initial = viewer.renderer.initialState(viewer.matchConfig);
    states.push(initial);

    let current = initial;
    for (const entry of viewer.acceptedLog) {
        current = viewer.renderer.applyMove(current, entry);
        states.push(current);
    }
    viewer.gameStates = states;
}

function buildHandBoundaries() {
    viewer.handBoundaries = [];
    let lastHand = -1;
    for (let i = 0; i < viewer.gameStates.length; i++) {
        const g = viewer.gameStates[i]?.game?.current;
        if (!g) continue;
        const h = g.hand_number;
        if (h !== undefined && h !== lastHand) {
            viewer.handBoundaries.push({ hand: h, turnIndex: i });
            lastHand = h;
        }
    }
}

function setupHandNav() {
    const nav = document.getElementById('hand-nav');
    const gameName = viewer.matchConfig?.game?.name;

    if (gameName !== 'poker' || viewer.handBoundaries.length <= 1) {
        nav.style.display = 'none';
        return;
    }

    nav.style.display = '';
    const sel = document.getElementById('hand-select');
    sel.innerHTML = viewer.handBoundaries.map(b =>
        `<option value="${b.turnIndex}">Hand #${b.hand}</option>`
    ).join('');
    sel.value = viewer.handBoundaries[0].turnIndex;
}

function updateHandNav() {
    const nav = document.getElementById('hand-nav');
    if (nav.style.display === 'none') return;

    const sel = document.getElementById('hand-select');
    const turn = viewer.currentTurn;

    // Find which hand we're in
    let currentHandIdx = 0;
    for (let i = viewer.handBoundaries.length - 1; i >= 0; i--) {
        if (turn >= viewer.handBoundaries[i].turnIndex) {
            currentHandIdx = i;
            break;
        }
    }
    sel.value = viewer.handBoundaries[currentHandIdx].turnIndex;

    document.getElementById('btn-prev-hand').disabled = (currentHandIdx === 0);
    document.getElementById('btn-next-hand').disabled = (currentHandIdx >= viewer.handBoundaries.length - 1);
}

function prevHand() {
    const turn = viewer.currentTurn;
    for (let i = viewer.handBoundaries.length - 1; i >= 0; i--) {
        if (viewer.handBoundaries[i].turnIndex < turn) {
            goToTurn(viewer.handBoundaries[i].turnIndex);
            return;
        }
    }
}

function nextHand() {
    const turn = viewer.currentTurn;
    for (let i = 0; i < viewer.handBoundaries.length; i++) {
        if (viewer.handBoundaries[i].turnIndex > turn) {
            goToTurn(viewer.handBoundaries[i].turnIndex);
            return;
        }
    }
}

function setupAgents() {
    const row = document.getElementById('agents-row');
    const agents = viewer.matchConfig.agents || [];
    const state0 = viewer.gameStates[0] || {};
    const marks = state0.marks || {};
    const colors = state0.colors || {};

    row.innerHTML = agents.map(a => {
        const mark = marks[a.agent_id];
        const color = colors[a.agent_id];
        let label, labelClass;
        if (mark) {
            label = mark;
            labelClass = mark === 'X' ? 'mark-x' : 'mark-o';
        } else if (color) {
            label = color === 'white' ? '\u2654' : '\u265A';
            labelClass = color === 'white' ? 'mark-white' : 'mark-black';
        } else {
            label = '?';
            labelClass = '';
        }
        return `
            <div class="agent-card" data-agent="${a.agent_id}">
                <div class="agent-name">
                    <span class="agent-mark ${labelClass}">${label}</span>
                    ${a.display_name || a.agent_id}
                    <span class="turn-dot"></span>
                </div>
            </div>
        `;
    }).join('');
}

function renderMoveLog() {
    const log = document.getElementById('move-log');
    const state0 = viewer.gameStates[0] || {};
    const marks = state0.marks || {};
    const colors = state0.colors || {};

    log.innerHTML = viewer.acceptedLog.map((entry, i) => {
        const turnNum = i + 1;
        const agentId = entry.agent_id;
        const label = marks[agentId] || (colors[agentId] ? colors[agentId][0].toUpperCase() : '?');
        const summary = viewer.renderer.formatMoveSummary(entry);
        return `<div class="log-entry" data-turn="${turnNum}" onclick="goToTurn(${turnNum})">
            <span class="turn-num">T${turnNum}</span>
            ${agentId} (${label}) ${summary}
        </div>`;
    }).join('');
}

// ─── Playback ───

function goToTurn(turn) {
    turn = Math.max(0, Math.min(turn, viewer.maxTurn));
    viewer.currentTurn = turn;

    const state = viewer.gameStates[turn];
    const lastMove = turn > 0 ? viewer.acceptedLog[turn - 1] : null;
    const animate = false; // Animate only on next/auto-play

    viewer.renderer.render(state, turn, lastMove, animate);

    // Show result if at end and game is over
    const overlay = document.getElementById('result-overlay');
    if (turn === viewer.maxTurn && viewer.result) {
        viewer.renderer.renderResult(viewer.result, state);
        overlay.textContent = viewer.result.summary;
        overlay.style.display = '';
    } else {
        overlay.style.display = 'none';
    }

    // Update controls
    document.getElementById('scrubber').value = turn;
    document.getElementById('turn-display').textContent = `Turn ${turn} / ${viewer.maxTurn}`;

    // Highlight current log entry
    document.querySelectorAll('.log-entry').forEach(el => {
        el.classList.toggle('current', parseInt(el.dataset.turn) === turn);
    });

    // Scroll log entry into view
    const currentEntry = document.querySelector('.log-entry.current');
    if (currentEntry) currentEntry.scrollIntoView({ block: 'nearest' });

    // Highlight active agent
    const agents = viewer.matchConfig.agents || [];
    if (turn > 0 && turn <= viewer.maxTurn) {
        const activeAgent = viewer.acceptedLog[turn - 1]?.agent_id;
        document.querySelectorAll('.agent-card').forEach(el => {
            el.classList.toggle('active', el.dataset.agent === activeAgent);
        });
    } else if (turn === 0 && agents.length > 0) {
        // Before any move, highlight first agent
        document.querySelectorAll('.agent-card').forEach((el, i) => {
            el.classList.toggle('active', i === 0);
        });
    }

    // Disable buttons at edges
    document.getElementById('btn-prev').disabled = (turn === 0);
    document.getElementById('btn-start').disabled = (turn === 0);
    document.getElementById('btn-next').disabled = (turn === viewer.maxTurn);
    document.getElementById('btn-end').disabled = (turn === viewer.maxTurn);

    // Update hand nav
    updateHandNav();
}

function nextTurn() {
    if (viewer.currentTurn >= viewer.maxTurn) {
        stopPlay();
        return;
    }
    const turn = viewer.currentTurn + 1;
    viewer.currentTurn = turn;

    const state = viewer.gameStates[turn];
    const lastMove = viewer.acceptedLog[turn - 1];

    viewer.renderer.render(state, turn, lastMove, true);

    // Show result at end
    const overlay = document.getElementById('result-overlay');
    if (turn === viewer.maxTurn && viewer.result) {
        viewer.renderer.renderResult(viewer.result, state);
        overlay.textContent = viewer.result.summary;
        overlay.style.display = '';
        stopPlay();
    } else {
        overlay.style.display = 'none';
    }

    // Update UI
    document.getElementById('scrubber').value = turn;
    document.getElementById('turn-display').textContent = `Turn ${turn} / ${viewer.maxTurn}`;

    document.querySelectorAll('.log-entry').forEach(el => {
        el.classList.toggle('current', parseInt(el.dataset.turn) === turn);
    });
    const currentEntry = document.querySelector('.log-entry.current');
    if (currentEntry) currentEntry.scrollIntoView({ block: 'nearest' });

    const activeAgent = lastMove?.agent_id;
    document.querySelectorAll('.agent-card').forEach(el => {
        el.classList.toggle('active', el.dataset.agent === activeAgent);
    });

    document.getElementById('btn-prev').disabled = false;
    document.getElementById('btn-start').disabled = false;
    document.getElementById('btn-next').disabled = (turn === viewer.maxTurn);
    document.getElementById('btn-end').disabled = (turn === viewer.maxTurn);
}

function prevTurn() {
    if (viewer.currentTurn > 0) goToTurn(viewer.currentTurn - 1);
}

function togglePlay() {
    if (viewer.playing) {
        stopPlay();
    } else {
        startPlay();
    }
}

function startPlay() {
    if (viewer.currentTurn >= viewer.maxTurn) {
        goToTurn(0); // Restart from beginning
    }
    viewer.playing = true;
    document.getElementById('btn-play').innerHTML = '&#10074;&#10074;';
    const interval = 1500 / viewer.playbackSpeed;
    viewer.playInterval = setInterval(() => {
        nextTurn();
        if (viewer.currentTurn >= viewer.maxTurn) stopPlay();
    }, interval);
}

function stopPlay() {
    viewer.playing = false;
    document.getElementById('btn-play').innerHTML = '&#9654;';
    if (viewer.playInterval) {
        clearInterval(viewer.playInterval);
        viewer.playInterval = null;
    }
}

// ─── Live Mode (SSE) ───

function startLiveMode(matchId) {
    // Use Server-Sent Events instead of polling
    const fromTurn = viewer.acceptedLog.length;
    const source = new EventSource(`/api/match/${matchId}/stream?from=${fromTurn}`);
    viewer.liveSource = source;

    source.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'move') {
            const entry = data.entry;
            viewer.acceptedLog.push(entry);
            viewer.maxTurn = viewer.acceptedLog.length;

            // Reconstruct only the new state (incremental)
            const prevState = viewer.gameStates[viewer.gameStates.length - 1];
            const newState = viewer.renderer.applyMove(prevState, entry);
            viewer.gameStates.push(newState);

            // Update UI
            renderMoveLog();
            document.getElementById('scrubber').max = viewer.maxTurn;
            buildHandBoundaries();
            setupHandNav();

            // Auto-advance to latest
            goToTurn(viewer.maxTurn);
        } else if (data.type === 'result') {
            viewer.result = data.result;
            viewer.mode = 'replay';
            const badge = document.getElementById('mode-badge');
            badge.textContent = 'Replay';
            badge.className = 'badge';
            updateExportButton();
            source.close();
            viewer.liveSource = null;
            goToTurn(viewer.maxTurn);
        } else if (data.type === 'dead') {
            viewer.mode = 'replay';
            const badge = document.getElementById('mode-badge');
            badge.textContent = 'Dead';
            badge.className = 'badge badge-dead';
            source.close();
            viewer.liveSource = null;
            // Navigate back to lobby after brief delay
            setTimeout(() => navigateTo(''), 3000);
        }
    };

    source.onerror = () => {
        // SSE connection lost — fall back to one-shot poll after delay
        source.close();
        viewer.liveSource = null;
        setTimeout(() => {
            if (viewer.mode === 'live') startLiveMode(matchId);
        }, 5000);
    };
}

// ─── Lobby Selection ───

function updateWatchButton() {
    const checked = document.querySelectorAll('.live-select:checked');
    const btn = document.getElementById('btn-watch-selected');
    if (checked.length >= 2) {
        btn.style.display = '';
        btn.textContent = `Watch ${checked.length} Selected`;
    } else {
        btn.style.display = 'none';
    }
}

function watchSelected() {
    const checked = document.querySelectorAll('.live-select:checked');
    const ids = Array.from(checked).map(cb => cb.value);
    if (ids.length >= 2) {
        window.location.hash = `/multi/${ids.join(',')}`;
    }
}

// ─── Multi-View ───

const multiView = {
    cells: [],       // { matchId, renderer, gameStates, acceptedLog, maxTurn, source, cellEl }
    matchIds: [],    // Currently displayed match IDs
    allMatches: [],  // Cached match list for picker
};

async function loadMultiView(matchIds) {
    const matches = await fetchJSON('/api/matches');
    if (!matches) return;
    multiView.allMatches = matches;

    // Clean up previous cells
    cleanupMultiView();

    const grid = document.getElementById('multi-grid');
    grid.innerHTML = '';

    // Filter to requested matches
    const toShow = matches.filter(m => matchIds.includes(m.match_id));
    multiView.matchIds = toShow.map(m => m.match_id);

    const liveCount = toShow.filter(m => m.status !== 'completed').length;
    document.getElementById('multi-live-count').textContent = `${liveCount} live`;

    for (const m of toShow) {
        addMultiCell(m, grid);
    }
}

function addMultiCell(matchInfo, grid) {
    const m = matchInfo;
    const cell = document.createElement('div');
    cell.className = 'multi-cell' + (m.status !== 'completed' ? ' live' : '');
    cell.dataset.matchId = m.match_id;
    cell.innerHTML = `
        <div class="multi-header">
            <span class="multi-game">${m.game}</span>
            <span class="multi-agents">${m.agents.join(' vs ')}</span>
            <span class="multi-turn">T${m.turn_count}</span>
            ${m.status !== 'completed' ? '<span class="live-dot"></span>' : ''}
            <button class="multi-remove" onclick="event.stopPropagation(); removeMultiCell('${m.match_id}')" title="Remove">&times;</button>
        </div>
        <div class="multi-board" data-match="${m.match_id}"></div>
        <div class="multi-status"></div>
    `;
    cell.addEventListener('click', () => navigateTo(m.match_id));
    grid.appendChild(cell);

    initMultiCell(m, cell);
}

async function initMultiCell(matchInfo, cellEl) {
    const matchId = matchInfo.match_id;
    const [config, log, result] = await Promise.all([
        fetchJSON(`/api/match/${matchId}/config`),
        fetchJSON(`/api/match/${matchId}/log`),
        fetchJSON(`/api/match/${matchId}/result`),
    ]);

    if (!config || !log) return;

    const gameName = config.game?.name || 'Unknown';
    const RendererClass = window.LxMRenderers?.[gameName];
    if (!RendererClass) return;

    const boardEl = cellEl.querySelector('.multi-board');
    const statusEl = cellEl.querySelector('.multi-status');
    const renderer = new RendererClass(boardEl);
    const acceptedLog = log.filter(e => e.result === 'accepted');

    // Reconstruct states
    const gameStates = [renderer.initialState(config)];
    let current = gameStates[0];
    for (const entry of acceptedLog) {
        current = renderer.applyMove(current, entry);
        gameStates.push(current);
    }

    const maxTurn = acceptedLog.length;
    const lastMove = maxTurn > 0 ? acceptedLog[maxTurn - 1] : null;
    renderer.render(gameStates[maxTurn], maxTurn, lastMove, false);

    if (result) {
        statusEl.textContent = result.summary || result.outcome;
        statusEl.className = 'multi-status completed';
    }

    const cellData = {
        matchId, renderer, gameStates, acceptedLog, maxTurn, source: null,
        config, turnEl: cellEl.querySelector('.multi-turn'), statusEl, cellEl,
    };
    multiView.cells.push(cellData);

    // SSE for live games
    if (!result) {
        const fromTurn = acceptedLog.length;
        const source = new EventSource(`/api/match/${matchId}/stream?from=${fromTurn}`);
        cellData.source = source;

        source.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'move') {
                cellData.acceptedLog.push(data.entry);
                cellData.maxTurn = cellData.acceptedLog.length;

                const prevState = cellData.gameStates[cellData.gameStates.length - 1];
                const newState = cellData.renderer.applyMove(prevState, data.entry);
                cellData.gameStates.push(newState);

                cellData.renderer.render(newState, cellData.maxTurn, data.entry, true);
                cellData.turnEl.textContent = `T${cellData.maxTurn}`;
            } else if (data.type === 'result') {
                cellData.statusEl.textContent = data.result.summary || data.result.outcome;
                cellData.statusEl.className = 'multi-status completed';
                cellData.cellEl.classList.remove('live');
                source.close();
                cellData.source = null;
                // Update live count
                const liveCount = multiView.cells.filter(c => c.source !== null).length;
                document.getElementById('multi-live-count').textContent = `${liveCount} live`;
            } else if (data.type === 'dead') {
                cellData.statusEl.textContent = 'Process died';
                cellData.statusEl.className = 'multi-status dead';
                cellData.cellEl.classList.remove('live');
                source.close();
                cellData.source = null;
                const liveCount = multiView.cells.filter(c => c.source !== null).length;
                document.getElementById('multi-live-count').textContent = `${liveCount} live`;
                // Remove cell after brief display
                setTimeout(() => removeMultiCell(matchId), 3000);
            }
        };

        source.onerror = () => { source.close(); cellData.source = null; };
    }
}

function removeMultiCell(matchId) {
    // Cleanup SSE
    const idx = multiView.cells.findIndex(c => c.matchId === matchId);
    if (idx !== -1) {
        if (multiView.cells[idx].source) multiView.cells[idx].source.close();
        multiView.cells.splice(idx, 1);
    }
    // Remove from DOM
    const cell = document.querySelector(`.multi-cell[data-match-id="${matchId}"]`);
    if (cell) cell.remove();
    // Update URL
    multiView.matchIds = multiView.matchIds.filter(id => id !== matchId);
    if (multiView.matchIds.length === 0) {
        navigateTo(null);
    } else {
        history.replaceState(null, '', `#/multi/${multiView.matchIds.join(',')}`);
    }
}

// Match picker for adding to multi-view
async function toggleMatchPicker() {
    const picker = document.getElementById('match-picker');
    if (picker.style.display !== 'none') {
        picker.style.display = 'none';
        return;
    }

    const matches = await fetchJSON('/api/matches');
    if (!matches) return;
    multiView.allMatches = matches;

    const available = matches.filter(m => !multiView.matchIds.includes(m.match_id));
    const list = document.getElementById('picker-list');

    if (available.length === 0) {
        list.innerHTML = '<div class="picker-empty">No more matches available</div>';
    } else {
        list.innerHTML = available.map(m => {
            const isLive = m.status !== 'completed';
            return `
                <div class="picker-item ${isLive ? 'live' : ''}" onclick="addFromPicker('${m.match_id}')">
                    ${isLive ? '<span class="live-dot"></span>' : ''}
                    <span class="picker-game">${m.game}</span>
                    <span class="picker-agents">${m.agents.join(' vs ')}</span>
                    <span class="picker-turn">T${m.turn_count}</span>
                </div>
            `;
        }).join('');
    }
    picker.style.display = '';
}

async function addFromPicker(matchId) {
    document.getElementById('match-picker').style.display = 'none';

    if (multiView.matchIds.includes(matchId)) return;

    const matchInfo = multiView.allMatches.find(m => m.match_id === matchId);
    if (!matchInfo) return;

    multiView.matchIds.push(matchId);
    history.replaceState(null, '', `#/multi/${multiView.matchIds.join(',')}`);

    const grid = document.getElementById('multi-grid');
    addMultiCell(matchInfo, grid);

    // Update live count
    const liveCount = multiView.cells.filter(c => c.source !== null).length;
    document.getElementById('multi-live-count').textContent = `${liveCount} live`;
}

function cleanupMultiView() {
    for (const cell of multiView.cells) {
        if (cell.source) { cell.source.close(); cell.source = null; }
    }
    multiView.cells = [];
    multiView.matchIds = [];
}

// ─── Export ───

async function exportReplay(format) {
    const matchId = viewer.matchConfig?.match_id;
    if (!matchId) return;

    // Auto-select format: MP4 for chess (many turns), GIF for short games
    if (!format) {
        const gameName = viewer.matchConfig?.game?.name;
        format = (gameName === 'tictactoe') ? 'gif' : 'mp4';
    }

    const btn = document.getElementById('btn-export');
    btn.disabled = true;
    btn.textContent = 'Exporting...';

    try {
        const speed = viewer.playbackSpeed;
        const res = await fetch(`/api/match/${matchId}/export?speed=${speed}&format=${format}`);
        if (!res.ok) throw new Error('Export failed');

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${matchId}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error('Export error:', e);
    } finally {
        btn.disabled = false;
        updateExportButton();
    }
}

function updateExportButton() {
    const btn = document.getElementById('btn-export');
    const gameName = viewer.matchConfig?.game?.name;
    btn.textContent = (gameName === 'tictactoe') ? 'Export GIF' : 'Export MP4';
}

// ─── Event Listeners ───

document.addEventListener('DOMContentLoaded', () => {
    // Button handlers
    document.getElementById('btn-export').addEventListener('click', () => exportReplay());
    document.getElementById('btn-start').addEventListener('click', () => goToTurn(0));
    document.getElementById('btn-prev').addEventListener('click', prevTurn);
    document.getElementById('btn-play').addEventListener('click', togglePlay);
    document.getElementById('btn-next').addEventListener('click', nextTurn);
    document.getElementById('btn-end').addEventListener('click', () => goToTurn(viewer.maxTurn));

    // Hand navigation (poker)
    document.getElementById('btn-prev-hand').addEventListener('click', prevHand);
    document.getElementById('btn-next-hand').addEventListener('click', nextHand);
    document.getElementById('hand-select').addEventListener('change', (e) => {
        goToTurn(parseInt(e.target.value));
    });

    // Scrubber
    document.getElementById('scrubber').addEventListener('input', (e) => {
        goToTurn(parseInt(e.target.value));
    });

    // Speed
    document.getElementById('speed-select').addEventListener('change', (e) => {
        viewer.playbackSpeed = parseInt(e.target.value);
        if (viewer.playing) {
            stopPlay();
            startPlay();
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (document.getElementById('viewer-page').style.display === 'none') return;
        if (e.key === 'ArrowRight') nextTurn();
        else if (e.key === 'ArrowLeft') prevTurn();
        else if (e.key === ' ') { e.preventDefault(); togglePlay(); }
        else if (e.key === 'Home') goToTurn(0);
        else if (e.key === 'End') goToTurn(viewer.maxTurn);
    });

    // Hash routing
    window.addEventListener('hashchange', handleRoute);
    handleRoute();
});
