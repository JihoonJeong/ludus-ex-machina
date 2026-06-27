/**
 * Diplomacy renderer for the LxM Match Viewer — v2 "The Wheel" board.
 *
 * A board, not a node graph: central disk (The Crown), inner ring of five March
 * sectors, outer ring of five Capital sectors offset 36° so each capital straddles
 * its two marches. Territories fill by supply-center owner; armies are crests;
 * resolved orders draw as arrows (animated on step); hover shows a tooltip; every
 * private cable is shown (replay = mirror layer). Fonts sized for readability.
 */

(function () {
    const C = {
        bg: '#0c1020', ring: '#222a48', text: '#e8eaf2', dim: '#9aa2c8', muted: '#6b73a0',
        neutral: '#566089', crown: '#e6c14a', moveOk: '#5ee08a', moveFail: '#ff6b6b',
        support: '#f4ad3d', panel: 'rgba(18,24,46,0.72)', tip: 'rgba(8,11,22,0.94)',
    };
    const FALLBACK = ['#d6453d', '#e3b23c', '#3fa34d', '#3d7fd6', '#9b59b6'];
    const CAP_BY_K = ['pyre', 'solace', 'thorne', 'tarn', 'vael'];
    const MARCH_BY_K = ['ashmoor', 'sunreach', 'wildfen', 'coldwater', 'duskgate'];
    const LABEL = {
        pyre: 'Pyre', solace: 'Solace', thorne: 'Thorne', tarn: 'Tarn', vael: 'Vael',
        ashmoor: 'Ashmoor', sunreach: 'Sunreach', wildfen: 'Wildfen',
        coldwater: 'Coldwater', duskgate: 'Duskgate', crown: 'The Crown',
    };
    const KIND = {
        pyre: 'capital', solace: 'capital', thorne: 'capital', tarn: 'capital', vael: 'capital',
        ashmoor: 'march', sunreach: 'march', wildfen: 'march', coldwater: 'march', duskgate: 'march',
        crown: 'crown',
    };
    const ANIM_MS = 550;
    const hasRAF = typeof requestAnimationFrame === 'function';
    const now = () => (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    const F = (px, bold) => `${bold ? 'bold ' : ''}${px}px -apple-system, sans-serif`;
    const MONO = (px) => `${px}px "SF Mono", monospace`;

    class DiplomacyRenderer {
        constructor(container) {
            this.canvas = document.createElement('canvas');
            this.W = 1280; this.H = 860;
            this.canvas.width = this.W * 2;
            this.canvas.height = this.H * 2;
            this.canvas.style.width = '100%';
            this.canvas.style.height = '100%';
            this.ctx = this.canvas.getContext('2d');
            this.ctx.scale(2, 2);
            container.appendChild(this.canvas);
            this._raf = null; this._hover = null; this._last = null;
            this._layout();
            this._onMove = (e) => this._hoverAt(e);
            this._onLeave = () => { if (this._hover) { this._hover = null; this._repaint(); } };
            this.canvas.addEventListener('mousemove', this._onMove);
            this.canvas.addEventListener('mouseleave', this._onLeave);
        }

        _layout() {
            this.cx = 430; this.cy = 450; this.R0 = 78; this.R1 = 188; this.R2 = 320;
            this.PANELX = this.W - 332; this.PANELW = 312;
            this.region = {};
            const reg = (name, deg, rIn, rOut) => {
                this.region[name] = { a0: deg - 36, a1: deg + 36, rIn, rOut, cangle: deg, cr: (rIn + rOut) / 2 };
            };
            for (let k = 0; k < 5; k++) {
                reg(CAP_BY_K[k], 72 * k, this.R1, this.R2);
                reg(MARCH_BY_K[k], 72 * k + 36, this.R0, this.R1);
            }
            this.region.crown = { a0: 0, a1: 360, rIn: 0, rOut: this.R0, cangle: 0, cr: 0 };
        }

        _rad(d) { return (d - 90) * Math.PI / 180; }
        _pt(d, r) { const a = this._rad(d); return { x: this.cx + r * Math.cos(a), y: this.cy + r * Math.sin(a) }; }
        _centroid(p) { return p === 'crown' ? { x: this.cx, y: this.cy } : this._pt(this.region[p].cangle, this.region[p].cr); }

        initialState() {
            return { year: 1901, phase: 'press', players: {}, seat_order: [], units: {}, sc_owner: {}, last_resolution: null, press_messages: [] };
        }

        applyMove(state, logEntry) {
            const p = logEntry.post_move_state;
            if (!p) return state;
            return {
                ...state,
                year: p.year ?? state.year, phase: p.phase ?? state.phase,
                players: p.players ?? state.players, seat_order: p.seat_order ?? state.seat_order,
                units: p.units ?? state.units, sc_owner: p.sc_owner ?? state.sc_owner,
                last_resolution: p.last_resolution ?? state.last_resolution,
                press_messages: p.press_messages ?? state.press_messages,
            };
        }

        _color(state, a) {
            if (!a) return C.neutral;
            const pl = state.players?.[a];
            if (pl?.color) return pl.color;
            const i = (state.seat_order || []).indexOf(a);
            return FALLBACK[i] || C.neutral;
        }
        _name(state, a) { return state.players?.[a]?.name || a || '—'; }
        _sc(state, a) { return Object.values(state.sc_owner || {}).filter(o => o === a).length; }
        _ua(state, a) { return Object.values(state.units || {}).filter(o => o === a).length; }

        render(state, turnNumber, lastMove, animate = false) {
            this._last = { state, lastMove };
            if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
            if (animate && hasRAF) {
                const t0 = now();
                const loop = () => {
                    const t = Math.min(1, (now() - t0) / ANIM_MS);
                    this._paint(state, lastMove, t);
                    this._raf = (t < 1) ? requestAnimationFrame(loop) : null;
                };
                loop();
            } else {
                this._paint(state, lastMove, 1);
            }
        }
        _repaint() { if (this._last) this._paint(this._last.state, this._last.lastMove, 1); }

        _paint(state, lastMove, t) {
            const ctx = this.ctx;
            const g = ctx.createRadialGradient(this.cx, this.cy, 40, this.cx, this.cy, 520);
            g.addColorStop(0, '#141a31'); g.addColorStop(1, C.bg);
            ctx.fillStyle = C.bg; ctx.fillRect(0, 0, this.W, this.H);
            ctx.fillStyle = g; ctx.fillRect(0, 0, this.W, this.H);
            this._board(ctx, state);
            this._arrows(ctx, state, t);
            this._unitsLayer(ctx, state);
            this._header(ctx, state);
            this._scoreboard(ctx, state);
            this._cables(ctx, state);
            if (lastMove) this._footer(ctx, lastMove);
            if (this._hover) this._tooltip(ctx, state, this._hover);
        }

        _sectorPath(ctx, g) {
            const a0 = this._rad(g.a0), a1 = this._rad(g.a1);
            ctx.beginPath();
            ctx.arc(this.cx, this.cy, g.rOut, a0, a1);
            ctx.arc(this.cx, this.cy, g.rIn, a1, a0, true);
            ctx.closePath();
        }

        _board(ctx, state) {
            for (const prov of [...CAP_BY_K, ...MARCH_BY_K]) {
                const g = this.region[prov];
                const owner = state.sc_owner?.[prov];
                const col = this._color(state, owner);
                this._sectorPath(ctx, g);
                ctx.fillStyle = owner ? this._alpha(col, 0.26) : 'rgba(40,48,80,0.45)';
                ctx.fill();
                ctx.lineWidth = (this._hover === prov) ? 4 : 2.5;
                ctx.strokeStyle = (this._hover === prov) ? C.text : (owner ? col : C.ring);
                ctx.stroke();
                const lp = this._pt(g.cangle, g.cr + (KIND[prov] === 'capital' ? -18 : 0));
                ctx.fillStyle = owner ? this._alpha(col, 0.95) : C.muted;
                ctx.font = F(19); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                ctx.fillText(LABEL[prov], lp.x, lp.y);
            }
            ctx.beginPath(); ctx.arc(this.cx, this.cy, this.R0, 0, Math.PI * 2);
            const cOwner = state.sc_owner?.crown;
            ctx.fillStyle = cOwner ? this._alpha(this._color(state, cOwner), 0.32) : 'rgba(40,48,80,0.5)';
            ctx.fill();
            ctx.lineWidth = (this._hover === 'crown') ? 4 : 3; ctx.strokeStyle = C.crown; ctx.stroke();
            ctx.fillStyle = C.crown; ctx.font = F(20, true);
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText('♛ The Crown', this.cx, this.cy);
        }

        _arrows(ctx, state, t) {
            const lr = state.last_resolution;
            if (!lr || !lr.orders) return;
            const out = lr.outcomes || {};
            for (const [prov, o] of Object.entries(lr.orders)) {
                if (o.type !== 'support') continue;
                const a = this._centroid(prov), b = this._centroid(o.target);
                if (!a || !b) continue;
                const cut = out[prov] === 'support-cut';
                ctx.globalAlpha = t;
                ctx.strokeStyle = cut ? C.moveFail : C.support;
                ctx.lineWidth = 2.5; ctx.setLineDash(cut ? [5, 5] : [3, 8]);
                ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
                ctx.setLineDash([]); ctx.globalAlpha = 1;
            }
            for (const [prov, o] of Object.entries(lr.orders)) {
                if (o.type !== 'move') continue;
                const a = this._centroid(prov), b = this._centroid(o.dest);
                if (!a || !b) continue;
                this._arrow(ctx, a, b, out[prov] === 'move' ? C.moveOk : C.moveFail, out[prov] !== 'move', t);
            }
            for (const prov of Object.keys(lr.dislodged || {})) {
                const p = this._centroid(prov); if (!p) continue;
                ctx.globalAlpha = Math.min(1, t * 1.4);
                ctx.strokeStyle = C.moveFail; ctx.lineWidth = 3.5;
                ctx.beginPath(); ctx.arc(p.x, p.y, 26 + (1 - t) * 12, 0, Math.PI * 2); ctx.stroke();
                ctx.globalAlpha = 1;
            }
        }

        _arrow(ctx, from, to, color, dashed, t) {
            const ang = Math.atan2(to.y - from.y, to.x - from.x);
            const r = 30;
            const sx = from.x + r * Math.cos(ang), sy = from.y + r * Math.sin(ang);
            const fex = to.x - r * Math.cos(ang), fey = to.y - r * Math.sin(ang);
            const ex = sx + (fex - sx) * t, ey = sy + (fey - sy) * t;
            ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 4.5;
            ctx.setLineDash(dashed ? [9, 6] : []);
            ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey); ctx.stroke();
            ctx.setLineDash([]);
            if (t > 0.82) {
                const h = 15;
                ctx.beginPath(); ctx.moveTo(fex, fey);
                ctx.lineTo(fex - h * Math.cos(ang - 0.42), fey - h * Math.sin(ang - 0.42));
                ctx.lineTo(fex - h * Math.cos(ang + 0.42), fey - h * Math.sin(ang + 0.42));
                ctx.closePath(); ctx.fill();
            }
        }

        _unitsLayer(ctx, state) {
            // crest sits offset from the sector centre so it clears the centred label:
            // capitals lean outward (toward the rim), marches inward (toward the Crown).
            for (const [prov, owner] of Object.entries(state.units || {})) {
                let p;
                if (prov === 'crown') {
                    p = { x: this.cx, y: this.cy - this.R0 + 22 };
                } else {
                    const g = this.region[prov];
                    p = this._pt(g.cangle, g.cr + (KIND[prov] === 'capital' ? 42 : -32));
                }
                this._crest(ctx, p.x, p.y, this._color(state, owner), (this._name(state, owner)[0] || '?').toUpperCase());
            }
        }

        _crest(ctx, x, y, color, initial) {
            ctx.beginPath(); ctx.arc(x, y, 18, 0, Math.PI * 2);
            ctx.fillStyle = color; ctx.fill();
            ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(0,0,0,0.45)'; ctx.stroke();
            ctx.lineWidth = 1.5; ctx.strokeStyle = 'rgba(255,255,255,0.55)';
            ctx.beginPath(); ctx.arc(x, y, 13, 0, Math.PI * 2); ctx.stroke();
            ctx.fillStyle = '#0c1020'; ctx.font = F(17, true);
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText(initial, x, y + 1);
        }

        _header(ctx, state) {
            ctx.fillStyle = C.text; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
            ctx.font = F(30, true);
            ctx.fillText('DIPLOMACY · The Wheel', 24, 42);
            ctx.fillStyle = C.dim; ctx.font = F(21);
            ctx.fillText(`Year ${state.year}   ·   ${(state.phase || '').toUpperCase()}   ·   first to 6 of 11 centers wins`, 24, 70);
        }

        _scoreboard(ctx, state) {
            const x = this.PANELX, y0 = 36;
            ctx.fillStyle = C.text; ctx.font = F(21, true); ctx.textAlign = 'left';
            ctx.fillText('Standings', x, y0);
            const seats = (state.seat_order || []).slice().sort((a, b) => this._sc(state, b) - this._sc(state, a));
            seats.forEach((a, i) => {
                const y = y0 + 34 + i * 40;
                const elim = state.players?.[a]?.status === 'eliminated';
                const sc = this._sc(state, a), ar = this._ua(state, a);
                this._crest(ctx, x + 14, y - 5, this._color(state, a), (this._name(state, a)[0] || '?').toUpperCase());
                ctx.textAlign = 'left';
                ctx.fillStyle = elim ? C.muted : (i === 0 ? C.crown : C.text);
                ctx.font = F(19, i === 0);
                ctx.fillText(`${this._name(state, a)}${elim ? ' ✕' : ''}`, x + 40, y);
                const bx = x + 158, bw = 120;
                ctx.fillStyle = C.ring; ctx.fillRect(bx, y - 13, bw, 10);
                ctx.fillStyle = this._color(state, a); ctx.fillRect(bx, y - 13, bw * Math.min(1, sc / 11), 10);
                ctx.fillStyle = C.dim; ctx.font = MONO(15); ctx.textAlign = 'right';
                ctx.fillText(`${sc} SC · ${ar}a`, bx + bw, y);
            });
        }

        _cables(ctx, state) {
            const msgs = (state.press_messages || []).slice(-5);
            const x = this.PANELX, y0 = 290, w = this.PANELW;
            ctx.fillStyle = C.text; ctx.font = F(21, true); ctx.textAlign = 'left';
            ctx.fillText('Diplomatic cables', x, y0);
            ctx.fillStyle = C.muted; ctx.font = F(15);
            ctx.fillText('(replay sees every private word)', x, y0 + 20);
            let y = y0 + 40;
            if (!msgs.length) { ctx.fillStyle = C.muted; ctx.fillText('— no cables yet —', x, y + 8); return; }
            for (const m of msgs) {
                const col = this._color(state, m.from);
                const to = m.to === 'all' ? 'ALL' : this._name(state, m.to);
                const lines = this._wrap(ctx, (m.text || '').slice(0, 70), w - 18);
                const h = 26 + lines.length * 19;
                ctx.fillStyle = C.panel; this._round(ctx, x, y, w, h, 8); ctx.fill();
                ctx.fillStyle = col; ctx.fillRect(x, y, 4, h);
                ctx.fillStyle = col; ctx.font = F(16, true);
                ctx.fillText(`[${m.year}] ${this._name(state, m.from)} → ${to}`, x + 14, y + 20);
                ctx.fillStyle = C.dim; ctx.font = F(16);
                lines.forEach((ln, i) => ctx.fillText(ln, x + 14, y + 41 + i * 19));
                y += h + 9;
            }
        }

        _footer(ctx, lastMove) {
            ctx.fillStyle = C.panel; this._round(ctx, 16, this.H - 50, this.W - 360, 38, 8); ctx.fill();
            ctx.fillStyle = C.text; ctx.font = MONO(17); ctx.textAlign = 'left';
            ctx.fillText(this.formatMoveSummary(lastMove).slice(0, 88), 32, this.H - 26);
        }

        _tooltip(ctx, state, prov) {
            const c = this._centroid(prov);
            const owner = state.sc_owner?.[prov], occ = state.units?.[prov];
            const lines = [LABEL[prov], `center: ${owner ? this._name(state, owner) : 'neutral'}`,
                `army: ${occ ? this._name(state, occ) : '—'}`, `(${KIND[prov]})`];
            ctx.font = F(16);
            const w = Math.max(...lines.map(l => ctx.measureText(l).width)) + 24;
            const h = 22 + lines.length * 19;
            let x = c.x + 28, y = c.y - h / 2;
            if (x + w > this.PANELX - 10) x = c.x - w - 28;
            if (y < 8) y = 8;
            ctx.fillStyle = C.tip; this._round(ctx, x, y, w, h, 7); ctx.fill();
            ctx.strokeStyle = C.ring; ctx.lineWidth = 1; this._round(ctx, x, y, w, h, 7); ctx.stroke();
            ctx.textAlign = 'left';
            lines.forEach((l, i) => {
                ctx.fillStyle = i === 0 ? C.text : C.dim;
                ctx.font = F(16, i === 0);
                ctx.fillText(l, x + 12, y + 20 + i * 19);
            });
        }

        _hoverAt(e) {
            const rect = this.canvas.getBoundingClientRect();
            if (!rect.width) return;
            const lx = (e.clientX - rect.left) / rect.width * this.W;
            const ly = (e.clientY - rect.top) / rect.height * this.H;
            const prov = this._hitTest(lx, ly);
            if (prov !== this._hover) { this._hover = prov; if (!this._raf) this._repaint(); }
        }

        _hitTest(lx, ly) {
            const dx = lx - this.cx, dy = ly - this.cy, dist = Math.hypot(dx, dy);
            if (dist <= this.R0) return 'crown';
            let compass = Math.atan2(dy, dx) * 180 / Math.PI + 90;
            compass = ((compass % 360) + 360) % 360;
            const angDiff = (a, b) => { const d = ((a - b) % 360 + 360) % 360; return Math.min(d, 360 - d); };
            for (const prov of [...CAP_BY_K, ...MARCH_BY_K]) {
                const g = this.region[prov];
                if (dist >= g.rIn && dist <= g.rOut && angDiff(compass, ((g.cangle % 360) + 360) % 360) <= 36) return prov;
            }
            return null;
        }

        _wrap(ctx, text, maxw) {
            ctx.font = F(16);
            const words = text.split(' '); const lines = []; let cur = '';
            for (const w of words) {
                const tt = cur ? cur + ' ' + w : w;
                if (ctx.measureText(tt).width > maxw && cur) { lines.push(cur); cur = w; } else cur = tt;
            }
            if (cur) lines.push(cur);
            return lines.slice(0, 2);
        }
        _round(ctx, x, y, w, h, r) {
            ctx.beginPath();
            ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r);
            ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r);
            ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
        }
        _alpha(hex, a) {
            const m = hex.replace('#', '');
            const n = parseInt(m.length === 3 ? m.split('').map(c => c + c).join('') : m, 16);
            return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
        }

        formatMoveSummary(logEntry) {
            const move = logEntry.envelope?.move;
            const agent = logEntry.agent_id || '';
            if (!move) return logEntry.result === 'timeout' ? `${agent}: timed out` : '?';
            switch (move.type) {
                case 'press': { const n = (move.messages || []).length; return `${agent}: ${n ? n + ' cable(s)' : 'silent'}`; }
                case 'orders': {
                    const parts = Object.entries(move.orders || {}).map(([p, s]) =>
                        (s && s.support) ? `${p} S ${s.support}` : (typeof s === 'string' && s !== 'hold') ? `${p}→${s}` : `${p} H`);
                    return `${agent}: ${parts.join(', ') || 'holds'}`;
                }
                case 'retreat': return `${agent}: retreat ${Object.entries(move.retreats || {}).map(([p, d]) => `${p}→${d}`).join(', ')}`;
                case 'build': { const b = (move.builds || []).map(x => '+' + x), d = (move.disbands || []).map(x => '-' + x); return `${agent}: ${[...b, ...d].join(' ') || 'no change'}`; }
                default: return `${agent}: ${move.type}`;
            }
        }

        renderResult(result, state) {
            const ctx = this.ctx;
            ctx.fillStyle = 'rgba(10,14,28,0.84)';
            this._round(ctx, this.cx - 320, this.cy - 60, 640, 120, 12); ctx.fill();
            ctx.textAlign = 'center';
            ctx.fillStyle = C.crown; ctx.font = F(30, true);
            const w = result?.winner;
            ctx.fillText(w ? `${this._name(state, w)} wins the Wheel` : 'Stalemate — the Wheel is shared', this.cx, this.cy - 4);
            ctx.fillStyle = C.text; ctx.font = F(18);
            ctx.fillText((result?.summary || '').slice(0, 64), this.cx, this.cy + 30);
        }

        destroy() {
            if (this._raf) cancelAnimationFrame(this._raf);
            this.canvas.removeEventListener('mousemove', this._onMove);
            this.canvas.removeEventListener('mouseleave', this._onLeave);
            if (this.canvas?.parentNode) this.canvas.parentNode.removeChild(this.canvas);
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['diplomacy'] = DiplomacyRenderer;
})();
