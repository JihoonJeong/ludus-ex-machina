/**
 * MUD (text-adventure field) renderer for the LxM Match Viewer.
 *
 * A 16-bit-adventure UI for the language-world-model field. Per-turn state is
 * pulled from `post_move_state` (= engine `current`: rooms / agents / objects /
 * npcs / locks / flags / last_events) and `post_move_context` (scenario / goal).
 *
 * Layout: a room panel (prose + exits + objects + NPCs + inventory) beside a
 * discovered-rooms MAP (the world model the agent is building — visited rooms
 * drawn, current room ★, reachable-but-unentered rooms shown as fog "?"), with a
 * scrolling event log below.
 *
 * IMAGE-READY: the room panel background tries
 *   assets/mud/<scenario>/<room_id>.png
 * and gracefully falls back to a 16-bit gradient when the image is absent.
 * Drop generated room art at that path (no code change needed).
 */

(function () {
    const C = {
        bg: '#0e0f1a', panel: '#15172a', frame: '#3a3f63', frameLit: '#d8c690',
        text: '#e6e3d3', muted: '#8a8fb0', accent: '#d8c690', parchment: '#efe6c8',
        exit: '#7fd1c0', locked: '#e2768c', obj: '#cda6e8', npc: '#f0b86e',
        you: '#ffd86b', fog: '#4a4f70', edge: '#454a6e', win: '#7fe0a0', loss: '#e2768c',
    };
    const DIR_DELTA = {
        north: [0, -1], south: [0, 1], east: [1, 0], west: [-1, 0],
        up: [0, -1], down: [0, 1], in: [1, 1], out: [-1, -1],
    };
    const DIR_ARROW = {
        north: '↑N', south: '↓S', east: '→E', west: '←W',
        up: '↑up', down: '↓down', in: 'in', out: 'out',
    };

    function esc(s) {
        if (s == null) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    const shortName = (n) => esc(String(n || '?').replace(/^The\s+/i, ''));

    // ---- agent-local view derived from `current` (mirrors engine fog) ---------
    function agentView(cur, aid) {
        const agent = (cur.agents || {})[aid] || {};
        const rid = agent.location;
        const room = (cur.rooms || {})[rid] || { name: '?', desc: '', exits: {} };
        const objs = cur.objects || {};
        const locks = cur.locks || {};

        const visible = [];
        for (const oid in objs) {
            const o = objs[oid];
            if (o.loc === `room:${rid}` && o.visible !== false) visible.push(o.name);
            const loc = o.loc || '';
            if (loc.startsWith('in:') && o.visible !== false) {
                const cont = objs[loc.slice(3)];
                if (cont && cont.loc === `room:${rid}` && cont.open) visible.push(o.name);
            }
        }
        const inv = [];
        for (const oid in objs) if (objs[oid].loc === `inv:${aid}`) inv.push(objs[oid].name);

        const npcs = [];
        for (const nid in (cur.npcs || {})) if (cur.npcs[nid].loc === rid) npcs.push(cur.npcs[nid].name);

        const exits = [];
        for (const d in (room.exits || {})) {
            const e = room.exits[d];
            const locked = !!(e.lock && locks[e.lock] && locks[e.lock].locked);
            exits.push({ dir: d, to: e.to, locked });
        }
        return { rid, room, visible, inv, npcs, exits, visited: agent.visited || [] };
    }

    // ---- map layout: BFS grid from the start room over all exits -------------
    function layout(rooms, startRid) {
        const pos = {}, used = new Set(), q = [];
        if (!startRid || !rooms[startRid]) startRid = Object.keys(rooms || {})[0];
        if (!startRid) return pos;
        pos[startRid] = [0, 0]; used.add('0,0'); q.push(startRid);
        while (q.length) {
            const rid = q.shift();
            const [gx, gy] = pos[rid];
            const exits = (rooms[rid] || {}).exits || {};
            for (const d in exits) {
                const to = exits[d].to;
                if (!to || pos[to] || !rooms[to]) continue;
                const [dx, dy] = DIR_DELTA[d] || [1, 0];
                let nx = gx + dx, ny = gy + dy, guard = 0;
                while (used.has(`${nx},${ny}`) && guard < 8) { nx += (dx || 1); ny += dy; guard++; }
                pos[to] = [nx, ny]; used.add(`${nx},${ny}`); q.push(to);
            }
        }
        return pos;
    }

    function mapSvg(cur, view) {
        const rooms = cur.rooms || {};
        const visited = new Set(view.visited);
        const start = view.visited[0] || view.rid;
        const pos = layout(rooms, start);

        // Drawn = visited ∪ fog (reachable-but-unentered from a visited room).
        const fog = new Set();
        for (const rid of visited) {
            const ex = (rooms[rid] || {}).exits || {};
            for (const d in ex) if (ex[d].to && !visited.has(ex[d].to)) fog.add(ex[d].to);
        }
        const drawn = new Set([...visited, ...fog].filter(r => pos[r]));
        if (!drawn.size) return '<div class="mud-map-empty">(exploring…)</div>';

        const CELL = 74, NW = 58, NH = 36, PAD = 26;
        let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
        for (const r of drawn) { const [x, y] = pos[r]; minx = Math.min(minx, x); miny = Math.min(miny, y); maxx = Math.max(maxx, x); maxy = Math.max(maxy, y); }
        const cx = (r) => (pos[r][0] - minx) * CELL + PAD + NW / 2;
        const cy = (r) => (pos[r][1] - miny) * CELL + PAD + NH / 2;
        const W = (maxx - minx) * CELL + NW + 2 * PAD;
        const H = (maxy - miny) * CELL + NH + 2 * PAD;

        const edges = [];
        for (const rid of visited) {
            const ex = (rooms[rid] || {}).exits || {};
            for (const d in ex) {
                const to = ex[d].to;
                if (!to || !drawn.has(to) || !pos[rid]) continue;
                if (rid > to && visited.has(to)) continue; // de-dup bidirectional
                const locked = !!(ex[d].lock && (cur.locks || {})[ex[d].lock] && cur.locks[ex[d].lock].locked);
                edges.push(`<line x1="${cx(rid)}" y1="${cy(rid)}" x2="${cx(to)}" y2="${cy(to)}" stroke="${locked ? C.locked : C.edge}" stroke-width="${locked ? 2 : 2.5}" ${locked ? 'stroke-dasharray="4 3"' : ''}/>`);
            }
        }
        const nodes = [];
        for (const r of drawn) {
            const x = cx(r) - NW / 2, y = cy(r) - NH / 2;
            const isFog = fog.has(r) && !visited.has(r);
            const isCur = r === view.rid;
            const fill = isCur ? 'rgba(216,198,144,0.22)' : (isFog ? 'transparent' : C.panel);
            const stroke = isCur ? C.you : (isFog ? C.fog : C.frame);
            const label = isFog ? '?' : shortName((rooms[r] || {}).name);
            nodes.push(
                `<g>${isCur ? `<rect x="${x - 3}" y="${y - 3}" width="${NW + 6}" height="${NH + 6}" rx="6" fill="none" stroke="${C.you}" stroke-width="1" opacity="0.4"/>` : ''}` +
                `<rect x="${x}" y="${y}" width="${NW}" height="${NH}" rx="5" fill="${fill}" stroke="${stroke}" stroke-width="${isCur ? 2 : 1.5}" ${isFog ? 'stroke-dasharray="3 3"' : ''}/>` +
                `<text x="${cx(r)}" y="${cy(r) + 4}" text-anchor="middle" font-size="${isFog ? 16 : 10}" fill="${isCur ? C.you : (isFog ? C.fog : C.text)}" font-family="monospace">${label.length > 9 ? label.slice(0, 8) + '…' : label}</text>` +
                `${isCur ? `<text x="${cx(r)}" y="${y - 6}" text-anchor="middle" font-size="11" fill="${C.you}">★</text>` : ''}</g>`
            );
        }
        return `<svg viewBox="0 0 ${W} ${H}" width="100%" preserveAspectRatio="xMidYMid meet" style="max-height:100%">${edges.join('')}${nodes.join('')}</svg>`;
    }

    let injected = false;
    function injectStyles() {
        if (injected) return; injected = true;
        const css = `
        .mud-root{position:relative;display:flex;flex-direction:column;height:100%;background:${C.bg};color:${C.text};font-family:'SF Mono',ui-monospace,Menlo,monospace;border-radius:6px;overflow:hidden;border:1px solid ${C.frame}}
        .mud-goal{padding:7px 14px;background:linear-gradient(90deg,rgba(216,198,144,0.14),transparent);border-bottom:1px solid ${C.frame};font-size:13px;color:${C.accent};letter-spacing:.3px;flex:0 0 auto}
        .mud-goal b{color:${C.parchment}}
        .mud-main{display:flex;flex:1 1 auto;min-height:0}
        .mud-room{flex:1 1 62%;padding:16px 18px;background-color:#0c0d16;background-size:cover;background-position:center;display:flex;flex-direction:column;min-width:0;border-right:1px solid ${C.frame}}
        .mud-room-title{font-size:15px;color:${C.frameLit};text-shadow:0 1px 0 #000;margin-bottom:10px;letter-spacing:.5px}
        .mud-room-desc{font-size:13.5px;line-height:1.6;color:${C.parchment};margin-bottom:14px;font-family:Georgia,'Times New Roman',serif;max-width:60ch}
        .mud-meta{margin-top:auto;font-size:12.5px;line-height:1.9}
        .mud-meta .k{color:${C.muted};display:inline-block;min-width:74px}
        .mud-exit{color:${C.exit}}
        .mud-exit.locked{color:${C.locked}}
        .mud-obj{color:${C.obj}} .mud-npc{color:${C.npc}} .mud-inv{color:${C.parchment}}
        .mud-side{flex:0 0 35%;display:flex;flex-direction:column;min-width:0;background:#0b0c15}
        .mud-map-wrap{flex:1 1 auto;min-height:0;padding:10px;display:flex;flex-direction:column}
        .mud-map-title{font-size:11px;color:${C.muted};letter-spacing:2px;margin-bottom:4px}
        .mud-map{flex:1 1 auto;min-height:0;display:flex;align-items:center;justify-content:center}
        .mud-map-empty{color:${C.fog};font-size:12px;margin:auto}
        .mud-legend{font-size:10.5px;color:${C.muted};padding-top:4px;border-top:1px solid ${C.frame}}
        .mud-legend .y{color:${C.you}} .mud-legend .f{color:${C.fog}} .mud-legend .l{color:${C.locked}}
        .mud-log{flex:0 0 96px;overflow-y:auto;padding:8px 14px;border-top:1px solid ${C.frame};background:#090a12;font-size:12px;line-height:1.55}
        .mud-log .turn{color:${C.muted}} .mud-log .act{color:${C.accent}} .mud-log .ev{color:${C.text}}
        .mud-log .latest{background:rgba(216,198,144,0.08)}
        .mud-placeholder{margin:auto;color:${C.muted};font-family:Georgia,serif;font-style:italic;font-size:15px}
        .mud-banner{position:absolute;left:50%;bottom:108px;transform:translateX(-50%);padding:8px 18px;border-radius:8px;font-size:14px;background:rgba(9,10,18,.94);border:1px solid ${C.frame}}
        .mud-banner.win{color:${C.win};border-color:${C.win}} .mud-banner.loss{color:${C.loss}}
        `;
        const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
    }

    class MudRenderer {
        constructor(container) {
            injectStyles();
            this.container = container;
            container.style.aspectRatio = '8 / 5'; // landscape, not the default square
            this.root = document.createElement('div');
            this.root.className = 'mud-root';
            container.appendChild(this.root);
        }

        initialState(matchConfig) {
            const a = (matchConfig && matchConfig.agents) || [];
            return { current: null, context: null, perspective: a[0] ? a[0].agent_id : null, log: [], turn: 0 };
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            if (!post) return state;
            const aid = logEntry.agent_id || state.perspective;
            const mv = (logEntry.envelope && logEntry.envelope.move) || {};
            const log = state.log.concat([{
                turn: logEntry.turn, agent: aid,
                action: this.formatMoveSummary(logEntry),
                events: post.last_events || [],
            }]);
            return {
                current: post,
                context: logEntry.post_move_context || state.context,
                perspective: aid,
                log,
                turn: logEntry.turn,
            };
        }

        render(state, turn, lastMove, animate) {
            const cur = state.current;
            this.root.querySelectorAll('.mud-banner').forEach(b => b.remove());
            if (!cur || !state.perspective) {
                this.root.innerHTML = `<div class="mud-placeholder">The adventure awaits its first move…</div>`;
                return;
            }
            const ctx = state.context || {};
            const v = agentView(cur, state.perspective);
            const scenario = ctx.scenario_id || 'astronomer_tower';
            const img = `assets/mud/${scenario}/${v.rid}.webp`;

            const exitsHtml = v.exits.length
                ? v.exits.map(e => `<span class="mud-exit${e.locked ? ' locked' : ''}">${DIR_ARROW[e.dir] || e.dir}${e.locked ? ' 🔒' : ''}</span>`).join('  ')
                : '<span class="mud-exit">(none)</span>';

            const logHtml = state.log.slice(-14).map((L, i, arr) => {
                const evs = (L.events || []).map(e => `<span class="ev">${esc(e)}</span>`).join(' ');
                return `<div class="${i === arr.length - 1 ? 'latest' : ''}"><span class="turn">t${L.turn}</span> <span class="act">▸ ${esc(L.action)}</span> — ${evs}</div>`;
            }).join('') || '<div class="turn">(no events yet)</div>';

            this.root.innerHTML = `
                <div class="mud-goal">GOAL · <b>${esc(ctx.goal || ctx.title || 'explore')}</b></div>
                <div class="mud-main">
                    <div class="mud-room" style="background-image:linear-gradient(rgba(8,9,16,.62),rgba(8,9,16,.86)),url('${img}')">
                        <div class="mud-room-title">═══ ${esc(v.room.name)} ═══</div>
                        <div class="mud-room-desc">${esc(v.room.desc)}</div>
                        <div class="mud-meta">
                            <div><span class="k">Exits:</span> ${exitsHtml}</div>
                            <div><span class="k">You see:</span> <span class="mud-obj">${v.visible.length ? v.visible.map(esc).join(' · ') : 'nothing of note'}</span></div>
                            ${v.npcs.length ? `<div><span class="k">Present:</span> <span class="mud-npc">${v.npcs.map(esc).join(' · ')}</span></div>` : ''}
                            <div><span class="k">Inventory:</span> <span class="mud-inv">${v.inv.length ? v.inv.map(esc).join(' · ') : '(empty)'}</span></div>
                        </div>
                    </div>
                    <div class="mud-side">
                        <div class="mud-map-wrap">
                            <div class="mud-map-title">WORLD MODEL · MAP</div>
                            <div class="mud-map">${mapSvg(cur, v)}</div>
                            <div class="mud-legend"><span class="y">★</span> you · <span class="f">?</span> unexplored · <span class="l">┄</span> locked</div>
                        </div>
                    </div>
                </div>
                <div class="mud-log">${logHtml}</div>`;
            const logEl = this.root.querySelector('.mud-log');
            if (logEl) logEl.scrollTop = logEl.scrollHeight;
        }

        renderResult(result, state) {
            if (!result) return;
            this.root.querySelectorAll('.mud-banner').forEach(b => b.remove());
            const solved = result.outcome === 'solved';
            const b = document.createElement('div');
            b.className = 'mud-banner ' + (solved ? 'win' : 'loss');
            b.textContent = solved ? `✦ ${result.summary || 'Zone solved!'}` : `${result.summary || 'Unsolved.'}`;
            this.root.appendChild(b);
        }

        formatMoveSummary(logEntry) {
            const m = (logEntry.envelope && logEntry.envelope.move) || {};
            if (!m.verb) return `(${logEntry.result || '?'})`;
            return [m.verb, m.direction, m.item, m.target].filter(Boolean).join(' ');
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['mud'] = MudRenderer;
})();
