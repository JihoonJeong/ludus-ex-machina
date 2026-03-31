/**
 * LxM Deduction — Solo Mode + AI Comparison (Gen 2)
 * Pure client-side. Loads scenarios from static JSON.
 */

const state = {
    lang: localStorage.getItem('lxm_lang') || 'en',
    scenario: null,
    scenarioId: null,
    scenarioBaseId: null,
    filesRead: new Set(),
    readOrder: [],
    selectedCulprit: null,
    startTime: null,
    submitted: false,
    aiResults: null,
};

const i18n = {
    en: {
        hero_title: 'Mystery Solver',
        hero_desc: 'Choose a mystery to solve. Read the evidence, identify the culprit, motive, and method.',
        evidence_title: 'Evidence',
        verdict_title: 'Your Verdict',
        culprit_label: 'Culprit',
        motive_label: 'Motive',
        method_label: 'Method',
        select_motive: '-- Select motive --',
        select_method: '-- Select method --',
        submit_btn: 'Submit Answer',
        notes_title: 'Your Notes',
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
        solo_mode: 'Solve',
        ai_results_btn: 'AI Results',
        ai_comparison_title: 'How AI models solved this',
        model_col: 'Model',
        culprit_pct_col: 'Culprit %',
        files_avg_col: 'Avg Files',
        trap_col: 'Red Herring Trap',
        you_level: 'You performed at the level of',
        sdi_context: 'SDI {sdi} ({grade}) — {pct}% of AI models found the culprit',
        try_another: 'Try Another Mystery',
        cloud_header: 'Cloud AI',
        slm_header: 'SLM (Local, Free)',
        tier_col: 'Tier',
        difficulty_inversion: 'Difficulty Inversion!',
        failure_insight_title: 'Why do Cloud and SLM fail differently?',
        failure_cloud: 'Cloud AI: Reads evidence but falls for red herrings (Reasoning Failure)',
        failure_slm: 'SLM: Doesn\'t read enough evidence to even encounter red herrings (Engagement Failure)',
    },
    ko: {
        hero_title: '\ubbf8\uc2a4\ud130\ub9ac \uc194\ubc84',
        hero_desc: '\ubbf8\uc2a4\ud130\ub9ac\ub97c \uc120\ud0dd\ud558\uc138\uc694. \uc99d\uac70\ub97c \uc77d\uace0 \ubc94\uc778, \ub3d9\uae30, \uc218\ub2e8\uc744 \ubc1d\ud788\uc138\uc694.',
        evidence_title: '\uc99d\uac70 \ud30c\uc77c',
        verdict_title: '\ud310\uacb0',
        culprit_label: '\ubc94\uc778',
        motive_label: '\ub3d9\uae30',
        method_label: '\uc218\ub2e8',
        select_motive: '-- \ub3d9\uae30 \uc120\ud0dd --',
        select_method: '-- \uc218\ub2e8 \uc120\ud0dd --',
        submit_btn: '\ub2f5\ubcc0 \uc81c\ucd9c',
        notes_title: '\uba54\ubaa8',
        notes_placeholder: '\ucd94\ub9ac \uacfc\uc815\uc744 \uae30\ub85d\ud558\uc138\uc694...',
        case_brief_btn: '\uc0ac\uac74 \uac1c\uc694',
        try_another: '\ub2e4\ub978 \ubbf8\uc2a4\ud130\ub9ac \ud480\uae30',
        correct_label: '\uc815\ub2f5',
        files_read: '\ud30c\uc77c \uc77d\uc74c',
        efficiency: '\ud6a8\uc728\uc131',
        suspects: '\uc6a9\uc758\uc790',
        evidence_files: '\uc99d\uac70 \ud30c\uc77c',
        select_culprit: '\ubc94\uc778\uc744 \uc120\ud0dd\ud558\uc138\uc694!',
        select_motive_warn: '\ub3d9\uae30\ub97c \uc120\ud0dd\ud558\uc138\uc694!',
        select_method_warn: '\uc218\ub2e8\uc744 \uc120\ud0dd\ud558\uc138\uc694!',
        solo_mode: '\ud480\uae30',
        ai_results_btn: 'AI \uacb0\uacfc',
        ai_comparison_title: 'AI \ubaa8\ub378\uc740 \uc774\ub807\uac8c \ud480\uc5c8\uc2b5\ub2c8\ub2e4',
        model_col: '\ubaa8\ub378',
        culprit_pct_col: '\ubc94\uc778 \uc815\ub2f5\ub960',
        files_avg_col: '\ud3c9\uade0 \uc99d\uac70 \uc218',
        trap_col: '\ub808\ub4dc\ud5e4\ub9c1 \ud568\uc815',
        you_level: '\ub2f9\uc2e0\uc740 \ub2e4\uc74c \uc218\uc900\uc785\ub2c8\ub2e4',
        sdi_context: 'SDI {sdi} ({grade}) \u2014 AI \ubaa8\ub378\uc758 {pct}%\uac00 \ubc94\uc778\uc744 \ub9de\uacbc\uc2b5\ub2c8\ub2e4',
        try_another: '\ub2e4\ub978 \ubbf8\uc2a4\ud130\ub9ac \ud480\uae30',
        cloud_header: 'Cloud AI',
        slm_header: 'SLM (\ub85c\uceec, \ubb34\ub8cc)',
        tier_col: '\ud2f0\uc5b4',
        difficulty_inversion: '\ub09c\uc774\ub3c4 \uc5ed\uc804!',
        failure_insight_title: 'Cloud\uc640 SLM\uc740 \uc65c \ub2e4\ub974\uac8c \uc2e4\ud328\ud560\uae4c?',
        failure_cloud: 'Cloud AI: \uc99d\uac70\ub97c \uc77d\uc9c0\ub9cc \ub808\ub4dc\ud5e4\ub9c1\uc5d0 \uc18d\uc74c (Reasoning Failure)',
        failure_slm: 'SLM: \uc99d\uac70\ub97c \ucda9\ubd84\ud788 \uc77d\uc9c0 \uc54a\uc544 \ud568\uc815\uc5d0 \ub178\ucd9c\ub3c4 \uc548 \ub428 (Engagement Failure)',
    },
};

