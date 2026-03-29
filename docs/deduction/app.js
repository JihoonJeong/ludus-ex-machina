/**
 * LxM Deduction — Solo Mode (Human Player)
 * Pure client-side. Loads scenarios from static JSON.
 */

const state = {
    lang: 'en',
    scenario: null,
    scenarioId: null,
    filesRead: new Set(),
    selectedCulprit: null,
    startTime: null,
    submitted: false,
};

// Base path for data
const DATA_BASE = window.location.hostname.includes('github.io')
    ? '/ludus-ex-machina/deduction/scenarios'
    : './scenarios';

// ── Scenario List ──

const SCENARIOS = [
    { id: 'mystery_001', id_ko: 'mystery_001_ko' },
    { id: 'mystery_002', id_ko: null },
    { id: 'mystery_003', id_ko: null },
];

async function loadScenarioList() {
    const grid = document.getElementById('scenario-list');
    grid.innerHTML = '';

    for (const s of SCENARIOS) {
        const sid = state.lang === 'ko' && s.id_ko ? s.id_ko : s.id;
        try {
            const res = await fetch(`${DATA_BASE}/${sid}/scenario.json`);
            if (!res.ok) continue;
            const data = await res.json();

            const card = document.createElement('div');
            card.className = 'scenario-card';
            card.onclick = () => startGame(sid);
            card.innerHTML = `
                <span class="difficulty ${data.difficulty}">${data.difficulty.toUpperCase()}</span>
                <h3>${data.title}</h3>
                <p class="desc">${data.description}</p>
                <p class="meta">${data.suspects.length} suspects · ${data.evidence_files.length} evidence files</p>
            `;
            grid.appendChild(card);
        } catch (e) {
            console.warn(`Failed to load ${sid}:`, e);
        }
    }
}

// ── Game ──

async function startGame(scenarioId) {
    const res = await fetch(`${DATA_BASE}/${scenarioId}/scenario.json`);
    state.scenario = await res.json();
    state.scenarioId = scenarioId;
    state.filesRead = new Set();
    state.selectedCulprit = null;
    state.submitted = false;
    state.startTime = Date.now();

    // Load case brief
    const briefRes = await fetch(`${DATA_BASE}/${scenarioId}/case_brief.md`);
    state.caseBrief = await briefRes.text();

    // Setup UI
    document.getElementById('scenario-select').style.display = 'none';
    document.getElementById('game-page').style.display = '';
    document.getElementById('result-page').style.display = 'none';

    renderEvidenceList();
    renderSuspects();
    renderOptions();
    showBrief();
    updateReadCount();
}

function renderEvidenceList() {
    const list = document.getElementById('evidence-list');
    const scenario = state.scenario;

    // Get all evidence files from scenario
    const files = scenario.evidence_files || [];
    list.innerHTML = files.map(f => `
        <div class="evidence-item" data-file="${f}" onclick="readEvidence('${f}')">
            <span class="evidence-dot"></span>
            <span class="evidence-name">${f.replace('.md', '')}</span>
        </div>
    `).join('');
}

function renderSuspects() {
    const container = document.getElementById('suspect-buttons');
    const names = state.scenario.suspect_names || {};
    const suspects = state.scenario.suspects || [];

    container.innerHTML = suspects.map(s => {
        const name = names[s] || s;
        return `<button class="suspect-btn" data-suspect="${s}" onclick="selectCulprit('${s}')">${s}: ${name}</button>`;
    }).join('');
}

function renderOptions() {
    const scenario = state.scenario;
    const isKo = state.lang === 'ko';

    // Motive
    const motiveSelect = document.getElementById('motive-select');
    const motiveOpts = (isKo && scenario.motive_options_ko) ? scenario.motive_options_ko : scenario.motive_options;
    motiveSelect.innerHTML = '<option value="">-- Select motive --</option>' +
        (motiveOpts || []).map(m => `<option value="${m}">${m.replace(/_/g, ' ')}</option>`).join('');

    // Method
    const methodSelect = document.getElementById('method-select');
    const methodOpts = (isKo && scenario.method_options_ko) ? scenario.method_options_ko : scenario.method_options;
    methodSelect.innerHTML = '<option value="">-- Select method --</option>' +
        (methodOpts || []).map(m => `<option value="${m}">${m.replace(/_/g, ' ')}</option>`).join('');
}

async function readEvidence(filename) {
    try {
        const res = await fetch(`${DATA_BASE}/${state.scenarioId}/evidence/${filename}`);
        const content = await res.text();
        state.filesRead.add(filename);

        // Update UI
        document.getElementById('current-file').textContent = filename;
        document.getElementById('content-body').innerHTML = markdownToHtml(content);

        // Mark as read
        document.querySelectorAll('.evidence-item').forEach(el => {
            el.classList.remove('active');
            if (state.filesRead.has(el.dataset.file)) {
                el.classList.add('read');
            }
            if (el.dataset.file === filename) {
                el.classList.add('active');
            }
        });

        updateReadCount();
    } catch (e) {
        document.getElementById('content-body').textContent = `Error loading: ${filename}`;
    }
}

