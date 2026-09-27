/**
 * robust_nav replay page (v0.3) — reads replays written by
 * scripts/robust_nav_export_replay.py.
 *
 * Three views, kept apart on purpose (Yeoul 157):
 *   - the true world (evaluator view): the voxel world, the agent at its true
 *     cell and heading, the true beacon, a trail, the cell a collided move
 *     bumped, an infra-wait ring, and — as an overlay — the sensor footprint:
 *     the grid AS DELIVERED to the policy, projected onto the cells it covers;
 *   - "Policy input at t": the observation the controller received, in its
 *     own frame, and the info it got — nothing else;
 *   - "Evaluator only": the true local grid (cells where the delivered value
 *     differs are outlined), position, geodesic distance, cause, metrics and
 *     the pair with the nominal twin.
 * No shortest path and no recovery estimate is drawn in the policy views.
 */
(function () {
    'use strict';

    const HEAD = ['north', 'east', 'south', 'west'];
    const DELTA = { north: [0, -1], south: [0, 1], east: [1, 0], west: [-1, 0] };
    const KIND_COLOR = { moved: '#5d7a66', collided: '#e2574c', waited: '#4c7fe2', invalid: '#a86be2', infra_wait: '#f0a030' };
    const $ = (id) => document.getElementById(id);

    const turnRight = (h) => HEAD[(HEAD.indexOf(h) + 1) % 4];
    function bodyToWorld(f, r, h) {
        const [fx, fy] = DELTA[h], [rx, ry] = DELTA[turnRight(h)];
        return [f * fx + r * rx, f * fy + r * ry];
    }
    function cellOffset(i, j, R, frame, heading) {
        return frame === 'body' ? bodyToWorld(R - i, j - R, heading) : [j - R, i - R];
    }
    const kindOf = (row) => (row.outcome === 'waited' && row.cause === 'infra') ? 'infra_wait' : row.outcome;
    const bit = (g, i, j) => g[i][j] === '1';

    // ── the 3D view: the match viewer's voxel renderer plus overlays ────────
    function makeScene(container) {
        const Base = window.LxMBlockworld3D;
        if (!Base || !window.THREE) return null;
        class RobustNavScene extends Base {
            constructor(el) {
                super(el);
                // the page's CSS sets the size; the base renderer's 100% would grow with the grid row
                el.style.height = '';
                el.style.minHeight = '';
                this._resize();
                // the match viewer's 2D/3D toggle and narration strip belong to that page
                el.querySelectorAll('button').forEach((b) => b.remove());
                this.sub.style.display = 'none';
                this.tw = null;
                this.overlay = new this.T.Group();
                this.scene.add(this.overlay);
            }

            show(replay, t, opts) {
                const T = this.T, rows = replay.rows, row = rows[t];
                const lay = replay.header.layout;
                const state = {
                    world: replay.world,
                    agents: { a: { x: row.pos[0], y: row.pos[1], z: 1, facing: row.heading } },
                    ground_items: [{ type: 'beacon', x: lay.goal[0], y: lay.goal[1], z: 1 }],
                    turn_order: ['a'],
                };
                this.render(state, t, null, !!opts.animate);
                this.overlay.clear();
                if (opts.footprint) this._footprint(replay, row);
                if (opts.trail && t > 0) {
                    const pts = rows.slice(0, t + 1).map((r) => new T.Vector3(r.pos[0], 0.56, r.pos[1]));
                    const line = new T.Line(new T.BufferGeometry().setFromPoints(pts),
                                            new T.LineBasicMaterial({ color: 0x9fb3ff }));
                    this.overlay.add(line);
                }
                if (row.outcome === 'collided' && DELTA[row.action]) {
                    const [dx, dy] = DELTA[row.action];
                    const box = new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(1.02, 1.02, 1.02)),
                                                   new T.LineBasicMaterial({ color: 0xff4040 }));
                    box.position.set(row.pos[0] + dx, 1, row.pos[1] + dy);
                    this.overlay.add(box);
                }
                if (kindOf(row) === 'infra_wait') {
                    const ring = new T.Mesh(new T.TorusGeometry(0.62, 0.06, 8, 32),
                                            new T.MeshBasicMaterial({ color: 0xf0a030 }));
                    ring.rotation.x = Math.PI / 2;
                    ring.position.set(row.pos[0], 0.6, row.pos[1]);
                    this.overlay.add(ring);
                }
                this._paintOnce(!opts.animate);
            }

            _footprint(replay, row) {
                const T = this.T, obs = row.obs, R = (obs.valid.length - 1) / 2;
                const frame = replay.header.frame || 'world';
                const dims = replay.world.dimensions;
                const cells = [];
                for (let i = 0; i < obs.valid.length; i++) {
                    for (let j = 0; j < obs.valid.length; j++) {
                        const [dx, dy] = cellOffset(i, j, R, frame, row.heading);
                        const x = row.pos[0] + dx, y = row.pos[1] + dy;
                        if (x < 0 || y < 0 || x >= dims.x || y >= dims.y) continue;
                        let color, alpha;
                        if (!bit(obs.valid, i, j)) { color = 0x20232e; alpha = 0.75; }
                        else if (bit(obs.beacon, i, j)) { color = 0xffd86b; alpha = 0.8; }
                        else if (bit(obs.blocked, i, j)) { color = 0xe2574c; alpha = 0.6; }
                        else { color = 0x6fdc8c; alpha = 0.26; }
                        const onTop = bit(row.true.blocked, i, j);
                        cells.push({ x, y, h: onTop ? 1.53 : 0.53, color, alpha });
                    }
                }
                for (const alphaGroup of [0.26, 0.6, 0.75, 0.8]) {
                    const group = cells.filter((c) => c.alpha === alphaGroup);
                    if (!group.length) continue;
                    const mesh = new T.InstancedMesh(new T.BoxGeometry(0.94, 0.04, 0.94),
                        new T.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: alphaGroup, depthWrite: false }),
                        group.length);
                    const tmp = new T.Object3D(), col = new T.Color();
                    group.forEach((c, k) => {
                        tmp.position.set(c.x, c.h, c.y);
                        tmp.updateMatrix();
                        mesh.setMatrixAt(k, tmp.matrix);
                        mesh.setColorAt(k, col.setHex(c.color));
                    });
                    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
                    this.overlay.add(mesh);
                }
            }
        }
        try { return new RobustNavScene(container); } catch (e) { console.warn(e); return null; }
    }

    // ── 2D grids ────────────────────────────────────────────────────────────
    function hatch(ctx, x, y, s) {
        ctx.save();
        ctx.beginPath(); ctx.rect(x, y, s, s); ctx.clip();
        ctx.strokeStyle = '#4a4f66'; ctx.lineWidth = 1;
        for (let k = -s; k < s; k += 5) { ctx.beginPath(); ctx.moveTo(x + k, y + s); ctx.lineTo(x + k + s, y); ctx.stroke(); }
        ctx.restore();
    }

    function drawArrow(ctx, cx, cy, vx, vy, len, color, width) {
        const n = Math.hypot(vx, vy) || 1, ux = vx / n, uy = vy / n;
        const ex = cx + ux * len, ey = cy + uy * len;
        ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = width;
        ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(ex, ey); ctx.stroke();
        const a = Math.atan2(uy, ux), h = Math.max(5, width * 3);
        ctx.beginPath();
        ctx.moveTo(ex, ey);
        ctx.lineTo(ex - h * Math.cos(a - 0.45), ey - h * Math.sin(a - 0.45));
        ctx.lineTo(ex - h * Math.cos(a + 0.45), ey - h * Math.sin(a + 0.45));
        ctx.closePath(); ctx.fill();
    }

    /** heading/cue as a canvas vector (x right, y down) in the grid's frame */
    function headingVec(frame, heading) {
        return frame === 'body' ? [0, -1] : DELTA[heading];
    }
    function cueVec(frame, dir) {
        return frame === 'body' ? [dir[1], -dir[0]] : [dir[0], dir[1]];   // body: [fwd, right] -> right, up
    }

    function drawPolicyGrid(canvas, row, frame, cue) {
        const ctx = canvas.getContext('2d'), obs = row.obs, n = obs.valid.length, s = Math.floor(canvas.width / n);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        for (let i = 0; i < n; i++) {
            for (let j = 0; j < n; j++) {
                const x = j * s, y = i * s;
                if (!bit(obs.valid, i, j)) { ctx.fillStyle = '#1b1e29'; ctx.fillRect(x, y, s, s); hatch(ctx, x, y, s); }
                else if (bit(obs.beacon, i, j)) { ctx.fillStyle = '#ffd86b'; ctx.fillRect(x, y, s, s); }
                else if (bit(obs.blocked, i, j)) { ctx.fillStyle = '#3b4052'; ctx.fillRect(x, y, s, s); }
                else { ctx.fillStyle = '#dfe4ee'; ctx.fillRect(x, y, s, s); }
                ctx.strokeStyle = 'rgba(0,0,0,.25)'; ctx.strokeRect(x + 0.5, y + 0.5, s - 1, s - 1);
            }
        }
        const c = (n * s) / 2;
        ctx.fillStyle = '#7fd1c0';
        ctx.beginPath(); ctx.arc(c, c, s * 0.3, 0, Math.PI * 2); ctx.fill();
        const [hx, hy] = headingVec(frame, row.heading);
        drawArrow(ctx, c, c, hx, hy, s * 0.95, '#0f5d52', 3);
        if (cue && cue.valid && (cue.dir[0] || cue.dir[1])) {
            const [vx, vy] = cueVec(frame, cue.dir);
            drawArrow(ctx, c, c, vx, vy, s * 3.2, '#c070ff', 2.5);
        }
    }

    function drawTrueGrid(canvas, row) {
        const ctx = canvas.getContext('2d'), tr = row.true, obs = row.obs, n = tr.blocked.length, s = Math.floor(canvas.width / n);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        for (let i = 0; i < n; i++) {
            for (let j = 0; j < n; j++) {
                const x = j * s, y = i * s;
                ctx.fillStyle = bit(tr.beacon, i, j) ? '#ffd86b' : bit(tr.blocked, i, j) ? '#3b4052' : '#b9bfcc';
                ctx.fillRect(x, y, s, s);
                if (!bit(obs.valid, i, j)) {
                    ctx.fillStyle = 'rgba(15,17,21,.55)'; ctx.fillRect(x, y, s, s);
                } else if (obs.blocked[i][j] !== tr.blocked[i][j] || obs.beacon[i][j] !== tr.beacon[i][j]) {
                    ctx.strokeStyle = '#ff8a1f'; ctx.lineWidth = 2; ctx.strokeRect(x + 1.5, y + 1.5, s - 3, s - 3);
                }
            }
        }
        const c = (n * s) / 2;
        ctx.fillStyle = '#e2a86b';
        ctx.beginPath(); ctx.arc(c, c, s * 0.28, 0, Math.PI * 2); ctx.fill();
    }

    // ── timeline ────────────────────────────────────────────────────────────
    function drawTimeline(canvas, replay, t) {
        const dpr = window.devicePixelRatio || 1;
        const w = canvas.clientWidth, h = canvas.clientHeight;
        canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
        const ctx = canvas.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        const rows = replay.rows, N = rows.length - 1, budget = (replay.metrics && replay.metrics.budget) || N || 1;
        const span = Math.max(N, budget), pad = 8, cw = (w - 2 * pad) / (span + 1);
        const X = (k) => pad + k * cw;
        // impaired observations (index t) — thin band on top
        rows.forEach((r, k) => {
            if (r.impaired) { ctx.fillStyle = '#b04cc0'; ctx.fillRect(X(k), 6, Math.max(1, cw), 7); }
        });
        // step outcomes (row k = the result of step k)
        for (let k = 1; k <= N; k++) {
            ctx.fillStyle = KIND_COLOR[kindOf(rows[k])] || '#555';
            ctx.fillRect(X(k), 18, Math.max(1, cw - (cw > 3 ? 1 : 0)), 24);
        }
        // onset / release markers
        const spec = replay.header.condition_spec || {};
        if (spec.impairment && spec.window) {
            ctx.strokeStyle = '#f3c9f7'; ctx.lineWidth = 1;
            spec.window.forEach((v) => {
                if (v == null) return;
                ctx.beginPath(); ctx.moveTo(X(v), 2); ctx.lineTo(X(v), 46); ctx.stroke();
            });
        }
        // budget line and end label
        ctx.fillStyle = '#8a8fb0'; ctx.font = '11px ui-monospace, monospace';
        const end = replay.header.end || (replay.metrics && replay.metrics.end) || '';
        ctx.fillText(`end: ${end}${replay.header.abort_reason ? ' — ' + replay.header.abort_reason : ''}`, pad, h - 6);
        ctx.fillText(`budget ${budget}`, w - pad - 70, h - 6);
        // playhead
        ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(X(t) + cw / 2, 2); ctx.lineTo(X(t) + cw / 2, 46); ctx.stroke();
        canvas._geom = { pad, cw, N };
    }

    // ── text panels ─────────────────────────────────────────────────────────
    function policyText(replay, t) {
        const row = replay.rows[t], last = replay.rows.length - 1;
        const lines = [`t        ${t}`, `heading  ${row.heading}`,
            `last     ${JSON.stringify({ action: row.action, outcome: row.outcome, bump_side: row.bump_side })}`];
        if (row.cue) lines.push(`cue      dir [${row.cue.dir.join(', ')}]  valid ${row.cue.valid}`);
        lines.push(`frame    ${replay.header.frame || 'world'}${(replay.header.frame || 'world') === 'body' ? ' (heading up)' : ' (north up)'}`);
        if (t === 0) lines.push('info     (none at reset)');
        else {
            const info = { t, outcome: row.outcome, reward: row.reward, done: t === last && replay.header.end !== 'aborted' };
            if (info.done) info.end = replay.header.end;
            lines.push(`info     ${JSON.stringify(info)}`);
        }
        return lines.join('\n');
    }

    function evalText(replay, t) {
        const h = replay.header, row = replay.rows[t], m = replay.metrics, lay = h.layout;
        const spec = h.condition_spec || {}, imp = spec.impairment;
        const L = [
            `${h.task || ''} ${h.version || ''}  config ${String(h.config_sha256 || '').slice(0, 10)}`,
            `condition ${h.condition}${imp ? '  ' + JSON.stringify(imp) + '  window ' + JSON.stringify(spec.window) : ''}`,
            `layout ${lay.family}${lay.base_family ? ' (base ' + lay.base_family + ')' : ''}  seed ${h.seed}  shortest ${lay.shortest}${lay.shortest_base != null ? ' (base ' + lay.shortest_base + ')' : ''}`,
            `policy ${replay.policy || '?'}  rep ${replay.rep}  frame ${h.frame}`,
            '',
            `pos ${JSON.stringify(row.pos)}  geo-to-goal ${row.geo}  goal ${JSON.stringify(lay.goal)}`,
            `cause ${row.cause || '-'}${row.meta && row.meta.infra_fail ? '  infra: ' + row.meta.infra_fail : ''}`,
            `impaired obs ${row.impaired ? 'yes' : 'no'}${row.meta && row.meta.act_ms != null ? '  act ' + row.meta.act_ms + ' ms' : ''}`,
        ];
        if (m) {
            L.push('', `episode: ${m.end} in ${m.end_turn}  SPL ${m.spl}  search ${m.search_steps ?? '-'}  approach ${m.approach_steps ?? '-'}`);
            L.push(`counts ${JSON.stringify(m.counts)}`);
            L.push(`stuck max ${m.longest_stationary_run}  revisits ${m.revisit_moves}  backtracks ${m.backtracks}`);
            for (const [rel, w] of Object.entries(m.windows || {})) {
                L.push(`window@${rel}: ${w.status}  new ${w.new_cells ?? '-'}  geo+ ${w.geo_progress ?? '-'}`);
            }
        } else {
            L.push('', '(no metrics in this replay)');
        }
        if (replay.pair) {
            const p = replay.pair;
            L.push(`vs nominal twin: ${p.impaired_status} / ${p.nominal_status}  reach ${p.reach}` +
                   `  delay ${p.delay.diff ?? '-'}  Δnew ${p.new_cells.diff ?? '-'}  Δgeo ${p.geo_progress.diff ?? '-'}`);
        }
        return L.join('\n');
    }

    /** What the controller actually read (Yeoul 158). With no label, the env
     *  observation as delivered IS the policy input. With a label, the
     *  controller read its own encoding of it: the grid is shown as the env
     *  observation before that encoder, and its packet (if exported) below. */
    function showInfoCondition(rp, t) {
        const cond = rp.info_condition, box = $('infoCond'), sub = $('obsSub'), pk = $('packetText');
        if (!cond) {
            box.className = 'infocond';
            box.textContent = 'information condition: env observation as delivered (full local grid' +
                (rp.rows[0].cue ? ' + cue' : '') + ')';
            sub.textContent = 'exactly what the controller received — nothing else';
            pk.style.display = 'none';
            return;
        }
        box.className = 'infocond reduced';
        box.textContent = `information condition: ${cond}`;
        sub.textContent = 'env observation BEFORE this controller\'s encoder — it did not read this grid directly';
        const steps = rp.policy_input;
        if (steps) {
            const rec = steps[String(t)];
            pk.style.display = 'block';
            pk.textContent = 'controller input packet (from its encoder)\n' +
                (rec === undefined ? '(none recorded at this t)' : JSON.stringify(rec, null, 1));
        } else {
            pk.style.display = 'block';
            pk.textContent = 'controller input packet: not exported (--policy-input)';
        }
    }

    // ── app ─────────────────────────────────────────────────────────────────
    const app = { replay: null, t: 0, timer: null, scene: null };

    function setT(t, animate) {
        const rp = app.replay;
        if (!rp) return;
        app.t = Math.max(0, Math.min(rp.rows.length - 1, t));
        const row = rp.rows[app.t], frame = rp.header.frame || 'world';
        $('scrub').value = app.t;
        $('tLabel').textContent = `t = ${app.t} / ${rp.rows.length - 1}`;
        if (app.scene) app.scene.show(rp, app.t, { animate, footprint: $('foot').checked, trail: $('trail').checked });
        drawPolicyGrid($('obsGrid'), row, frame, row.cue);
        showInfoCondition(rp, app.t);
        drawTrueGrid($('trueGrid'), row);
        $('obsText').textContent = policyText(rp, app.t);
        $('evalText').textContent = evalText(rp, app.t);
        const spec = rp.header.condition_spec || {};
        const imp = $('impTag');
        if (spec.impairment) {
            imp.style.display = 'block';
            const [on, off] = spec.window || [0, null];
            imp.textContent = row.impaired ? `impaired: ${spec.impairment.kind} (t ${on}–${off == null ? 'end' : off - 1})`
                : (app.t < on ? `${spec.impairment.kind} from t=${on}` : `${spec.impairment.kind} released at t=${off}`);
            imp.style.opacity = row.impaired ? '1' : '.6';
        } else imp.style.display = 'none';
        const endTag = $('endTag');
        if (app.t === rp.rows.length - 1) {
            endTag.style.display = 'block';
            endTag.textContent = `end: ${rp.header.end}${rp.header.abort_reason ? ' — ' + rp.header.abort_reason : ''}`;
        } else endTag.style.display = 'none';
        drawTimeline($('timeline'), rp, app.t);
    }

    function stop() { if (app.timer) { clearInterval(app.timer); app.timer = null; } $('play').textContent = '▶'; }
    function play() {
        if (!app.replay) return;
        if (app.t >= app.replay.rows.length - 1) setT(0, false);
        const rate = Number($('speed').value) || 3;
        $('play').textContent = '⏸';
        app.timer = setInterval(() => {
            if (app.t >= app.replay.rows.length - 1) { stop(); return; }
            setT(app.t + 1, rate <= 8);
        }, 1000 / rate);
    }

    function load(replay) {
        stop();
        if (!replay || replay.kind !== 'robust_nav_replay') { message('not a robust_nav replay file'); return; }
        app.replay = replay;
        $('msg').style.display = 'none';
        $('main').style.display = '';
        $('scrub').max = replay.rows.length - 1;
        if (!app.scene) {
            app.scene = makeScene($('world'));
            if (!app.scene) $('worldTag').textContent = 'WebGL unavailable — grids and timeline only';
        }
        setT(0, false);
    }

    function message(html) {
        const m = $('msg');
        m.innerHTML = html;
        m.style.display = 'block';
    }

    async function fetchJSON(url) {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`${r.status} ${url}`);
        return r.json();
    }

    async function boot() {
        const params = new URLSearchParams(location.search);
        const src = params.get('src');
        $('file').addEventListener('change', (e) => {
            const f = e.target.files[0];
            if (!f) return;
            f.text().then((txt) => load(JSON.parse(txt))).catch((err) => message(String(err)));
        });
        const pick = $('pick');
        pick.addEventListener('change', () => {
            fetchJSON('/robust-nav-data/' + pick.value).then(load).catch((err) => message(String(err)));
        });
        try {
            const idx = await fetchJSON('/robust-nav-data/index.json');
            const groups = {};
            for (const e of idx.replays) {
                const g = `${e.task} · ${e.condition}`;
                (groups[g] = groups[g] || []).push(e);
            }
            for (const [g, es] of Object.entries(groups)) {
                const og = document.createElement('optgroup');
                og.label = g;
                for (const e of es) {
                    const o = document.createElement('option');
                    o.value = e.file;
                    o.textContent = `${e.policy} · seed ${e.seed} · ${e.end} in ${e.steps}` +
                        (e.info_condition ? ` · ${e.info_condition}` : '');
                    og.appendChild(o);
                }
                pick.appendChild(og);
            }
            if (src) {
                const hit = idx.replays.find((e) => src.endsWith('/' + e.file));
                if (hit) pick.value = hit.file;
                else {
                    const o = document.createElement('option');
                    o.value = ''; o.textContent = '(opened from URL)';
                    pick.insertBefore(o, pick.firstChild);
                    pick.value = '';
                }
            } else if (idx.replays.length) {
                pick.value = (idx.replays[0] || {}).file;
                load(await fetchJSON('/robust-nav-data/' + pick.value));
            }
        } catch (err) {
            pick.style.display = 'none';
            if (!src) {
                $('main').style.display = 'none';
                message('No replay index. Export some first:<br><code>.venv/bin/python scripts/robust_nav_export_replay.py --smoke &lt;smoke dir&gt; --policies … --conditions … --seeds …</code><br>' +
                        'then run <code>python viewer/server.py</code> and reload — or open a replay file above.');
            }
        }
        if (src) fetchJSON(src).then(load).catch((err) => message(String(err)));

        $('first').onclick = () => { stop(); setT(0, false); };
        $('last').onclick = () => { stop(); if (app.replay) setT(app.replay.rows.length - 1, false); };
        $('prev').onclick = () => { stop(); setT(app.t - 1, true); };
        $('next').onclick = () => { stop(); setT(app.t + 1, true); };
        $('play').onclick = () => (app.timer ? stop() : play());
        $('speed').onchange = () => { if (app.timer) { stop(); play(); } };
        $('scrub').oninput = (e) => { stop(); setT(Number(e.target.value), false); };
        $('foot').onchange = () => setT(app.t, false);
        $('trail').onchange = () => setT(app.t, false);
        $('timeline').addEventListener('click', (e) => {
            const g = e.currentTarget._geom;
            if (!g) return;
            const x = e.clientX - e.currentTarget.getBoundingClientRect().left;
            stop();
            setT(Math.round((x - g.pad) / g.cw - 0.5), false);
        });
        window.addEventListener('resize', () => app.replay && drawTimeline($('timeline'), app.replay, app.t));
        window.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
            if ([' ', 'ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(e.key)) e.preventDefault();
            if (e.key === ' ') { app.timer ? stop() : play(); }
            else if (e.key === 'ArrowRight') { stop(); setT(app.t + 1, true); }
            else if (e.key === 'ArrowLeft') { stop(); setT(app.t - 1, true); }
            else if (e.key === 'Home') { stop(); setT(0, false); }
            else if (e.key === 'End') { stop(); if (app.replay) setT(app.replay.rows.length - 1, false); }
        });
    }

    boot();
})();
