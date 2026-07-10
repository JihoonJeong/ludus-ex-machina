/**
 * MUD (text-adventure field) renderer for the LxM Match Viewer.
 *
 * A 16-bit-adventure UI for the language-world-model field. Per-turn state is
 * pulled from `post_move_state` (= engine `current`: rooms / agents / objects /
 * npcs / locks / flags / last_events) and `post_move_context` (scenario / goal).
 *
 * Layout: a room panel (prose + exits + objects + NPCs + inventory) beside a
 * compact WORLD-MODEL mini-map (discovered rooms as a graph — current room ★,
 * reachable-but-unentered rooms as fog "?", locked exits as red dashed edges),
 * with a scrolling event log below. Rooms are labelled with short codes (AS, SL,
 * …) mapped to full names in a legend. Press **M** or click the map (or the ⤢
 * button) for a LARGE overlay map with zoom (+/−/fit) and pan.
 *
 * IMAGE-READY: the room panel background tries
 *   assets/mud/<scenario>/<room_id>.webp
 * and gracefully falls back to a 16-bit gradient when the image is absent.
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

    // ---- short room codes (AS, SL, …), stable + unique across the zone -------
    function baseCode(name) {
        const clean = String(name || '?').replace(/^the\s+/i, '').trim();
        const words = clean.split(/[\s'’\-]+/).filter(w => w.length > 1);
        if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
        return (clean.slice(0, 2) || '?').replace(/^./, c => c.toUpperCase());
    }
    function assignCodes(rooms) {
        const codes = {}, used = new Set();
        for (const rid of Object.keys(rooms || {}).sort()) {
            let c = baseCode((rooms[rid] || {}).name), base = c, n = 2;
            while (used.has(c)) { c = (base[0] || '?') + n; n++; }
            used.add(c); codes[rid] = c;
        }
        return codes;
    }

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
            exits.push({ dir: d, to: e.to, locked: !!(e.lock && locks[e.lock] && locks[e.lock].locked) });
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

    // ---- map SVG at a FIXED cell scale (boxes never rescale; scroll/zoom
    //      handled by the container). Returns natural W/H + current-node center.
    function mapSvg(cur, view, codes) {
        const rooms = cur.rooms || {};
        const visited = new Set(view.visited);
        const pos = layout(rooms, view.visited[0] || view.rid);
        const fog = new Set();
        for (const rid of visited) {
            const ex = (rooms[rid] || {}).exits || {};
            for (const d in ex) if (ex[d].to && !visited.has(ex[d].to)) fog.add(ex[d].to);
        }
        const drawn = new Set([...visited, ...fog].filter(r => pos[r]));
        if (!drawn.size) return { svg: '<div class="mud-map-empty">(exploring…)</div>', W: 0, H: 0, curX: null, curY: null };

        const CELL = 64, NW = 46, NH = 30, PAD = 18;
        let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
        for (const r of drawn) { const [x, y] = pos[r]; minx = Math.min(minx, x); miny = Math.min(miny, y); maxx = Math.max(maxx, x); maxy = Math.max(maxy, y); }
        const cx = r => (pos[r][0] - minx) * CELL + PAD + NW / 2;
        const cy = r => (pos[r][1] - miny) * CELL + PAD + NH / 2;
        const W = (maxx - minx) * CELL + NW + 2 * PAD, H = (maxy - miny) * CELL + NH + 2 * PAD;

        const edges = [];
        for (const rid of visited) {
            const ex = (rooms[rid] || {}).exits || {};
            for (const d in ex) {
                const to = ex[d].to;
                if (!to || !drawn.has(to) || !pos[rid]) continue;
                if (rid > to && visited.has(to)) continue;
                const locked = !!(ex[d].lock && (cur.locks || {})[ex[d].lock] && cur.locks[ex[d].lock].locked);
                edges.push(`<line x1="${cx(rid)}" y1="${cy(rid)}" x2="${cx(to)}" y2="${cy(to)}" stroke="${locked ? C.locked : C.edge}" stroke-width="2" ${locked ? 'stroke-dasharray="4 3"' : ''}/>`);
            }
        }
        const nodes = [];
        for (const r of drawn) {
            const x = cx(r) - NW / 2, y = cy(r) - NH / 2;
            const isFog = fog.has(r) && !visited.has(r);
            const isCur = r === view.rid;
            const fill = isCur ? 'rgba(216,198,144,0.22)' : (isFog ? 'transparent' : C.panel);
            const stroke = isCur ? C.you : (isFog ? C.fog : C.frame);
            const label = isFog ? '?' : (codes[r] || '?');
            nodes.push(
                `<g>${isCur ? `<rect class="mud-halo" x="${x - 3}" y="${y - 3}" width="${NW + 6}" height="${NH + 6}" rx="6" fill="none" stroke="${C.you}" stroke-width="1" opacity="0.45"/>` : ''}` +
                `<rect x="${x}" y="${y}" width="${NW}" height="${NH}" rx="5" fill="${fill}" stroke="${stroke}" stroke-width="${isCur ? 2 : 1.4}" ${isFog ? 'stroke-dasharray="3 3"' : ''}/>` +
                `<text x="${cx(r)}" y="${cy(r) + 4}" text-anchor="middle" font-size="${isFog ? 15 : 13}" fill="${isCur ? C.you : (isFog ? C.fog : C.text)}" font-family="monospace" font-weight="${isCur ? 'bold' : 'normal'}">${esc(label)}</text>` +
                `${isCur ? `<text class="mud-star" x="${cx(r)}" y="${y - 5}" text-anchor="middle" font-size="11" fill="${C.you}">★</text>` : ''}</g>`
            );
        }
        const svg = `<svg viewBox="0 0 ${W} ${H}" data-w="${W}" data-h="${H}" class="mud-mapsvg" xmlns="http://www.w3.org/2000/svg">${edges.join('')}${nodes.join('')}</svg>`;
        return { svg, W, H, curX: drawn.has(view.rid) ? cx(view.rid) : null, curY: drawn.has(view.rid) ? cy(view.rid) : null };
    }

    function legendHtml(view, codes, rooms) {
        const seen = [];
        for (const r of view.visited) if (!seen.includes(r)) seen.push(r);
        const items = seen.map(r => `<span class="lg-item"><b>${esc(codes[r] || '?')}</b> ${shortName((rooms[r] || {}).name)}</span>`).join('');
        return `<div class="lg-codes">${items}</div>` +
            `<div class="lg-sym"><span class="y">★</span> you · <span class="f">?</span> unexplored · <span class="l">┄</span> locked</div>`;
    }

    let injected = false;
    function injectStyles() {
        if (injected) return; injected = true;
        const css = `
        .mud-root{position:relative;display:flex;flex-direction:column;height:100%;background:${C.bg};color:${C.text};font-family:'SF Mono',ui-monospace,Menlo,monospace;border-radius:6px;overflow:hidden;border:1px solid ${C.frame}}
        .mud-goal{padding:7px 14px;background:linear-gradient(90deg,rgba(216,198,144,0.14),transparent);border-bottom:1px solid ${C.frame};font-size:13px;color:${C.accent};letter-spacing:.3px;flex:0 0 auto}
        .mud-goal b{color:${C.parchment}}
        .mud-main{display:flex;flex:1 1 auto;min-height:0}
        .mud-room{flex:1 1 62%;position:relative;padding:16px 18px;background-color:#0c0d16;background-size:cover;background-position:center;display:flex;flex-direction:column;min-width:0;border-right:1px solid ${C.frame};overflow:hidden}
        .mud-room>*{position:relative;z-index:2}
        .mud-scenewrap{position:absolute !important;inset:0;z-index:0 !important;pointer-events:none}
        .mud-scene{position:absolute;inset:0;width:100%;height:100%}
        .mud-scene-shade{position:absolute;inset:0;background:linear-gradient(rgba(8,9,16,.45) 0%,rgba(8,9,16,.25) 35%,rgba(8,9,16,.68) 100%)}
        .mud-subtitle{position:absolute;left:0;right:0;bottom:8px;text-align:center;font-family:Georgia,serif;font-size:13.5px;color:${C.parchment};text-shadow:0 1px 3px #000,0 0 12px rgba(0,0,0,.8);padding:0 40px;max-height:70px;overflow:hidden}
        .mud-sub-line{margin-top:2px;opacity:.94}
        .mud-titlecard{position:absolute;inset:0;display:none;align-items:center;justify-content:center;z-index:3}
        .mud-titlecard.show{display:flex;animation:mudTcIn .8s cubic-bezier(.22,1.4,.36,1) both}
        .mud-tc-inner{background:rgba(10,11,20,.78);border:1px solid ${C.frameLit};border-radius:10px;padding:18px 34px;text-align:center;color:${C.frameLit};font-size:22px;letter-spacing:2px;box-shadow:0 0 40px rgba(216,198,144,.35),inset 0 0 24px rgba(216,198,144,.08)}
        .mud-tc-inner span{display:block;margin-top:6px;font-size:12.5px;letter-spacing:1px;color:${C.parchment}}
        @keyframes mudTcIn{from{transform:scale(.7);opacity:0}to{transform:scale(1);opacity:1}}
        .mud-halo{animation:mudHalo 2.2s ease-in-out infinite}
        @keyframes mudHalo{0%,100%{opacity:.2}50%{opacity:.75}}
        .mud-star{animation:mudStar 1.6s ease-in-out infinite}
        @keyframes mudStar{0%,100%{opacity:.6}50%{opacity:1}}
        .mud-collapse{margin-left:6px;color:${C.muted};cursor:pointer;font-size:12px;border:1px solid ${C.frame};border-radius:5px;padding:0 6px;line-height:1.5}
        .mud-collapse:hover{color:${C.accent};border-color:${C.accent}}
        .mud-showmap{position:absolute;top:12px;right:14px;z-index:5;background:rgba(9,10,18,.82);border:1px solid ${C.frame};color:${C.accent};border-radius:6px;padding:4px 11px;font-size:12px;cursor:pointer;font-family:'SF Mono',ui-monospace,monospace}
        .mud-showmap:hover{border-color:${C.accent}}
        .mud-room-title{font-size:15px;color:${C.frameLit};text-shadow:0 1px 0 #000;margin-bottom:10px;letter-spacing:.5px}
        .mud-room-desc{font-size:13.5px;line-height:1.6;color:${C.parchment};margin-bottom:14px;font-family:Georgia,'Times New Roman',serif;max-width:60ch}
        .mud-meta{margin-top:auto;font-size:12.5px;line-height:1.9}
        .mud-meta .k{color:${C.muted};display:inline-block;min-width:74px}
        .mud-exit{color:${C.exit}} .mud-exit.locked{color:${C.locked}}
        .mud-obj{color:${C.obj}} .mud-npc{color:${C.npc}} .mud-inv{color:${C.parchment}}
        .mud-side{flex:0 0 35%;display:flex;flex-direction:column;min-width:0;background:#0b0c15;padding:10px}
        .mud-map-title{font-size:11px;color:${C.muted};letter-spacing:2px;margin-bottom:4px;display:flex;align-items:center}
        .mud-open{margin-left:auto;color:${C.accent};cursor:pointer;font-size:10.5px;letter-spacing:.5px;border:1px solid ${C.frame};border-radius:5px;padding:1px 7px}
        .mud-open:hover{border-color:${C.accent}}
        .mud-map{flex:1 1 auto;min-height:90px;overflow:auto;position:relative;border:1px solid ${C.frame};border-radius:6px;background:rgba(0,0,0,.18);cursor:zoom-in}
        .mud-map .mud-mapsvg{display:block;margin:auto}
        .mud-map-empty{color:${C.fog};font-size:12px;margin:auto;text-align:center;padding-top:30px}
        .mud-legend{padding-top:5px;font-size:10.5px;color:${C.muted};line-height:1.7}
        .mud-legend .lg-item{display:inline-block;margin-right:8px;white-space:nowrap}
        .mud-legend .lg-item b{color:${C.text}}
        .mud-legend .lg-sym{margin-top:2px}
        .mud-legend .y{color:${C.you}} .mud-legend .f{color:${C.fog}} .mud-legend .l{color:${C.locked}}
        .mud-log{flex:0 0 92px;overflow-y:auto;padding:8px 14px;border-top:1px solid ${C.frame};background:#090a12;font-size:12px;line-height:1.55}
        .mud-log .turn{color:${C.muted}} .mud-log .act{color:${C.accent}} .mud-log .ev{color:${C.text}}
        .mud-log .latest{background:rgba(216,198,144,0.08)}
        .mud-placeholder{margin:auto;color:${C.muted};font-family:Georgia,serif;font-style:italic;font-size:15px}
        .mud-overlay{position:absolute;inset:0;z-index:30;display:none;flex-direction:column;background:rgba(6,7,13,.96)}
        .mud-overlay.open{display:flex}
        .mud-ov-head{display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid ${C.frame}}
        .mud-ov-title{font-size:12px;letter-spacing:2px;color:${C.muted}}
        .mud-ov-spacer{flex:1}
        .mud-ov-btn{background:${C.panel};border:1px solid ${C.frame};color:${C.text};border-radius:6px;padding:3px 11px;font-size:14px;cursor:pointer;font-family:'SF Mono',monospace;line-height:1.1}
        .mud-ov-btn:hover{border-color:${C.accent};color:${C.accent}}
        .mud-ov-map{flex:1 1 auto;overflow:auto;position:relative}
        .mud-ov-map .mud-mapsvg{display:block}
        .mud-ov-legend{padding:9px 14px;border-top:1px solid ${C.frame};font-size:12px;color:${C.muted};line-height:1.8}
        .mud-ov-legend .lg-item{display:inline-block;margin-right:14px;white-space:nowrap}
        .mud-ov-legend .lg-item b{color:${C.accent}}
        .mud-ov-legend .y{color:${C.you}} .mud-ov-legend .f{color:${C.fog}} .mud-ov-legend .l{color:${C.locked}}
        `;
        const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
    }

    class MudRenderer {
        constructor(container) {
            injectStyles();
            this.container = container;
            container.style.aspectRatio = '8 / 5';
            // Definite height so the board is sized by the layout (max-height cap),
            // NOT shrink-to-fit to per-turn content — otherwise the board jitters a
            // few px as room prose / object counts change between turns.
            container.style.height = '100%';
            this.root = document.createElement('div');
            this.root.className = 'mud-root';
            container.appendChild(this.root);

            // Map-overlay state (persists across per-turn re-renders).
            this._mapZoom = 1;
            this._overlayOpen = false;
            this._sideCollapsed = false;
            this._last = { cur: null, view: null, codes: {}, curX: null, curY: null };

            // ── Cinematic scene (Viewer 2.0 P1) ─────────────────────────────
            // A persistent canvas stage (fx.js) reparented into .mud-room after
            // every innerHTML rebuild — reparenting keeps the canvas alive, so
            // the Ken Burns drift / particles / typewriter never reset between
            // turns. Falls back silently to the old static background when
            // fx.js is absent or reduced-motion is on.
            this._fx = null;
            if (window.LxMFX) {
                const FX = window.LxMFX;
                const wrap = document.createElement('div');
                wrap.className = 'mud-scenewrap';
                wrap.innerHTML =
                    `<canvas class="mud-scene"></canvas>` +
                    `<div class="mud-scene-shade"></div>` +
                    `<div class="mud-subtitle"></div>` +
                    `<div class="mud-titlecard"></div>`;
                const canvas = wrap.querySelector('canvas');
                const stage = new FX.Stage(canvas);
                this._fx = {
                    FX, wrap, stage,
                    ken: stage.add(new FX.KenBurnsLayer()),
                    particles: stage.add(new FX.ParticleLayer(null)),
                    vignette: stage.add(new FX.VignetteLayer({ strength: 0.5 })),
                    tw: new FX.Typewriter(wrap.querySelector('.mud-subtitle'), { cps: 60 }),
                    scenario: null, rid: null, wonShown: false,
                };
                stage.start();
            }

            // Overlay lives as a sibling of root (survives root.innerHTML rebuilds).
            this._overlay = document.createElement('div');
            this._overlay.className = 'mud-overlay';
            this._overlay.innerHTML =
                `<div class="mud-ov-head"><span class="mud-ov-title">WORLD MODEL · MAP</span>` +
                `<span class="mud-ov-spacer"></span>` +
                `<button class="mud-ov-btn" data-z="out" title="Zoom out">−</button>` +
                `<button class="mud-ov-btn" data-z="fit" title="Fit">fit</button>` +
                `<button class="mud-ov-btn" data-z="in" title="Zoom in">+</button>` +
                `<button class="mud-ov-btn mud-ov-close" title="Close (Esc/M)">×</button></div>` +
                `<div class="mud-ov-map"></div><div class="mud-ov-legend"></div>`;
            container.appendChild(this._overlay);

            // Open the overlay by clicking the mini-map or the ⤢ button.
            this.root.addEventListener('click', (e) => {
                if (e.target.closest('.mud-collapse')) { this._sideCollapsed = true; this._applyCollapse(); return; }
                if (e.target.closest('.mud-showmap')) { this._sideCollapsed = false; this._applyCollapse(); return; }
                if (e.target.closest('.mud-map') || e.target.closest('.mud-open')) this.openOverlay();
            });
            // Overlay controls (delegated; survive innerHTML refresh of the map body).
            this._overlay.addEventListener('click', (e) => {
                const zb = e.target.closest('[data-z]');
                if (zb) { this._zoom(zb.dataset.z); return; }
                if (e.target.closest('.mud-ov-close') || e.target === this._overlay) this.closeOverlay();
            });
            // M toggles, Esc closes — only while this viewer is the visible one.
            this._onKey = (e) => {
                if (!this.container || !this.container.isConnected || this.container.offsetParent === null) return;
                const t = e.target;
                if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
                if (e.key === 'm' || e.key === 'M') { e.preventDefault(); this.toggleOverlay(); }
                else if (e.key === 'Escape' && this._overlayOpen) this.closeOverlay();
            };
            document.addEventListener('keydown', this._onKey);
        }

        initialState(matchConfig) {
            const a = (matchConfig && matchConfig.agents) || [];
            return { current: null, context: null, perspective: a[0] ? a[0].agent_id : null, log: [], turn: 0 };
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            if (!post) return state;
            const aid = logEntry.agent_id || state.perspective;
            const log = state.log.concat([{
                turn: logEntry.turn, agent: aid,
                action: this.formatMoveSummary(logEntry),
                events: post.last_events || [],
            }]);
            const mv = (logEntry.envelope && logEntry.envelope.move) || {};
            return {
                current: post, context: logEntry.post_move_context || state.context,
                perspective: aid, log, turn: logEntry.turn,
                lastDir: mv.verb === 'go' ? mv.direction : null,
            };
        }

        render(state, turn, lastMove, animate) {
            const cur = state.current;
            if (!cur || !state.perspective) {
                this.root.innerHTML = `<div class="mud-placeholder">The adventure awaits its first move…</div>`;
                return;
            }
            const ctx = state.context || {};
            const v = agentView(cur, state.perspective);
            const codes = assignCodes(cur.rooms || {});
            const m = mapSvg(cur, v, codes);
            this._last = { cur, view: v, codes, curX: m.curX, curY: m.curY };

            const img = `assets/mud/${ctx.scenario_id || 'astronomer_tower'}/${v.rid}.webp`;
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
                        <div class="mud-map-title">WORLD MODEL · MAP <span class="mud-open" title="Full map (M)">⤢ M</span><span class="mud-collapse" title="Hide map (full-width room)">▸</span></div>
                        <div class="mud-map" title="Click or press M to expand">${m.svg}</div>
                        <div class="mud-legend">${legendHtml(v, codes, cur.rooms || {})}</div>
                    </div>
                </div>
                <div class="mud-log">${logHtml}</div>`;

            // Mini-map: fixed scale, scroll the current room into view.
            const mapEl = this.root.querySelector('.mud-map');
            const svgEl = mapEl && mapEl.querySelector('svg');
            if (svgEl) { this._sizeSvg(svgEl, 1); this._center(mapEl); }
            const logEl = this.root.querySelector('.mud-log');
            if (logEl) logEl.scrollTop = logEl.scrollHeight;
            this._applyCollapse();
            if (this._overlayOpen) this._renderOverlay();

            this._updateScene(state, cur, ctx, v, img, animate);
        }

        // ── cinematic scene update (P1) ─────────────────────────────────────
        _updateScene(state, cur, ctx, v, imgSrc, animate) {
            const fx = this._fx;
            if (!fx) return;
            // reparent the persistent scene into the freshly rebuilt room panel
            const room = this.root.querySelector('.mud-room');
            if (!room) return;
            if (fx.wrap.parentElement !== room) room.insertBefore(fx.wrap, room.firstChild);
            // the canvas now paints the art — drop the CSS photo, keep gradient
            room.style.backgroundImage = 'linear-gradient(rgba(8,9,16,.62),rgba(8,9,16,.86))';

            // per-scenario ambience, set once per match
            const sid = ctx.scenario_id || 'astronomer_tower';
            if (fx.scenario !== sid) {
                fx.scenario = sid;
                const AMBIENCE = {
                    astronomer_tower: { p: 'dust', warm: '255,190,90', strength: 0.5 },
                    grimhold_keep: { p: 'embers', warm: '255,120,40', strength: 0.58 },
                    ss_erebus: { p: 'debris', alarm: '255,60,50', strength: 0.6 },
                    critter_cove: { p: 'fireflies', strength: 0.42 },
                    tidewater_warren: { p: 'debris', strength: 0.55 },
                };
                const a = AMBIENCE[sid] || { p: 'dust', strength: 0.5 };
                fx.particles.set(a.p);
                fx.vignette.strength = a.strength;
                fx.vignette.warm = a.warm || null;
                fx.vignette.alarm = a.alarm || null;
            }

            // room change → Ken Burns crossfade, direction-aware
            if (fx.rid !== v.rid) {
                fx.rid = v.rid;
                fx.ken.show(fx.FX.loadImage(imgSrc), state.lastDir);
            }

            // narrate the newest events as a cinematic subtitle
            const latest = state.log[state.log.length - 1];
            if (animate && latest && latest.turn === state.turn) {
                const sub = fx.wrap.querySelector('.mud-subtitle');
                if (sub.childElementCount > 3) sub.innerHTML = '';
                for (const e of (latest.events || []).slice(0, 3)) fx.tw.type(e, 'mud-sub-line');
            }

            // win moment: golden burst + title card, once
            if (cur.won && !fx.wonShown) {
                fx.wonShown = true;
                fx.particles.burst('255,216,107', 110);
                setTimeout(() => fx.particles.burst('127,224,160', 70), 450);
                const card = fx.wrap.querySelector('.mud-titlecard');
                card.innerHTML = `<div class="mud-tc-inner">✦ ZONE SOLVED ✦<span>` +
                    `${esc(ctx.title || '')} · ${(cur.turn || 1) - 1} turns</span></div>`;
                card.classList.add('show');
            } else if (!cur.won && fx.wonShown) {
                // scrubbed back before the win
                fx.wonShown = false;
                fx.wrap.querySelector('.mud-titlecard').classList.remove('show');
            }
        }

        // ---- overlay map ----------------------------------------------------
        openOverlay() { this._overlayOpen = true; this._overlay.classList.add('open'); this._renderOverlay(true); }
        closeOverlay() { this._overlayOpen = false; this._overlay.classList.remove('open'); }
        toggleOverlay() { this._overlayOpen ? this.closeOverlay() : this.openOverlay(); }

        // Collapse the sidebar mini-map → room panel (with its art) goes full-width.
        // A floating "🗺 map" button restores it; M still opens the big overlay.
        _applyCollapse() {
            const side = this.root.querySelector('.mud-side');
            const room = this.root.querySelector('.mud-room');
            if (!side || !room) return;
            let btn = room.querySelector('.mud-showmap');
            if (this._sideCollapsed) {
                side.style.display = 'none';
                room.style.flexBasis = '100%';
                room.style.borderRight = 'none';
                if (!btn) {
                    btn = document.createElement('button');
                    btn.className = 'mud-showmap';
                    btn.textContent = '🗺 map';
                    btn.title = 'Show map';
                    room.appendChild(btn);
                }
            } else {
                side.style.display = '';
                room.style.flexBasis = '';
                room.style.borderRight = '';
                if (btn) btn.remove();
            }
        }

        _renderOverlay(fit) {
            if (!this._last.cur) return;
            const m = mapSvg(this._last.cur, this._last.view, this._last.codes);
            this._last.curX = m.curX; this._last.curY = m.curY;
            const mapEl = this._overlay.querySelector('.mud-ov-map');
            mapEl.innerHTML = m.svg;
            this._overlay.querySelector('.mud-ov-legend').innerHTML =
                legendHtml(this._last.view, this._last.codes, this._last.cur.rooms || {});
            const svgEl = mapEl.querySelector('svg');
            if (!svgEl) return;
            if (fit) this._zoom('fit'); else { this._sizeSvg(svgEl, this._mapZoom); this._center(mapEl); }
        }

        _zoom(mode) {
            const mapEl = this._overlay.querySelector('.mud-ov-map');
            const svgEl = mapEl && mapEl.querySelector('svg');
            if (!svgEl) return;
            const W = +svgEl.dataset.w || 1, H = +svgEl.dataset.h || 1;
            if (mode === 'in') this._mapZoom = Math.min(4, this._mapZoom * 1.25);
            else if (mode === 'out') this._mapZoom = Math.max(0.35, this._mapZoom / 1.25);
            else if (mode === 'fit') {
                const pad = 48;
                this._mapZoom = Math.max(0.35, Math.min(4,
                    Math.min((mapEl.clientWidth - pad) / W, (mapEl.clientHeight - pad) / H)));
            }
            this._sizeSvg(svgEl, this._mapZoom);
            this._center(mapEl);
        }

        _sizeSvg(svgEl, zoom) {
            svgEl.setAttribute('width', (+svgEl.dataset.w || 0) * zoom);
            svgEl.setAttribute('height', (+svgEl.dataset.h || 0) * zoom);
        }

        _center(containerEl) {
            const { curX, curY } = this._last;
            if (curX == null) return;
            const z = containerEl.classList.contains('mud-ov-map') ? this._mapZoom : 1;
            containerEl.scrollLeft = Math.max(0, curX * z - containerEl.clientWidth / 2);
            containerEl.scrollTop = Math.max(0, curY * z - containerEl.clientHeight / 2);
        }

        renderResult(result, state) {
            // The app renders its own result overlay (.result-overlay) — no
            // renderer-side banner, to avoid a duplicate.
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
