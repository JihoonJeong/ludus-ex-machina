/**
 * LxM Deduction — Solo Mode (Human Player)
 * Pure client-side. Loads scenarios from static JSON.
 */

const state = {
    lang: localStorage.getItem('lxm_lang') || 'en',
    scenario: null,
    scenarioId: null,
    filesRead: new Set(),
    readOrder: [],
    selectedCulprit: null,
    startTime: null,
    submitted: false,
    // Race mode
    raceMode: false,
    aiModel: null,
    aiResult: null,
    aiResults: null, // pre-loaded
};

const i18n = {
    en: {
        hero_title: '🔍 Mystery Solver',
        hero_desc: 'Choose a mystery to solve. Read the evidence, identify the culprit, motive, and method.',
        evidence_title: '📁 Evidence',
        verdict_title: '🎯 Your Verdict',
        culprit_label: 'Culprit',
        motive_label: 'Motive',
        method_label: 'Method',
        select_motive: '-- Select motive --',
        select_method: '-- Select method --',
        submit_btn: 'Submit Answer',
        notes_title: '📝 Your Notes',
        notes_placeholder: 'Write your reasoning here...',
        case_brief_btn: 'Case Brief',
        try_another: 'Try Another Mystery',
        correct_label: 'Correct',
        files_read: 'files read',
        efficiency: 'efficiency',
        suspects: 'suspects',
        evidence_files: 'evidence files',
        select_culprit: 'Select a culprit!',
        select_motive_warn: 'Select a motive!',
        select_method_warn: 'Select a method!',
        race_mode: 'Race vs AI',
        solo_mode: 'Solo',
        choose_opponent: 'Choose AI opponent:',
        start_race: 'Start Race!',
        ai_finished: 'AI has submitted an answer!',
        race_result_title: 'Race Result',
        you: 'You',
        ai: 'AI',
        winner_label: 'Winner',
        time_label: 'Time',
        faster: 'faster',
    },
    ko: {
        hero_title: '🔍 미스터리 솔버',
        hero_desc: '미스터리를 선택하세요. 증거를 읽고 범인, 동기, 수단을 밝히세요.',
        evidence_title: '📁 증거 파일',
        verdict_title: '🎯 판결',
        culprit_label: '범인',
        motive_label: '동기',
        method_label: '수단',
        select_motive: '-- 동기 선택 --',
        select_method: '-- 수단 선택 --',
        submit_btn: '답변 제출',
        notes_title: '📝 메모',
        notes_placeholder: '추리 과정을 기록하세요...',
        case_brief_btn: '사건 개요',
        try_another: '다른 미스터리 풀기',
        correct_label: '정답',
        files_read: '파일 읽음',
        efficiency: '효율성',
        suspects: '용의자',
        evidence_files: '증거 파일',
        select_culprit: '범인을 선택하세요!',
        select_motive_warn: '동기를 선택하세요!',
        select_method_warn: '수단을 선택하세요!',
        race_mode: 'AI와 대결',
        solo_mode: '혼자 풀기',
        choose_opponent: 'AI 상대 선택:',
        start_race: '대결 시작!',
        ai_finished: 'AI가 답을 제출했습니다!',
        race_result_title: '대결 결과',
        you: '나',
        ai: 'AI',
        winner_label: '승자',
        time_label: '소요 시간',
        faster: '더 빠름',
    },
};

function t(key) {
    return i18n[state.lang]?.[key] || i18n.en[key] || key;
}

// Base path for data
const DATA_BASE = window.location.hostname.includes('github.io')
    ? '/ludus-ex-machina/deduction/scenarios'
    : './scenarios';

// ── Scenario List ──

const SCENARIOS = [
    { id: 'mystery_001', id_ko: 'mystery_001_ko' },
    { id: 'mystery_002', id_ko: 'mystery_002_ko' },
    { id: 'mystery_003', id_ko: 'mystery_003_ko' },
];

// Load pre-computed AI results
async function loadAIResults() {
    try {
        const res = await fetch(`${DATA_BASE}/../ai_results.json`);
        if (res.ok) state.aiResults = await res.json();
    } catch (e) {
        console.warn('No AI results for race mode');
    }
}