function t(key) {
    return i18n[state.lang]?.[key] || i18n.en[key] || key;
}

// Base path for data
const DATA_BASE = window.location.hostname.includes('github.io')
    ? '/ludus-ex-machina/deduction/scenarios'
    : './scenarios';

const AI_RESULTS_PATH = window.location.hostname.includes('github.io')
    ? '/ludus-ex-machina/deduction/ai_results.json'
    : './ai_results.json';

// -- Scenario List --

const SCENARIOS = [
    { id: 'mystery_005', id_ko: 'mystery_005_ko' },
    { id: 'mystery_006', id_ko: 'mystery_006_ko' },
    { id: 'mystery_007', id_ko: 'mystery_007_ko' },
];

// Load AI results
async function loadAIResults() {
    try {
        const res = await fetch(AI_RESULTS_PATH);
        if (res.ok) state.aiResults = await res.json();
    } catch (e) {
        console.warn('No AI results available');
    }
}

function getScenarioAIData(baseId) {
    return state.aiResults?.scenarios?.[baseId] || null;
}

function renderStars(count, max) {
    return '\u2605'.repeat(count) + '\u2606'.repeat(max - count);
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

            const baseId = s.id;
            const aiData = getScenarioAIData(baseId);
            const sdiHtml = aiData ? `
                <div class="sdi-badge">
                    <span class="sdi-stars">${renderStars(aiData.stars, 4)}</span>
                    <span class="sdi-number">SDI ${aiData.sdi.toFixed(2)}</span>
                    <span class="sdi-grade ${aiData.grade.toLowerCase()}">${aiData.grade}</span>
                </div>
            ` : '';

            const card = document.createElement('div');
            card.className = 'scenario-card';
            card.innerHTML = `
                <span class="difficulty ${data.difficulty}">${data.difficulty.toUpperCase()}</span>
                ${sdiHtml}
                <h3>${data.title}</h3>
                <p class="desc">${data.description}</p>
                <p class="meta">${data.suspects.length} ${t('suspects')} \u00b7 ${data.evidence_files.length} ${t('evidence_files')}</p>
                <div class="card-actions">
                    <button class="btn-card btn-solve" onclick="startGame('${sid}', '${baseId}')">${t('solo_mode')}</button>
                    ${aiData ? `<button class="btn-card btn-ai-results" onclick="showAIResultsModal('${baseId}')">${t('ai_results_btn')}</button>` : ''}
                </div>
            `;
            grid.appendChild(card);
        } catch (e) {
            console.warn(`Failed to load ${sid}:`, e);
        }
    }
}

// -- AI Results Modal --

