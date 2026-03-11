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
    liveInterval: null,
    acceptedLog: [],   // Only accepted moves
};

// ─── API ───

async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) return null;
    return res.json();
}

// ─── Home Page ───

async function loadMatchList() {
    const matches = await fetchJSON('/api/matches');
    const list = document.getElementById('match-list');
    const empty = document.getElementById('no-matches');

    if (!matches || matches.length === 0) {
        empty.style.display = '';
        list.innerHTML = '';
        return;
    }
    empty.style.display = 'none';

    list.innerHTML = matches.map(m => {
        const statusHtml = m.status === 'completed'
            ? `<span class="result-text">${m.result?.summary || m.result?.outcome || 'Completed'}</span>`
            : `<span class="live-text">LIVE</span>`;
        return `
            <div class="match-card" onclick="navigateTo('${m.match_id}')">
                <div class="game-name">${m.game}</div>
                <div class="match-id">${m.match_id}</div>
                <div class="agents-names">${m.agents.join(' vs ')}</div>
                <div class="match-meta">
                    ${statusHtml}
                    <span>${m.turn_count} turns</span>
                </div>
            </div>
        `;
    }).join('');
}

// ─── Navigation ───

function navigateTo(matchId) {
    window.location.hash = matchId ? `/match/${matchId}` : '/';
}

function handleRoute() {
    const hash = window.location.hash.slice(1) || '/';

    // Cleanup
    stopPlay();
    if (viewer.liveInterval) {
        clearInterval(viewer.liveInterval);
        viewer.liveInterval = null;
    }

    if (hash.startsWith('/match/')) {
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

    // Filter accepted moves
    viewer.acceptedLog = log.filter(e => e.result === 'accepted');
    viewer.maxTurn = viewer.acceptedLog.length;
    viewer.currentTurn = 0;

    // Update UI
    const gameName = config.game?.name || 'Unknown';
    document.getElementById('match-title').textContent = `${gameName} — ${matchId}`;
    const badge = document.getElementById('mode-badge');
    badge.textContent = viewer.mode === 'live' ? 'Live' : 'Replay';
    badge.className = 'badge' + (viewer.mode === 'live' ? ' live' : '');

    // Setup renderer
    const RendererClass = window.LxMRenderers?.[gameName];
    if (!RendererClass) {
        alert(`No renderer for game: ${gameName}`);
        return;
    }
    const container = document.getElementById('board-container');
    container.innerHTML = '';
    viewer.renderer = new RendererClass(container);

    // Reconstruct states
    reconstructStates();

    // Setup agents UI
    setupAgents();

    // Setup scrubber
    const scrubber = document.getElementById('scrubber');
    scrubber.max = viewer.maxTurn;
    scrubber.value = 0;

    // Render initial state
    goToTurn(0);

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

function setupAgents() {
    const row = document.getElementById('agents-row');
    const agents = viewer.matchConfig.agents || [];
    const marks = viewer.gameStates[0]?.marks || {};

    row.innerHTML = agents.map(a => {
        const mark = marks[a.agent_id] || '?';
        const markClass = mark === 'X' ? 'mark-x' : 'mark-o';
        return `
            <div class="agent-card" data-agent="${a.agent_id}">
                <div class="agent-name">
                    <span class="agent-mark ${markClass}">${mark}</span>
                    ${a.display_name || a.agent_id}
                    <span class="turn-dot"></span>
                </div>
            </div>
        `;
    }).join('');
}

function renderMoveLog() {
    const log = document.getElementById('move-log');
    const marks = viewer.gameStates[0]?.marks || {};

    log.innerHTML = viewer.acceptedLog.map((entry, i) => {
        const turnNum = i + 1;
        const agentId = entry.agent_id;
        const mark = marks[agentId] || '?';
        const summary = viewer.renderer.formatMoveSummary(entry);
        return `<div class="log-entry" data-turn="${turnNum}" onclick="goToTurn(${turnNum})">
            <span class="turn-num">T${turnNum}</span>
            ${agentId} (${mark}) ${summary}
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

// ─── Live Mode ───

function startLiveMode(matchId) {
    viewer.liveInterval = setInterval(async () => {
        const log = await fetchJSON(`/api/match/${matchId}/log`);
        const result = await fetchJSON(`/api/match/${matchId}/result`);

        if (!log) return;

        const newAccepted = log.filter(e => e.result === 'accepted');
        if (newAccepted.length > viewer.acceptedLog.length) {
            viewer.log = log;
            viewer.acceptedLog = newAccepted;
            viewer.maxTurn = newAccepted.length;

            reconstructStates();
            renderMoveLog();

            document.getElementById('scrubber').max = viewer.maxTurn;

            // Auto-advance to latest
            goToTurn(viewer.maxTurn);
        }

        if (result) {
            viewer.result = result;
            viewer.mode = 'replay';
            const badge = document.getElementById('mode-badge');
            badge.textContent = 'Replay';
            badge.className = 'badge';
            clearInterval(viewer.liveInterval);
            viewer.liveInterval = null;
            goToTurn(viewer.maxTurn);
        }
    }, 2000);
}

// ─── Export ───

async function exportGif() {
    const matchId = viewer.matchConfig?.match_id;
    if (!matchId) return;

    const btn = document.getElementById('btn-export');
    btn.disabled = true;
    btn.textContent = 'Exporting...';

    try {
        const speed = viewer.playbackSpeed;
        const res = await fetch(`/api/match/${matchId}/export?speed=${speed}`);
        if (!res.ok) throw new Error('Export failed');

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${matchId}.gif`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error('Export error:', e);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Export GIF';
    }
}

// ─── Event Listeners ───

document.addEventListener('DOMContentLoaded', () => {
    // Button handlers
    document.getElementById('btn-export').addEventListener('click', exportGif);
    document.getElementById('btn-start').addEventListener('click', () => goToTurn(0));
    document.getElementById('btn-prev').addEventListener('click', prevTurn);
    document.getElementById('btn-play').addEventListener('click', togglePlay);
    document.getElementById('btn-next').addEventListener('click', nextTurn);
    document.getElementById('btn-end').addEventListener('click', () => goToTurn(viewer.maxTurn));

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