async function loadScenarioList() {
    const grid = document.getElementById('scenario-list');
    grid.innerHTML = '';

    // Update hero text
    document.querySelector('.hero-mini h1').textContent = t('hero_title');
    document.getElementById('hero-desc').textContent = t('hero_desc');

    for (const s of SCENARIOS) {
        const sid = state.lang === 'ko' && s.id_ko ? s.id_ko : s.id;
        try {
            const res = await fetch(`${DATA_BASE}/${sid}/scenario.json`);
            if (!res.ok) continue;
            const data = await res.json();

            // Check if AI results exist for this scenario (use base EN id)
            const baseId = s.id; // Always use EN id for AI results lookup
            const hasAI = state.aiResults && state.aiResults[baseId];

            const card = document.createElement('div');
            card.className = 'scenario-card';
            card.innerHTML = `
                <span class="difficulty ${data.difficulty}">${data.difficulty.toUpperCase()}</span>
                <h3>${data.title}</h3>
                <p class="desc">${data.description}</p>
                <p class="meta">${data.suspects.length} ${t('suspects')} · ${data.evidence_files.length} ${t('evidence_files')}</p>
                <div class="card-actions">
                    <button class="btn-card" onclick="startGame('${sid}')">${t('solo_mode')}</button>
                    ${hasAI ? `<button class="btn-card btn-race" onclick="showRaceSetup('${sid}', '${baseId}')">${t('race_mode')}</button>` : ''}
                </div>
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
    state.readOrder = [];
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

    // Apply i18n to game page
    document.querySelector('.evidence-panel h3').textContent = t('evidence_title');
    document.querySelector('.submit-panel h3').textContent = t('verdict_title');
    document.querySelector('.form-group label[for="culprit"]')?.textContent ||
        (document.querySelectorAll('.form-group label')[0].textContent = t('culprit_label'));
    document.querySelectorAll('.form-group label')[0].textContent = t('culprit_label');
    document.querySelectorAll('.form-group label')[1].textContent = t('motive_label');
    document.querySelectorAll('.form-group label')[2].textContent = t('method_label');
    document.getElementById('btn-submit').textContent = t('submit_btn');
    document.querySelector('.notes-section h4').textContent = t('notes_title');
    document.getElementById('notes').placeholder = t('notes_placeholder');
    document.getElementById('btn-back-to-brief').textContent = t('case_brief_btn');

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
    motiveSelect.innerHTML = `<option value="">${t('select_motive')}</option>` +
        (motiveOpts || []).map(m => `<option value="${m}">${m.replace(/_/g, ' ')}</option>`).join('');

    // Method
    const methodSelect = document.getElementById('method-select');
    const methodOpts = (isKo && scenario.method_options_ko) ? scenario.method_options_ko : scenario.method_options;
    methodSelect.innerHTML = `<option value="">${t('select_method')}</option>` +
        (methodOpts || []).map(m => `<option value="${m}">${m.replace(/_/g, ' ')}</option>`).join('');
}

async function readEvidence(filename) {
    try {
        const res = await fetch(`${DATA_BASE}/${state.scenarioId}/evidence/${filename}`);
        const content = await res.text();
        if (!state.filesRead.has(filename)) {
            state.readOrder.push(filename);
        }
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

    if (!culprit) { alert(t('select_culprit')); return; }
    if (!motive) { alert(t('select_motive_warn')); return; }
    if (!method) { alert(t('select_method_warn')); return; }

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

    document.getElementById('btn-try-another').textContent = t('try_another');

    const humanResult = {
        culprit, motive, method,
        culpritCorrect, motiveCorrect, methodCorrect,
        accuracy, efficiency, finalScore, elapsed,
        correctAnswer: answer, correctAnswerKo: answerKo,
    };

    if (state.raceMode && state.aiResult) {
        showRaceResult(humanResult);
    } else {
        showResult(humanResult);
    }
}

function showResult(r) {
    document.getElementById('game-page').style.display = 'none';
    document.getElementById('result-page').style.display = '';

    const emoji = r.accuracy === 3 ? '🎉' : r.accuracy >= 2 ? '👍' : r.accuracy >= 1 ? '🤔' : '❌';
    document.getElementById('result-title').textContent = `${emoji} ${r.accuracy}/3 ${t('correct_label')}`;

    const check = (ok) => ok ? '<span class="result-correct">✅</span>' : '<span class="result-wrong">❌</span>';

    document.getElementById('result-details').innerHTML = `
        <div class="result-row">
            <span>${t('culprit_label')}: ${r.culprit}</span>
            <span>${check(r.culpritCorrect)} (${t('correct_label')}: ${r.correctAnswer.culprit})</span>
        </div>
        <div class="result-row">
            <span>${t('motive_label')}: ${r.motive.replace(/_/g, ' ')}</span>
            <span>${check(r.motiveCorrect)} (${t('correct_label')}: ${r.correctAnswer.motive.replace(/_/g, ' ')})</span>
        </div>
        <div class="result-row">
            <span>${t('method_label')}: ${r.method.replace(/_/g, ' ')}</span>
            <span>${check(r.methodCorrect)} (${t('correct_label')}: ${r.correctAnswer.method.replace(/_/g, ' ')})</span>
        </div>
        <div class="result-score">${r.finalScore.toFixed(1)}</div>
        <div style="color: var(--text-muted); font-size: 13px;">
            ${state.filesRead.size} ${t('files_read')} · ${r.elapsed}s · ${t('efficiency')} ${(r.efficiency * 100).toFixed(0)}%
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
    localStorage.setItem('lxm_lang', lang);
    document.querySelectorAll('.lang-btn').forEach(btn =>
        btn.classList.toggle('active', btn.textContent === lang.toUpperCase())
    );
    // Reload scenario list
    if (document.getElementById('scenario-select').style.display !== 'none') {
        loadScenarioList();
    }
}

// Init lang buttons
document.querySelectorAll('.lang-btn').forEach(btn =>
    btn.classList.toggle('active', btn.textContent === state.lang.toUpperCase())
);

// ── Race Mode ──

function showRaceSetup(scenarioId, baseId) {
    const models = Object.keys(state.aiResults?.[baseId] || {});
    if (!models.length) return;

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-card">
            <h3>${t('choose_opponent')}</h3>
            <div class="model-buttons">
                ${models.map(m => `<button class="btn-model" onclick="startRace('${scenarioId}', '${baseId}', '${m}')">${m.charAt(0).toUpperCase() + m.slice(1)}</button>`).join('')}
            </div>
            <button class="btn-sm" onclick="this.closest('.modal-overlay').remove()" style="margin-top:12px">Cancel</button>
        </div>
    `;
    document.body.appendChild(modal);
}

function startRace(scenarioId, baseId, model) {
    document.querySelector('.modal-overlay')?.remove();
    state.raceMode = true;
    state.aiModel = model;
    state.aiResult = state.aiResults?.[baseId]?.[model] || null;
    startGame(scenarioId);
}

function showRaceResult(humanResult) {
    const ai = state.aiResult;
    if (!ai) return;

    const h = humanResult;
    const hScore = h.finalScore;
    const aScore = ai.final_score;
    const hCorrect = h.accuracy;
    const aCorrect = ai.accuracy;

    let winner;
    if (hCorrect > aCorrect) winner = 'human';
    else if (aCorrect > hCorrect) winner = 'ai';
    else if (hScore > aScore) winner = 'human';
    else if (aScore > hScore) winner = 'ai';
    else winner = 'tie';

    const winEmoji = winner === 'human' ? '🏆 ' + t('you') : winner === 'ai' ? '🤖 ' + state.aiModel : '🤝 Tie';
    const check = (ok) => ok ? '✅' : '❌';

    document.getElementById('result-page').style.display = '';
    document.getElementById('game-page').style.display = 'none';

    document.getElementById('result-title').textContent = `${t('race_result_title')} — ${winEmoji}`;

    document.getElementById('result-details').innerHTML = `
        <table class="race-table">
            <thead>
                <tr>
                    <th></th>
                    <th>${t('you')}</th>
                    <th>🤖 ${state.aiModel}</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>${t('culprit_label')}</td>
                    <td>${check(h.culpritCorrect)} ${h.culprit}</td>
                    <td>${check(ai.culprit_correct)} ${ai.answer?.culprit || '?'}</td>
                </tr>
                <tr>
                    <td>${t('motive_label')}</td>
                    <td>${check(h.motiveCorrect)} ${(h.motive||'').replace(/_/g,' ')}</td>
                    <td>${check(ai.motive_correct===1)} ${(ai.answer?.motive||'').replace(/_/g,' ')}</td>
                </tr>
                <tr>
                    <td>${t('method_label')}</td>
                    <td>${check(h.methodCorrect)} ${(h.method||'').replace(/_/g,' ')}</td>
                    <td>${check(ai.method_correct===1)} ${(ai.answer?.method||'').replace(/_/g,' ')}</td>
                </tr>
                <tr>
                    <td>${t('files_read')}</td>
                    <td>${state.filesRead.size}</td>
                    <td>${ai.files_read}</td>
                </tr>
                <tr>
                    <td>${t('time_label')}</td>
                    <td>${h.elapsed}s</td>
                    <td>~5s</td>
                </tr>
                <tr style="font-weight:bold">
                    <td>Score</td>
                    <td>${hScore.toFixed(1)}</td>
                    <td>${aScore.toFixed(1)}</td>
                </tr>
            </tbody>
        </table>
        <div class="race-winner">${t('winner_label')}: ${winEmoji}</div>
        <div class="race-paths">
            <div>
                <strong>${t('you')}:</strong> ${state.readOrder.map(f => f.replace('.md','')).join(' → ') || 'none'}
            </div>
            <div>
                <strong>AI:</strong> ${(ai.timeline||[]).filter(e=>e.action==='read').map(e=>e.file.replace('.md','')).join(' → ') || 'none'}
            </div>
        </div>
    `;
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
loadAIResults().then(handleRoute);
