/**
 * Conquest Board — dynamic render from data/conquest.json.
 *
 * The board is DATA: run a match -> export the replay -> `python
 * scripts/build_conquest.py` -> the board grows a column/cell on deploy.
 * The static rows in index.html remain as a no-JS/fetch-failure fallback.
 *
 * 13 models no longer fit one table at a glance, so the board is a
 * LINEAGE CAROUSEL (2026-07-21): one slide per training lineage, rotating
 * right on a timer (paused on hover / hidden tab / reduced-motion), with
 * dots + arrows for manual control. Slide index survives language
 * re-render (hooked from applyTranslations via window.renderConquest).
 */

(function () {
    let DATA = null;
    let slide = 0;
    let timer = null;

    const GROUPS = [
        { id: 'anthropic', match: k => k.startsWith('claude:'),
          label: { en: 'Anthropic · Claude', ko: 'Anthropic · Claude' } },
        { id: 'openai', match: k => k.startsWith('codex:'),
          label: { en: 'OpenAI · GPT', ko: 'OpenAI · GPT' } },
        { id: 'challengers', match: k => k.startsWith('gemini:') || k.startsWith('grok:'),
          label: { en: 'Google + xAI', ko: 'Google + xAI' } },
    ];
    const ROTATE_MS = 7000;

    function lang() {
        return localStorage.getItem('lxm_lang') || 'en';
    }

    const CREST = { claude: 'crest_claude', codex: 'crest_openai',
                    gemini: 'crest_google', ollama: 'crest_ollama' };
    function crestImg(key) {
        const c = CREST[key.split(':')[0]];
        return c ? `<img src="./viewer/assets/identity/${c}.webp" alt="" ` +
                   `style="width:20px;height:20px;vertical-align:-5px;margin-right:6px;border-radius:4px">` : '';
    }

    function slideTable(models, L) {
        const worldTh = L === 'ko' ? '월드' : 'World';
        const head = ['<tr>', `<th>${worldTh}</th>`]
            .concat(models.map(m =>
                `<th style="white-space:nowrap">${crestImg(m.key)}${m.label}</th>`))
            .concat(['</tr>']).join('');
        const rows = DATA.worlds.map(w => {
            const cells = models.map(m => {
                const a = w.attempts[m.key];
                if (!a) return '<td class="cell-draw">—</td>';
                const cls = a.outcome === 'solved' ? 'cell-win' : 'cell-lose';
                const note = (a.note && a.note[L]) || (a.note && a.note.en) || a.outcome;
                if (!a.match_id) return `<td class="${cls}">${note}</td>`;  // owner-judged, no replay
                return `<td class="${cls}"><a href="./viewer/#/match/${a.match_id}" ` +
                       `style="color:inherit;text-decoration:none">${note}</a></td>`;
            }).join('');
            return `<tr><td class="model-name">${w.name[L] || w.name.en}</td>${cells}</tr>`;
        }).join('');
        return `<div class="results-table-wrap"><table class="results-table">` +
               `<thead>${head}</thead><tbody>${rows}</tbody></table></div>`;
    }

    function stopTimer() { if (timer) { clearInterval(timer); timer = null; } }

    function startTimer() {
        stopTimer();
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        timer = setInterval(() => {
            if (document.hidden) return;
            slide = (slide + 1) % GROUPS.length;
            move();
        }, ROTATE_MS);
    }

    function move() {
        const track = document.getElementById('conquest-track');
        if (track) track.style.transform = `translateX(-${slide * 100}%)`;
        GROUPS.forEach((g, i) => {
            const dot = document.getElementById(`conquest-dot-${i}`);
            if (dot) dot.classList.toggle('active', i === slide);
        });
        const cap = document.getElementById('conquest-caption');
        if (cap) cap.textContent =
            `${GROUPS[slide].label[lang()] || GROUPS[slide].label.en} (${slide + 1}/${GROUPS.length})`;
    }

    function render() {
        if (!DATA) return;
        const host = document.getElementById('conquest-board') ||
                     (function () {
                         // adopt the static fallback's wrap as the carousel host
                         const t = document.getElementById('conquest-table');
                         if (!t) return null;
                         const wrap = t.closest('.results-table-wrap') || t.parentElement;
                         const div = document.createElement('div');
                         div.id = 'conquest-board';
                         wrap.replaceWith(div);
                         return div;
                     })();
        if (!host) return;
        const L = lang();

        const grouped = GROUPS.map(g => DATA.models.filter(m => g.match(m.key)));
        const slides = grouped.map(models =>
            `<div class="conquest-slide">${slideTable(models, L)}</div>`).join('');
        const dots = GROUPS.map((g, i) =>
            `<button class="conquest-dot" id="conquest-dot-${i}" aria-label="${g.label.en}"></button>`).join('');

        host.innerHTML =
            `<div class="conquest-topbar">` +
            `<span class="conquest-caption" id="conquest-caption"></span>` +
            `<span class="conquest-ctrls">` +
            `<button class="conquest-arrow" id="conquest-prev" aria-label="previous">‹</button>` +
            `${dots}` +
            `<button class="conquest-arrow" id="conquest-next" aria-label="next">›</button>` +
            `</span></div>` +
            `<div class="conquest-carousel"><div class="conquest-track" id="conquest-track">${slides}</div></div>`;

        document.getElementById('conquest-prev').onclick = () => {
            slide = (slide - 1 + GROUPS.length) % GROUPS.length; move(); startTimer();
        };
        document.getElementById('conquest-next').onclick = () => {
            slide = (slide + 1) % GROUPS.length; move(); startTimer();
        };
        GROUPS.forEach((g, i) => {
            document.getElementById(`conquest-dot-${i}`).onclick = () => {
                slide = i; move(); startTimer();
            };
        });
        const car = host.querySelector('.conquest-carousel');
        car.addEventListener('mouseenter', stopTimer);
        car.addEventListener('mouseleave', startTimer);

        move();
        startTimer();

        // Creature lane — organ-augmented plane runs, kept apart from the
        // bare-model board (different category; config disclosed per entry).
        const lane = document.getElementById('conquest-creatures');
        if (lane && DATA.creatures && DATA.creatures.length) {
            const title = L === 'ko' ? '크리처 레인 — 플레인 검증 런 (organ 구성 공개)' :
                'Creature lane — plane-verified runs (organ configs disclosed)';
            const AVATAR = { Nimbus: 'avatar_nimbus', Kiln: 'avatar_kiln' };
            const items = DATA.creatures.map(c => {
                const w = DATA.worlds.find(x => x.id === c.world);
                const wname = w ? (w.name[L] || w.name.en) : c.world;
                const note = (c.note && c.note[L]) || (c.note && c.note.en) || '';
                const av = AVATAR[c.name]
                    ? `<img src="./viewer/assets/identity/${AVATAR[c.name]}.webp" alt="" ` +
                      `style="width:26px;height:26px;border-radius:50%;vertical-align:-8px;` +
                      `margin-right:7px;border:1px solid rgba(216,198,144,.4)">`
                    : `<img src="./viewer/assets/identity/crest_creature.webp" alt="" ` +
                      `style="width:22px;height:22px;border-radius:4px;vertical-align:-6px;margin-right:7px">`;
                return `<li style="margin-top:6px;list-style:none">${av}<strong>${c.name}</strong> · ${wname} — ${note}</li>`;
            }).join('');
            lane.innerHTML = `<p class="conquest-creature-title">${title}</p><ul>${items}</ul>`;
        }
    }

    window.renderConquest = render;

    fetch('./data/conquest.json')
        .then(r => (r.ok ? r.json() : null))
        .then(d => { if (d && d.worlds) { DATA = d; render(); } })
        .catch(() => { /* static fallback rows remain */ });
})();
