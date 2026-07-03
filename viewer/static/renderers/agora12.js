/**
 * Agora-12 renderer for the LxM Match Viewer.
 *
 * Social-survival field: five spaces (market / plaza / three alleys), N agents
 * with energy + influence, market pool, seeded crises. Per-turn state comes
 * from `post_move_state` (= engine `current`): agents / messages / billboard /
 * crisis / round / last_events.
 *
 * Layout: the original agora map art (assets/agora12/map.webp) sits behind a
 * dark overlay; five location panels show who's where (agent chips with energy
 * bars + influence), what was said this round, and a fallen strip + event log.
 */

(function () {
    const C = {
        bg: '#0b0e14', panel: 'rgba(17, 22, 34, 0.82)', border: '#2c3550',
        text: '#dfe4f2', muted: '#8a92b0', teal: '#39c6c0', amber: '#e8a33d',
        gold: '#d8c690', red: '#e2768c', green: '#4ade80',
    };
    const SPACES = ['market', 'plaza', 'alley_a', 'alley_b', 'alley_c'];
    const SPACE_LABEL = { market: 'MARKET', plaza: 'PLAZA', alley_a: 'ALLEY A', alley_b: 'ALLEY B', alley_c: 'ALLEY C' };
    const CHIP_COLORS = ['#39c6c0', '#e8a33d', '#8b5cf6', '#4ade80', '#60a5fa', '#f472b6',
                         '#f59e0b', '#34d399', '#c084fc', '#fb7185', '#a3e635', '#22d3ee'];

    function esc(s) {
        if (s == null) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    const chipColor = (order, aid) => CHIP_COLORS[Math.max(0, order.indexOf(aid)) % CHIP_COLORS.length];
    const tier = (inf) => inf >= 10 ? 'elder' : inf >= 5 ? 'notable' : 'commoner';

    let injected = false;
    function injectStyles() {
        if (injected) return; injected = true;
        const css = `
        .ag-root{display:flex;flex-direction:column;height:100%;background:${C.bg};color:${C.text};font-family:'SF Mono',ui-monospace,Menlo,monospace;border-radius:6px;overflow:hidden;border:1px solid ${C.border}}
        .ag-head{display:flex;align-items:center;gap:12px;padding:7px 14px;border-bottom:1px solid ${C.border};font-size:13px;flex:0 0 auto}
        .ag-title{color:${C.gold};letter-spacing:1px}
        .ag-round{color:${C.muted}}
        .ag-crisis{margin-left:auto;color:${C.red};font-size:12px}
        .ag-bill{margin-left:auto;color:${C.amber};font-size:12px}
        .ag-main{flex:1 1 auto;min-height:0;position:relative;padding:10px;display:grid;gap:8px;
            grid-template-columns:repeat(3,1fr);grid-template-rows:1.2fr 1fr;
            grid-template-areas:"market market plaza" "aa ab ac";
            background:linear-gradient(rgba(8,10,16,.82),rgba(8,10,16,.9)),var(--ag-map) center/cover no-repeat}
        .ag-space{background:${C.panel};border:1px solid ${C.border};border-radius:8px;padding:8px 10px;min-height:0;display:flex;flex-direction:column;overflow:hidden}
        .ag-space.market{grid-area:market;border-color:rgba(57,198,192,.5)}
        .ag-space.plaza{grid-area:plaza;border-color:rgba(216,198,144,.5)}
        .ag-space.alley_a{grid-area:aa} .ag-space.alley_b{grid-area:ab} .ag-space.alley_c{grid-area:ac}
        .ag-space h4{font-size:10px;letter-spacing:2px;color:${C.muted};margin-bottom:6px}
        .ag-space.market h4{color:${C.teal}} .ag-space.plaza h4{color:${C.gold}}
        .ag-chips{display:flex;flex-wrap:wrap;gap:6px;align-content:flex-start}
        .ag-chip{display:flex;flex-direction:column;gap:2px;padding:4px 8px;border-radius:6px;background:rgba(11,14,20,.85);border:1px solid ${C.border};min-width:64px}
        .ag-chip.elder{border-color:${C.gold}} .ag-chip.notable{border-color:${C.teal}}
        .ag-chip .id{font-size:11px;display:flex;gap:5px;align-items:center}
        .ag-chip .dot{width:7px;height:7px;border-radius:50%}
        .ag-chip .inf{color:${C.gold};font-size:10px;margin-left:auto}
        .ag-bar{height:4px;border-radius:2px;background:#232a3f;overflow:hidden}
        .ag-bar i{display:block;height:100%}
        .ag-said{margin-top:6px;font-size:10.5px;color:${C.muted};line-height:1.5;overflow:hidden}
        .ag-said b{color:${C.text};font-weight:600}
        .ag-fallen{padding:4px 14px;font-size:11px;color:${C.muted};border-top:1px solid ${C.border};flex:0 0 auto}
        .ag-fallen .d{color:${C.red};margin-right:10px}
        .ag-log{flex:0 0 88px;overflow-y:auto;padding:7px 14px;border-top:1px solid ${C.border};background:#080a10;font-size:11.5px;line-height:1.55}
        .ag-log .t{color:${C.muted}} .ag-log .latest{background:rgba(216,198,144,.08)}
        .ag-empty{margin:auto;color:${C.muted};font-style:italic;font-size:14px;font-family:Georgia,serif}
        `;
        const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
    }

    class Agora12Renderer {
        constructor(container) {
            injectStyles();
            this.container = container;
            container.style.aspectRatio = '8 / 5';
            container.style.height = '100%';   // definite height (MUD lesson: no shrink-to-fit jitter)
            this.root = document.createElement('div');
            this.root.className = 'ag-root';
            container.appendChild(this.root);
        }

        initialState(matchConfig) {
            const a = (matchConfig && matchConfig.agents) || [];
            return { current: null, context: null, order: a.map(x => x.agent_id), log: [], turn: 0 };
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            if (!post) return state;
            const mv = (logEntry.envelope && logEntry.envelope.move) || {};
            const log = state.log.concat([{
                turn: logEntry.turn, agent: logEntry.agent_id,
                action: this.formatMoveSummary(logEntry),
                events: post.last_events || [],
            }]);
            return {
                current: post,
                context: logEntry.post_move_context || state.context,
                order: post.turn_order || state.order,
                log, turn: logEntry.turn,
            };
        }

        render(state, turn, lastMove, animate) {
            const cur = state.current;
            if (!cur) {
                this.root.innerHTML = '<div class="ag-empty">The agora awaits its first morning…</div>';
                return;
            }
            const ctx = state.context || {};
            const order = state.order || Object.keys(cur.agents || {});
            const agents = cur.agents || {};
            const alive = order.filter(a => agents[a] && agents[a].alive);
            const dead = order.filter(a => agents[a] && !agents[a].alive);
            const maxE = ctx.max_energy || 200;

            const stakes = ctx.stakes !== false;   // White Room: no bars, no ✦
            const chip = (aid) => {
                const a = agents[aid];
                if (!stakes) {
                    return `<div class="ag-chip" title="${esc(aid)}">
                              <span class="id"><span class="dot" style="background:${chipColor(order, aid)}"></span>${esc(aid)}</span>
                            </div>`;
                }
                const pct = Math.max(2, Math.round(100 * a.energy / maxE));
                const col = a.energy <= 20 ? C.red : a.energy <= 50 ? C.amber : C.green;
                const t = tier(a.influence);
                return `<div class="ag-chip ${t}" title="${esc(aid)} — energy ${a.energy}, influence ${a.influence} (${t})">
                          <span class="id"><span class="dot" style="background:${chipColor(order, aid)}"></span>${esc(aid)}
                            <span class="inf">${a.influence ? '✦' + a.influence : ''}</span></span>
                          <span class="ag-bar"><i style="width:${pct}%;background:${col}"></i></span>
                        </div>`;
            };

            const spaceHtml = (s) => {
                const here = alive.filter(a => agents[a].location === s);
                const said = (cur.messages && cur.messages[s]) || [];
                return `<div class="ag-space ${s}">
                          <h4>${SPACE_LABEL[s]}</h4>
                          <div class="ag-chips">${here.map(chip).join('') || ''}</div>
                          ${said.length ? `<div class="ag-said">${said.slice(-2).map(m =>
                              `<div><b>${esc(m.from)}:</b> "${esc(m.text).slice(0, 70)}"</div>`).join('')}</div>` : ''}
                        </div>`;
            };

            const head =
                `<div class="ag-head"><span class="ag-title">${esc((ctx.title || 'The Agora')).toUpperCase()}</span>` +
                `<span class="ag-round">round ${cur.round}/${ctx.rounds || '?'}${stakes ? ` · ${alive.length}/${order.length} alive` : ''}</span>` +
                (cur.crisis ? `<span class="ag-crisis">⚠ ${esc(cur.crisis.name).toUpperCase()}</span>`
                    : (cur.billboard ? `<span class="ag-bill">${esc(cur.billboard.text).slice(0, 60)}</span>` : '')) +
                `</div>`;

            const fallen = dead.length
                ? `<div class="ag-fallen">${dead.map(a =>
                      `<span class="d">☠ ${esc(a)} (r${agents[a].death_round ?? '?'})</span>`).join('')}</div>`
                : '';

            const logHtml = state.log.slice(-12).map((L, i, arr) => {
                const evs = (L.events || []).map(e => esc(e)).join(' · ');
                return `<div class="${i === arr.length - 1 ? 'latest' : ''}"><span class="t">t${L.turn} ${esc(L.agent)}</span> ▸ ${esc(L.action)}${evs ? ' — ' + evs : ''}</div>`;
            }).join('') || '<div class="t">(no events yet)</div>';

            this.root.innerHTML = head +
                `<div class="ag-main" style="--ag-map:url('assets/agora12/map.webp')">${SPACES.map(spaceHtml).join('')}</div>` +
                fallen +
                `<div class="ag-log">${logHtml}</div>`;
            const logEl = this.root.querySelector('.ag-log');
            if (logEl) logEl.scrollTop = logEl.scrollHeight;
        }

        renderResult(result, state) { /* app renders its own overlay */ }

        formatMoveSummary(logEntry) {
            const m = (logEntry.envelope && logEntry.envelope.move) || {};
            if (!m.verb) return `(${logEntry.result || '?'})`;
            const bits = [m.verb];
            if (m.location) bits.push(m.location);
            if (m.target) bits.push(m.target);
            if (m.message) bits.push('"' + String(m.message).slice(0, 26) + '"');
            return bits.join(' ');
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['agora12'] = Agora12Renderer;
})();