function showBrief() {
    document.getElementById('current-file').textContent = 'Case Brief';
    document.getElementById('content-body').innerHTML = markdownToHtml(state.caseBrief || 'Loading...');
    document.querySelectorAll('.evidence-item').forEach(el => el.classList.remove('active'));
}

function selectCulprit(id) {
    state.selectedCulprit = id;
    document.querySelectorAll('.suspect-btn').forEach(btn => {
        btn.classList.toggle('selected', btn.dataset.suspect === id);
    });
}

function updateReadCount() {
    const total = (state.scenario?.evidence_files || []).length;
    document.getElementById('read-count').textContent =
        `${state.filesRead.size}/${total} files read`;
}

function submitAnswer() {
    if (state.submitted) return;

    const culprit = state.selectedCulprit;
    const motive = document.getElementById('motive-select').value;
    const method = document.getElementById('method-select').value;

    if (!culprit) { alert('Select a culprit!'); return; }
    if (!motive) { alert('Select a motive!'); return; }
    if (!method) { alert('Select a method!'); return; }

    state.submitted = true;
    const elapsed = Math.round((Date.now() - state.startTime) / 1000);

    // Score
    const answer = state.scenario.answer;
    const answerKo = state.scenario.answer_ko || {};
    const culpritCorrect = culprit.toUpperCase() === answer.culprit.toUpperCase();
    const motiveCorrect = motive === answer.motive || motive === answerKo.motive;
    const methodCorrect = method === answer.method || method === answerKo.method;

    const accuracy = (culpritCorrect ? 1 : 0) + (motiveCorrect ? 1 : 0) + (methodCorrect ? 1 : 0);
    const total = (state.scenario.evidence_files || []).length;
    const efficiency = 1 - (state.filesRead.size / total);
    const finalScore = accuracy * (1 + efficiency * 0.5);

    showResult({
        culprit, motive, method,
        culpritCorrect, motiveCorrect, methodCorrect,
        accuracy, efficiency, finalScore, elapsed,
        correctAnswer: answer, correctAnswerKo: answerKo,
    });
}

function showResult(r) {
    document.getElementById('game-page').style.display = 'none';
    document.getElementById('result-page').style.display = '';

    const emoji = r.accuracy === 3 ? '🎉' : r.accuracy >= 2 ? '👍' : r.accuracy >= 1 ? '🤔' : '❌';
    document.getElementById('result-title').textContent = `${emoji} ${r.accuracy}/3 Correct`;

    const check = (ok) => ok ? '<span class="result-correct">✅</span>' : '<span class="result-wrong">❌</span>';

    document.getElementById('result-details').innerHTML = `
        <div class="result-row">
            <span>Culprit: ${r.culprit}</span>
            <span>${check(r.culpritCorrect)} (correct: ${r.correctAnswer.culprit})</span>
        </div>
        <div class="result-row">
            <span>Motive: ${r.motive.replace(/_/g, ' ')}</span>
            <span>${check(r.motiveCorrect)} (correct: ${r.correctAnswer.motive.replace(/_/g, ' ')})</span>
        </div>
        <div class="result-row">
            <span>Method: ${r.method.replace(/_/g, ' ')}</span>
            <span>${check(r.methodCorrect)} (correct: ${r.correctAnswer.method.replace(/_/g, ' ')})</span>
        </div>
        <div class="result-score">${r.finalScore.toFixed(1)}</div>
        <div style="color: var(--text-muted); font-size: 13px;">
            ${state.filesRead.size} files read · ${r.elapsed}s · efficiency ${(r.efficiency * 100).toFixed(0)}%
        </div>
    `;
}

// ── Markdown (simple) ──

function markdownToHtml(md) {
    if (!md) return '';
    return md
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^\|(.+)\|$/gm, (match) => {
            const cells = match.split('|').filter(c => c.trim());
            return '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
        })
        .replace(/(<tr>.*<\/tr>\n?)+/g, '<table>$&</table>')
        .replace(/^- (.+)$/gm, '• $1')
        .replace(/\n/g, '<br>');
}

// ── i18n ──

function setLang(lang) {
    state.lang = lang;
    document.querySelectorAll('.lang-btn').forEach(btn =>
        btn.classList.toggle('active', btn.textContent === lang.toUpperCase())
    );
    // Reload scenario list
    if (document.getElementById('scenario-select').style.display !== 'none') {
        loadScenarioList();
    }
}

// ── Routing ──

function handleRoute() {
    const hash = location.hash.slice(1);
    if (hash && hash.startsWith('/')) {
        const sid = hash.slice(1);
        startGame(sid);
    } else {
        document.getElementById('scenario-select').style.display = '';
        document.getElementById('game-page').style.display = 'none';
        document.getElementById('result-page').style.display = 'none';
        loadScenarioList();
    }
}

window.addEventListener('hashchange', handleRoute);
handleRoute();