function showAIResultsModal(baseId) {
    const aiData = getScenarioAIData(baseId);
    if (!aiData) return;

    const names = state.aiResults?.model_display_names || {};
    const models = aiData.models;

    const cloudModels = Object.entries(models).filter(([, m]) => m.tier === 'cloud');
    const slmModels = Object.entries(models).filter(([, m]) => m.tier === 'slm');
    const cloudAvgPct = cloudModels.length > 0
        ? Math.round(cloudModels.reduce((s, [, m]) => s + m.culprit_pct, 0) / cloudModels.length)
        : 0;

    let rows = `<tr class="tier-header"><td colspan="4">Cloud AI</td></tr>`;
    for (const [key, m] of cloudModels) {
        rows += `
            <tr class="ai-row">
                <td>${names[key] || key}</td>
                <td>${m.culprit_pct}%</td>
                <td>${m.files_avg}</td>
                <td>${m.red_herring_trapped}</td>
            </tr>
        `;
    }
    if (slmModels.length > 0) {
        rows += `<tr class="tier-header slm-header"><td colspan="4">SLM (Local, Free)</td></tr>`;
        for (const [key, m] of slmModels) {
            const isInversion = m.culprit_pct > cloudAvgPct && cloudAvgPct < 50;
            rows += `
                <tr class="ai-row ${isInversion ? 'difficulty-inversion' : ''}">
                    <td>${names[key] || key}${isInversion ? ' \u26a1' : ''}</td>
                    <td>${m.culprit_pct}%${isInversion ? ' <span class="inversion-badge">Inversion!</span>' : ''}</td>
                    <td>${m.files_avg}</td>
                    <td>${m.red_herring_trapped}${m.note ? ` <span class="model-note">${m.note}</span>` : ''}</td>
                </tr>
            `;
        }
    }

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
    modal.innerHTML = `
        <div class="modal-card ai-results-modal">
            <h3>${aiData.title} — AI Results</h3>
            <div class="sdi-context">
                SDI ${aiData.sdi.toFixed(2)} (${aiData.grade}) ${renderStars(aiData.stars, 4)}
            </div>
            <table class="ai-comparison">
                <thead>
                    <tr>
                        <th>${t('model_col')}</th>
                        <th>${t('culprit_pct_col')}</th>
                        <th>${t('files_avg_col')}</th>
                        <th>${t('trap_col')}</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
            <button class="btn-sm" onclick="this.closest('.modal-overlay').remove()" style="margin-top:12px">Close</button>
        </div>
    `;
    document.body.appendChild(modal);
}

// -- Game --

