/**
 * Conquest Board — dynamic render from data/conquest.json.
 *
 * The board is DATA now: run a match -> export the replay -> `python
 * scripts/build_conquest.py` -> the table grows a column/cell on deploy.
 * The static rows in index.html remain as a no-JS/fetch-failure fallback.
 * Bilingual: notes carry {en,ko}; re-renders on language switch (hooked from
 * applyTranslations via window.renderConquest).
 */

(function () {
    let DATA = null;

    function lang() {
        return localStorage.getItem('lxm_lang') || 'en';
    }

    function render() {
        if (!DATA) return;
        const table = document.getElementById('conquest-table');
        if (!table) return;
        const L = lang();
        const yourModel = L === 'ko' ? '당신의 모델' : 'your model';
        const worldTh = L === 'ko' ? '월드' : 'World';

        const head = ['<tr>', `<th>${worldTh}</th>`]
            .concat(DATA.models.map(m => `<th>${m.label}</th>`))
            .concat([`<th>${yourModel}</th>`, '</tr>']).join('');

        const rows = DATA.worlds.map(w => {
            const cells = DATA.models.map(m => {
                const a = w.attempts[m.key];
                if (!a) return '<td class="cell-draw">—</td>';
                const cls = a.outcome === 'solved' ? 'cell-win' : 'cell-lose';
                const note = (a.note && a.note[L]) || (a.note && a.note.en) || a.outcome;
                return `<td class="${cls}"><a href="./viewer/#/match/${a.match_id}" ` +
                       `style="color:inherit;text-decoration:none">${note}</a></td>`;
            }).join('');
            return `<tr><td class="model-name">${w.name[L] || w.name.en}</td>${cells}` +
                   `<td class="cell-draw">—</td></tr>`;
        }).join('');

        table.querySelector('thead').innerHTML = head;
        table.querySelector('tbody').innerHTML = rows;

        // Creature lane — organ-augmented plane runs, kept apart from the
        // bare-model board (different category; config disclosed per entry).
        const lane = document.getElementById('conquest-creatures');
        if (lane && DATA.creatures && DATA.creatures.length) {
            const title = L === 'ko' ? '크리처 레인 — 플레인 검증 런 (organ 구성 공개)' :
                'Creature lane — plane-verified runs (organ configs disclosed)';
            const items = DATA.creatures.map(c => {
                const w = DATA.worlds.find(x => x.id === c.world);
                const wname = w ? (w.name[L] || w.name.en) : c.world;
                const note = (c.note && c.note[L]) || (c.note && c.note.en) || '';
                return `<li><strong>${c.name}</strong> · ${wname} — ${note}</li>`;
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
