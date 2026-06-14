/* Deduction Scenario Creator — Outline Builder */

const ARCHETYPES = [
    {
        id: 'classic_whodunit',
        name: 'Classic Whodunit',
        icon: '\u{1F50D}',
        desc: 'Closed circle of suspects with alibis — find the contradiction to identify the culprit.',
        emphasis: 'WHO did it',
        mechanic: 'Alibi contradiction & logical elimination',
        hintField: 'key_contradiction',
        hintLabel: 'Key Contradiction *',
        hintPlaceholder: 'e.g. C claims he left at 11:15 but CCTV shows corridor empty at that time',
    },
    {
        id: 'forensic_puzzle',
        name: 'Forensic Puzzle',
        icon: '\u{1F9EA}',
        desc: 'Physical and scientific evidence tells the story — reconstruct the causal chain.',
        emphasis: 'HOW it was done',
        mechanic: 'Causal chain reasoning',
        hintField: 'causal_chain',
        hintLabel: 'Causal Chain *',
        hintPlaceholder: 'e.g. Swapped label \u2192 wrong chemical mixed \u2192 toxic gas \u2192 ventilation off \u2192 lethal exposure',
    },
    {
        id: 'impossible_crime',
        name: 'Impossible Crime',
        icon: '\u{1F510}',
        desc: 'The crime cannot have happened the way it appears — find the trick mechanism.',
        emphasis: 'HOW was it possible',
        mechanic: 'Locked room / trick deduction',
        hintField: 'trick_mechanism',
        hintLabel: 'Trick Mechanism *',
        hintPlaceholder: 'e.g. Entered through shared ventilation duct, relocked deadbolt using string through mail slot',
    },
    {
        id: 'paper_trail',
        name: 'Paper Trail',
        icon: '\u{1F4CA}',
        desc: 'The truth is buried in records and transactions — spot the numerical anomaly.',
        emphasis: 'Follow the money',
        mechanic: 'Numerical anomaly detection',
        hintField: 'numerical_anomaly',
        hintLabel: 'Numerical Anomaly *',
        hintPlaceholder: 'e.g. All phantom invoices are round numbers, all approved on Fridays when CFO is away',
    },
    {
        id: 'digital_forensics',
        name: 'Digital Forensics',
        icon: '\u{1F4BB}',
        desc: 'Reconstruct activity from logs, metadata, and digital artifacts.',
        emphasis: 'Build the timeline',
        mechanic: 'Timestamp & metadata analysis',
        hintField: 'timeline_key',
        hintLabel: 'Timeline Key *',
        hintPlaceholder: 'e.g. VPN log shows 3AM login from home IP, but suspect claimed laptop was stolen that week',
    },
    {
        id: 'psychological_inverted',
        name: 'Psychological',
        icon: '\u{1F9E0}',
        desc: 'You may suspect early — prove it by understanding their behavioral pattern.',
        emphasis: 'WHY they did it',
        mechanic: 'Behavioral profiling',
        hintField: 'behavioral_key',
        hintLabel: 'Behavioral Key *',
        hintPlaceholder: 'e.g. Only suspect who never asks about investigation progress; provides too much detail unprompted',
    },
];

const SUSPECT_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];

let state = {
    archetype: null,
    culprit: null,
    suspects: [],  // [{letter, name}]
};

// --- Init ---
function init() {
    renderArchetypeGrid();
    addDefaultSuspects();
    renderSuspects();

    document.getElementById('btn-add-suspect').addEventListener('click', addSuspect);
    document.getElementById('btn-back-archetype').addEventListener('click', () => showStep('step-archetype'));
    document.getElementById('btn-back-outline').addEventListener('click', () => showStep('step-outline'));
    document.getElementById('btn-preview').addEventListener('click', handlePreview);
    document.getElementById('btn-download').addEventListener('click', handleDownload);
}

// --- Step Navigation ---
function showStep(stepId) {
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
    document.getElementById(stepId).classList.add('active');
    window.scrollTo(0, 0);
}

// --- Archetype Grid ---
function renderArchetypeGrid() {
    const grid = document.getElementById('archetype-grid');
    grid.innerHTML = ARCHETYPES.map(a => `
        <div class="archetype-card" data-id="${a.id}">
            <div class="archetype-icon">${a.icon}</div>
            <h3>${a.name}</h3>
            <div class="desc">${a.desc}</div>
            <div class="emphasis">${a.emphasis}</div>
            <div class="mechanic">${a.mechanic}</div>
        </div>
    `).join('');

    grid.querySelectorAll('.archetype-card').forEach(card => {
        card.addEventListener('click', () => selectArchetype(card.dataset.id));
    });
}

function selectArchetype(id) {
    state.archetype = ARCHETYPES.find(a => a.id === id);

    // Update visual selection
    document.querySelectorAll('.archetype-card').forEach(c => c.classList.remove('selected'));
    document.querySelector(`[data-id="${id}"]`).classList.add('selected');

    // Setup archetype-specific hint field
    const hintField = document.getElementById('field-archetype-hint');
    const hintLabel = document.getElementById('label-archetype-hint');
    const hintInput = document.getElementById('f-archetype-hint');

    hintField.style.display = 'block';
    hintLabel.textContent = state.archetype.hintLabel;
    hintInput.placeholder = state.archetype.hintPlaceholder;
    hintInput.value = '';

    // Update subtitle
    document.getElementById('archetype-subtitle').textContent =
        `${state.archetype.name} — ${state.archetype.mechanic}`;

    // Go to step 2
    setTimeout(() => showStep('step-outline'), 200);
}

