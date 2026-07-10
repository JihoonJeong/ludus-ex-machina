/**
 * Dugout renderer (Viewer 2.0, P4) — a ballpark broadcast scoreboard.
 *
 * The prediction field's replay is a nightly sports broadcast: a YOU-vs-HOUSE
 * race bar up top, the latest game as a big reveal card (your pick flips into
 * the actual linescore with a points breakdown), a chip strip of the slate so
 * far (✓/✗ per game), and a cumulative points chart drawn on a small canvas.
 * LED-amber monospace numbers on graphite, stadium-scoreboard vibe.
 *
 * State comes straight from the engine `current`: forecasts[] (each with
 * teams / move / agent / house / actual), agent_total, house_total. Older
 * replays without `teams` fall back to HOME/AWAY labels. Win moments (exact
 * score, beating the house) burst via fx.js when present.
 */
(function () {
    'use strict';

    const C = {
        bg: '#0d0f14', panel: '#141821', border: '#2a3040', led: '#ffc94d',
        text: '#dfe3ec', muted: '#8a92b0', you: '#7fd1c0',
        house: '#e2768c', win: '#4ade80', loss: '#f87171', dim: '#3a4256',
    };

    function esc(s) {
        if (s == null) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    let injected = false;
    function injectStyles() {
        if (injected) return; injected = true;
        const css = `
        .dg-root{display:flex;flex-direction:column;height:100%;background:${C.bg};color:${C.text};font-family:'SF Mono',ui-monospace,Menlo,monospace;border:1px solid ${C.border};border-radius:6px;overflow:hidden}
        .dg-head{display:flex;align-items:center;gap:14px;padding:10px 16px;background:linear-gradient(180deg,#171b26,#12151d);border-bottom:1px solid ${C.border}}
        .dg-badge{font-size:11px;letter-spacing:1.5px;color:${C.muted};border:1px solid ${C.border};border-radius:4px;padding:3px 8px}
        .dg-race{flex:1;display:flex;flex-direction:column;gap:4px}
        .dg-race-bar{position:relative;height:14px;background:#0a0c11;border:1px solid ${C.border};border-radius:7px;overflow:hidden}
        .dg-race-you{position:absolute;top:0;left:0;bottom:0;background:linear-gradient(90deg,rgba(127,209,192,.25),${C.you});transition:width .8s cubic-bezier(.22,1,.36,1)}
        .dg-race-house{position:absolute;top:0;bottom:0;width:2px;background:${C.house};box-shadow:0 0 8px ${C.house};transition:left .8s cubic-bezier(.22,1,.36,1)}
        .dg-race-lbl{display:flex;justify-content:space-between;font-size:11px;color:${C.muted}}
        .dg-race-lbl b{color:${C.led};font-size:13px}
        .dg-race-lbl .you b{color:${C.you}} .dg-race-lbl .house b{color:${C.house}}
        .dg-main{display:flex;flex:1;min-height:0}
        .dg-card{flex:1 1 58%;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:12px;border-right:1px solid ${C.border};position:relative;overflow:hidden}
        .dg-matchup{font-size:13px;color:${C.muted};letter-spacing:1px;margin-bottom:10px}
        .dg-line{display:grid;grid-template-columns:auto 56px;gap:4px 18px;align-items:center;background:${C.panel};border:1px solid ${C.border};border-radius:10px;padding:14px 22px;box-shadow:inset 0 0 30px rgba(0,0,0,.5)}
        .dg-line .team{font-size:16px;letter-spacing:1px}
        .dg-line .runs{font-size:30px;text-align:right;color:${C.led};text-shadow:0 0 10px rgba(255,201,77,.45);font-variant-numeric:tabular-nums}
        .dg-line .win-side{color:#fff}
        .dg-pick{margin-top:10px;font-size:12.5px;color:${C.muted}}
        .dg-pick b{color:${C.you}} .dg-pick .bad{color:${C.loss}} .dg-pick .good{color:${C.win}}
        .dg-pts{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;justify-content:center}
        .dg-pt{font-size:11px;border:1px solid ${C.border};border-radius:5px;padding:3px 8px;color:${C.muted}}
        .dg-pt b{color:${C.led}}
        .dg-side{flex:1 1 42%;display:flex;flex-direction:column;min-width:0}
        .dg-chart-t{font-size:11px;letter-spacing:1.5px;color:${C.muted};padding:8px 12px 2px}
        .dg-chart{width:100%;height:118px;display:block}
        .dg-strip{flex:1;overflow-y:auto;padding:8px 12px;display:flex;flex-wrap:wrap;gap:6px;align-content:flex-start}
        .dg-chip{font-size:11px;border-radius:6px;padding:5px 8px;border:1px solid ${C.border};background:${C.panel};min-width:74px}
        .dg-chip .t{color:${C.muted};font-size:10px}
        .dg-chip .s{font-size:12.5px;color:${C.led}}
        .dg-chip.w{border-color:rgba(74,222,128,.5)} .dg-chip.w .ok{color:${C.win}}
        .dg-chip.l{border-color:rgba(248,113,113,.4)} .dg-chip.l .ok{color:${C.loss}}
        .dg-empty{color:${C.muted};font-size:13px;display:flex;align-items:center;justify-content:center;flex:1}
        .dg-fxcanvas{position:absolute;inset:0;pointer-events:none}`;
        const el = document.createElement('style');
        el.textContent = css;
        document.head.appendChild(el);
    }

    class DugoutRenderer {
        constructor(container) {
            injectStyles();
            this.container = container;
            container.style.height = '100%';
            this.root = document.createElement('div');
            this.root.className = 'dg-root';
            container.appendChild(this.root);
            this._lastRevealIdx = -1;
            this._fx = null; // lazy: {stage, particles} on first card render
        }

        initialState(matchConfig) {
            const a = (matchConfig && matchConfig.agents) || [];
            return { current: null, context: null,
                     perspective: a[0] ? a[0].agent_id : 'forecaster', turn: 0 };
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            if (!post) return state;
            return { current: post, context: logEntry.post_move_context || state.context,
                     perspective: state.perspective, turn: logEntry.turn };
        }

        render(state, turn, lastMove, animate) {
            const cur = state.current;
            if (!cur) {
                this.root.innerHTML = '<div class="dg-empty">First pitch coming up…</div>';
                return;
            }
            const ctx = state.context || {};
            const fc = cur.forecasts || [];
            const latest = fc[fc.length - 1];
            const n = ctx.n_games || fc.length || 1;
            const maxPts = n * 110;
            const youPct = Math.min(100, 100 * (cur.agent_total || 0) / maxPts);
            const housePct = Math.min(100, 100 * (cur.house_total || 0) / maxPts);

            this.root.innerHTML = `
                <div class="dg-head">
                    <div class="dg-badge">⚾ ${esc(ctx.league || 'MLB')} · ${esc(ctx.date || '')}${ctx.anon ? ' · MASKED FEED' : ''}</div>
                    <div class="dg-race">
                        <div class="dg-race-bar">
                            <div class="dg-race-you" style="width:${youPct}%"></div>
                            <div class="dg-race-house" style="left:${housePct}%"></div>
                        </div>
                        <div class="dg-race-lbl">
                            <span class="you">${esc(state.perspective)} <b>${(cur.agent_total || 0).toFixed(1)}</b></span>
                            <span>game ${Math.min(fc.length, n)} / ${n}</span>
                            <span class="house">house <b>${(cur.house_total || 0).toFixed(1)}</b></span>
                        </div>
                    </div>
                </div>
                <div class="dg-main">
                    <div class="dg-card">${latest ? this._cardHtml(latest) : '<div class="dg-empty">forecasting…</div>'}</div>
                    <div class="dg-side">
                        <div class="dg-chart-t">CUMULATIVE POINTS</div>
                        <canvas class="dg-chart"></canvas>
                        <div class="dg-strip">${fc.map((f, i) => this._chipHtml(f, i)).join('')}</div>
                    </div>
                </div>`;

            this._drawChart(fc, n);
            const strip = this.root.querySelector('.dg-strip');
            if (strip) strip.scrollTop = strip.scrollHeight;

            // celebration: exact score or newly beating the house
            if (animate && latest && window.LxMFX) {
                const idx = fc.length - 1;
                if (idx !== this._lastRevealIdx) {
                    this._lastRevealIdx = idx;
                    const card = this.root.querySelector('.dg-card');
                    if (latest.agent.exact_score_bonus > 0) this._burst(card, '255,201,77');
                    else if (latest.agent.winner_points > 0 && latest.agent.total > latest.house.total)
                        this._burst(card, '127,209,192', 46);
                }
            }
        }

        _cardHtml(f) {
            const t = f.teams || {};
            const away = t.away || 'AWAY', home = t.home || 'HOME';
            const a = f.actual, m = f.move, bd = f.agent;
            const awayWin = a.winner === 'away';
            const pickOk = bd.winner_points > 0;
            const pickTeam = m.winner === 'home' ? home : away;
            return `
                <div class="dg-matchup">${esc(t.away_starter || '')} ${t.away_starter ? '·' : ''} ${esc(away)}  @  ${esc(home)} ${t.home_starter ? '·' : ''} ${esc(t.home_starter || '')}</div>
                <div class="dg-line">
                    <span class="team ${awayWin ? 'win-side' : ''}">${esc(away)}</span><span class="runs">${a.away_score}</span>
                    <span class="team ${!awayWin ? 'win-side' : ''}">${esc(home)}</span><span class="runs">${a.home_score}</span>
                </div>
                <div class="dg-pick">pick: <b>${esc(pickTeam)}</b> ${m.away_score}-${m.home_score}
                    @${(m.confidence ?? 0.5).toFixed(2)} —
                    <span class="${pickOk ? 'good' : 'bad'}">${pickOk ? '✓ CORRECT' : '✗ WRONG'}</span></div>
                <div class="dg-pts">
                    <span class="dg-pt">winner <b>${bd.winner_points}</b></span>
                    <span class="dg-pt">score <b>${bd.score_points}</b></span>
                    ${bd.exact_score_bonus ? `<span class="dg-pt">EXACT <b>+${bd.exact_score_bonus}</b></span>` : ''}
                    <span class="dg-pt">calib <b>${bd.calibration_points}</b></span>
                    <span class="dg-pt">total <b>${bd.total}</b></span>
                    <span class="dg-pt">house <b style="color:${C.house}">${f.house.total}</b></span>
                </div>`;
        }

        _chipHtml(f, i) {
            const t = f.teams || {};
            const ok = f.agent.winner_points > 0;
            return `<div class="dg-chip ${ok ? 'w' : 'l'}">
                <div class="t">g${i + 1} ${esc(t.away || 'A')}@${esc(t.home || 'H')}</div>
                <div class="s"><span class="ok">${ok ? '✓' : '✗'}</span> ${f.agent.total} <span style="color:${C.muted}">vs</span> ${f.house.total}</div>
            </div>`;
        }

        _drawChart(fc, n) {
            const cv = this.root.querySelector('.dg-chart');
            if (!cv) return;
            const w = cv.clientWidth || 300, h = cv.clientHeight || 118;
            cv.width = w * 2; cv.height = h * 2;
            const x = cv.getContext('2d');
            x.scale(2, 2);
            x.clearRect(0, 0, w, h);
            if (!fc.length) return;
            const pad = 8;
            let ya = 0, yh = 0;
            const ptsA = [[pad, h - pad]], ptsH = [[pad, h - pad]];
            const maxY = Math.max(1, ...fc.map((_, i) =>
                fc.slice(0, i + 1).reduce((s, f) => s + Math.max(f.agent.total, f.house.total), 0)));
            fc.forEach((f, i) => {
                ya += f.agent.total; yh += f.house.total;
                const px = pad + (w - 2 * pad) * ((i + 1) / n);
                ptsA.push([px, h - pad - (h - 2 * pad) * (ya / maxY)]);
                ptsH.push([px, h - pad - (h - 2 * pad) * (yh / maxY)]);
            });
            const line = (pts, color, glow) => {
                x.beginPath();
                pts.forEach(([px, py], i) => i ? x.lineTo(px, py) : x.moveTo(px, py));
                x.strokeStyle = color; x.lineWidth = 2;
                x.shadowColor = color; x.shadowBlur = glow ? 6 : 0;
                x.stroke(); x.shadowBlur = 0;
            };
            line(ptsH, C.house, false);
            line(ptsA, C.you, true);
        }

        _burst(cardEl, color, count) {
            if (!cardEl || !window.LxMFX) return;
            let cv = cardEl.querySelector('.dg-fxcanvas');
            if (!cv) {
                cv = document.createElement('canvas');
                cv.className = 'dg-fxcanvas';
                cardEl.appendChild(cv);
                const stage = new window.LxMFX.Stage(cv);
                this._fx = { stage, particles: stage.add(new window.LxMFX.ParticleLayer(null)) };
                stage.start();
            }
            if (this._fx) this._fx.particles.burst(color, count || 80);
        }

        renderResult() { /* app-level overlay */ }

        formatMoveSummary(logEntry) {
            const m = (logEntry.envelope && logEntry.envelope.move) || {};
            if (!m.winner) return `(${logEntry.result || '?'})`;
            return `pick ${m.winner} ${m.away_score}-${m.home_score} @${m.confidence ?? '—'}`;
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['dugout'] = DugoutRenderer;
})();