async function startGame(scenarioId, baseId) {
    const res = await fetch(`${DATA_BASE}/${scenarioId}/scenario.json`);
    state.scenario = await res.json();
    state.scenarioId = scenarioId;
    state.scenarioBaseId = baseId || scenarioId.replace(/_ko$/, '');
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

    const motiveSelect = document.getElementById('motive-select');
    const motiveOpts = (isKo && scenario.motive_options_ko) ? scenario.motive_options_ko : scenario.motive_options;
    motiveSelect.innerHTML = `<option value="">${t('select_motive')}</option>` +
        (motiveOpts || []).map(m => `<option value="${m}">${m.replace(/_/g, ' ')}</option>`).join('');

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

        document.getElementById('current-file').textContent = filename;
        document.getElementById('content-body').innerHTML = markdownToHtml(content);

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
        `${state.filesRead.size}/${total} ${t('files_read')}`;
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

    const emoji = r.accuracy === 3 ? '\ud83c\udf89' : r.accuracy >= 2 ? '\ud83d\udc4d' : r.accuracy >= 1 ? '\ud83e\udd14' : '\u274c';
    document.getElementById('result-title').textContent = `${emoji} ${r.accuracy}/3 ${t('correct_label')}`;
    document.getElementById('btn-try-another').textContent = t('try_another');

    const check = (ok) => ok ? '<span class="result-correct">\u2705</span>' : '<span class="result-wrong">\u274c</span>';

    // Basic result
    let html = `
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
            ${state.filesRead.size} ${t('files_read')} \u00b7 ${r.elapsed}s \u00b7 ${t('efficiency')} ${(r.efficiency * 100).toFixed(0)}%
        </div>
    `;

    // AI Comparison
    const baseId = state.scenarioBaseId;
    const aiData = getScenarioAIData(baseId);

    if (aiData) {
        const names = state.aiResults?.model_display_names || {};
        const models = aiData.models;
        const userCulpritPct = r.culpritCorrect ? 100 : 0;

        // Calculate overall AI culprit success rate
        let totalModels = Object.keys(models).length;
        let modelsCorrect = 0;
        for (const m of Object.values(models)) {
            if (m.culprit_pct >= 50) modelsCorrect++;
        }
        const aiSuccessPct = Math.round((modelsCorrect / totalModels) * 100);

        // Find nearest model
        let nearestModel = null;
        let nearestDiff = Infinity;
        for (const [key, m] of Object.entries(models)) {
            const diff = Math.abs(m.culprit_pct - userCulpritPct);
            if (diff < nearestDiff) {
                nearestDiff = diff;
                nearestModel = key;
            }
        }

        // SDI context
        const sdiText = t('sdi_context')
            .replace('{sdi}', aiData.sdi.toFixed(2))
            .replace('{grade}', aiData.grade)
            .replace('{pct}', aiSuccessPct);

        html += `
            <div class="sdi-context result-sdi">${sdiText}</div>
            <h3 class="ai-comparison-title">${t('ai_comparison_title')}</h3>
            <table class="ai-comparison">
                <thead>
                    <tr>
                        <th>${t('model_col')}</th>
                        <th>${t('culprit_pct_col')}</th>
                        <th>${t('files_avg_col')}</th>
                        <th>${t('trap_col')}</th>
                    </tr>
                </thead>
                <tbody>
        `;

        // Separate cloud and SLM models
        const cloudModels = Object.entries(models).filter(([, m]) => m.tier === 'cloud');
        const slmModels = Object.entries(models).filter(([, m]) => m.tier === 'slm');

        // Calculate cloud average culprit_pct for inversion detection
        const cloudAvgPct = cloudModels.length > 0
            ? Math.round(cloudModels.reduce((s, [, m]) => s + m.culprit_pct, 0) / cloudModels.length)
            : 0;

        // Cloud section
        html += `<tr class="tier-header"><td colspan="4">${t('cloud_header')}</td></tr>`;
        for (const [key, m] of cloudModels) {
            const isNearest = key === nearestModel;
            html += `
                <tr class="ai-row ${isNearest ? 'nearest-model' : ''}">
                    <td>${names[key] || key}${isNearest ? ' \u2190' : ''}</td>
                    <td>${m.culprit_pct}%</td>
                    <td>${m.files_avg}</td>
                    <td>${m.red_herring_trapped}</td>
                </tr>
            `;
        }

        // SLM section
        if (slmModels.length > 0) {
            html += `<tr class="tier-header slm-header"><td colspan="4">${t('slm_header')}</td></tr>`;
            for (const [key, m] of slmModels) {
                const isNearest = key === nearestModel;
                const isInversion = m.culprit_pct > cloudAvgPct && cloudAvgPct < 50;
                html += `
                    <tr class="ai-row ${isNearest ? 'nearest-model' : ''} ${isInversion ? 'difficulty-inversion' : ''}">
                        <td>${names[key] || key}${isNearest ? ' \u2190' : ''}${isInversion ? ' \u26a1' : ''}</td>
                        <td>${m.culprit_pct}%${isInversion ? ` <span class="inversion-badge">${t('difficulty_inversion')}</span>` : ''}</td>
                        <td>${m.files_avg}</td>
                        <td>${m.red_herring_trapped}</td>
                    </tr>
                `;
            }
        }

        html += `
                </tbody>
            </table>
        `;

        if (nearestModel) {
            html += `<div class="nearest-label">${t('you_level')} <strong>${names[nearestModel] || nearestModel}</strong></div>`;
        }

        // Failure modes insight
        const failureModes = state.aiResults?.failure_modes;
        if (failureModes) {
            html += `
                <div class="failure-insight">
                    <h4>${t('failure_insight_title')}</h4>
                    <p class="failure-cloud">${t('failure_cloud')}</p>
                    <p class="failure-slm">${t('failure_slm')}</p>
                </div>
            `;
        }
    }

    document.getElementById('result-details').innerHTML = html;
}

// -- Markdown (simple) --

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
        .replace(/^- (.+)$/gm, '\u2022 $1')
        .replace(/\n/g, '<br>');
}

// -- i18n --

function setLang(lang) {
    state.lang = lang;
    localStorage.setItem('lxm_lang', lang);
    document.querySelectorAll('.lang-btn').forEach(btn =>
        btn.classList.toggle('active', btn.textContent === lang.toUpperCase())
    );
    if (document.getElementById('scenario-select').style.display !== 'none') {
        loadScenarioList();
    }
}

// Init lang buttons
document.querySelectorAll('.lang-btn').forEach(btn =>
    btn.classList.toggle('active', btn.textContent === state.lang.toUpperCase())
);

// -- Routing --

function handleRoute() {
    const hash = location.hash.slice(1);
    if (hash && hash.startsWith('/')) {
        const sid = hash.slice(1);
        // Determine baseId from sid
        const baseId = sid.replace(/_ko$/, '');
        startGame(sid, baseId);
    } else {
        document.getElementById('scenario-select').style.display = '';
        document.getElementById('game-page').style.display = 'none';
        document.getElementById('result-page').style.display = 'none';
        loadScenarioList();
    }
}

window.addEventListener('hashchange', handleRoute);
loadAIResults().then(handleRoute);