// --- Suspects ---
function addDefaultSuspects() {
    state.suspects = [
        { letter: 'A', name: '' },
        { letter: 'B', name: '' },
        { letter: 'C', name: '' },
        { letter: 'D', name: '' },
    ];
}

function addSuspect() {
    if (state.suspects.length >= 6) return;
    const next = SUSPECT_LETTERS[state.suspects.length];
    state.suspects.push({ letter: next, name: '' });
    renderSuspects();
}

function removeSuspect(letter) {
    if (state.suspects.length <= 4) return;
    state.suspects = state.suspects.filter(s => s.letter !== letter);
    if (state.culprit === letter) state.culprit = null;
    // Re-letter
    state.suspects.forEach((s, i) => s.letter = SUSPECT_LETTERS[i]);
    renderSuspects();
}

function setCulprit(letter) {
    state.culprit = letter;
    renderSuspects();
}

function renderSuspects() {
    const list = document.getElementById('suspect-list');
    list.innerHTML = state.suspects.map(s => `
        <div class="suspect-row ${s.letter === state.culprit ? 'is-culprit' : ''}">
            <span class="suspect-letter">${s.letter}</span>
            <input class="suspect-name-input" type="text"
                   data-letter="${s.letter}"
                   value="${s.name}"
                   placeholder="Name (Role), e.g. Dr. Kim Junghyun (Lab Director)">
            <button class="btn-culprit ${s.letter === state.culprit ? 'active' : ''}"
                    onclick="setCulprit('${s.letter}')" title="Set as culprit">&#9733;</button>
            ${state.suspects.length > 4 ?
                `<button class="btn-remove-suspect" onclick="removeSuspect('${s.letter}')" title="Remove">&times;</button>` :
                ''}
        </div>
    `).join('');

    // Bind name inputs
    list.querySelectorAll('.suspect-name-input').forEach(input => {
        input.addEventListener('input', (e) => {
            const s = state.suspects.find(s => s.letter === e.target.dataset.letter);
            if (s) s.name = e.target.value;
        });
    });

    // Update count
    document.getElementById('suspect-count').textContent =
        `${state.suspects.length}/${SUSPECT_LETTERS.length}`;

    // Hide add button if max
    document.getElementById('btn-add-suspect').style.display =
        state.suspects.length >= 6 ? 'none' : 'block';
}

// --- Validation ---
function validate() {
    const errors = [];

    if (!state.archetype) errors.push('Select an archetype first');
    if (!val('f-title')) errors.push('Title is required');
    if (!val('f-incident')) errors.push('Incident description is required');
    if (!val('f-motive')) errors.push('Motive hint is required');
    if (!val('f-method')) errors.push('Method hint is required');
    if (!state.culprit) errors.push('Select a culprit (click the star)');

    const emptyNames = state.suspects.filter(s => !s.name.trim());
    if (emptyNames.length > 0) {
        errors.push(`Suspect ${emptyNames.map(s => s.letter).join(', ')}: name is required`);
    }

    // Archetype-specific hint
    if (state.archetype) {
        const hintVal = val('f-archetype-hint');
        if (!hintVal) {
            errors.push(`${state.archetype.hintLabel.replace(' *', '')} is required for ${state.archetype.name}`);
        }
    }

    return errors;
}

function val(id) {
    return document.getElementById(id).value.trim();
}

// --- Preview ---
function handlePreview() {
    const errors = validate();
    const msgEl = document.getElementById('validation-messages');

    if (errors.length > 0) {
        msgEl.innerHTML = errors.map(e => `<div class="val-error">\u2717 ${e}</div>`).join('');
        return;
    }
    msgEl.innerHTML = '';

    const outline = buildOutline();
    document.getElementById('preview-json').textContent = JSON.stringify(outline, null, 2);
    document.getElementById('preview-command').textContent =
        `python -m lxm.tools.generate_scenario outline.json`;

    showStep('step-preview');
}

function buildOutline() {
    const outline = {
        archetype: state.archetype.id,
        title: val('f-title'),
        difficulty: document.getElementById('f-difficulty').value,
        culprit: state.culprit,
        suspects: {},
        incident: val('f-incident'),
        motive_hint: val('f-motive'),
        method_hint: val('f-method'),
    };

    // Setting (optional)
    const setting = val('f-setting');
    if (setting) outline.setting = setting;

    // Suspects
    state.suspects.forEach(s => {
        outline.suspects[s.letter] = s.name;
    });

    // Archetype-specific hint
    const hintVal = val('f-archetype-hint');
    if (hintVal && state.archetype) {
        outline[state.archetype.hintField] = hintVal;
    }

    // Extra constraints (optional)
    const extra = val('f-extra');
    if (extra) outline.extra_constraints = extra;

    return outline;
}

// --- Download ---
function handleDownload() {
    const outline = buildOutline();
    const blob = new Blob([JSON.stringify(outline, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `outline_${state.archetype.id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// --- Go ---
init();
