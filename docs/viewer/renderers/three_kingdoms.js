/**
 * Three Kingdoms: Red Cliffs renderer for the LxM Match Viewer.
 *
 * Solo strategy field. Per-turn state from `post_move_state` (= engine
 * `current`): player resources / alliance / fire_ready / cao / wind / news.
 *
 * Layout: a large BEAT-ART panel (the original ai-three-kingdoms event
 * illustrations — opening, alliance sealed, chained fleet, the southeast wind,
 * fire attack, victory, defeat — switch with the campaign state) beside a
 * campaign sidebar (resources, alliance meter, wind, Cao's fleet), with an
 * event log below.
 */

(function () {
    const C = {
        bg: '#0c0e15', panel: 'rgba(15, 19, 30, 0.86)', border: '#2c3550',
        text: '#e3e6f0', muted: '#8a92b0', gold: '#d8c690', red: '#e2768c',
        flame: '#e25822', teal: '#39c6c0', green: '#4ade80',
    };
    const ART = 'assets/three_kingdoms/';

    function esc(s) {
        if (s == null) return '';
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function beatArt(cur) {
        const evs = (cur.last_events || []).join(' ');
        if (cur.won) return ['victory.webp', 'The river burns — Red Cliffs is won'];
        if (cur.lost) return ['defeat.webp', esc(cur.lost)];
        if (/fire ships (launch|strike)/i.test(evs)) return ['fire.webp', 'Fire on the river'];
        if (cur.wind === 'southeast') return ['wind.webp', 'The southeast wind blows — three days only'];
        if (cur.cao && cur.cao.chained) return ['chained.webp', "Cao Cao's ships are chained — 연환진"];
        if (cur.allied) return ['alliance.webp', 'The Sun-Liu alliance is sealed'];
        return ['opening.webp', 'Winter, 208 AD — Cao Cao marches south'];
    }

    let injected = false;
    function injectStyles() {
        if (injected) return; injected = true;
        const css = `
        .tk-root{display:flex;flex-direction:column;height:100%;background:${C.bg};color:${C.text};font-family:'SF Mono',ui-monospace,Menlo,monospace;border-radius:6px;overflow:hidden;border:1px solid ${C.border}}
        .tk-main{flex:1 1 auto;min-height:0;display:flex}
        .tk-art{flex:1 1 62%;position:relative;background-size:cover;background-position:center;border-right:1px solid ${C.border};min-width:0;overflow:hidden}
        .tk-art>*{position:relative;z-index:2}
        .tk-scenewrap{position:absolute !important;inset:0;z-index:0 !important;pointer-events:none}
        .tk-scene{position:absolute;inset:0;width:100%;height:100%}
        .tk-caption{position:absolute;left:0;right:0;bottom:0;padding:26px 14px 10px;font-size:12.5px;color:${C.gold};letter-spacing:.4px;background:linear-gradient(transparent,rgba(8,10,16,.92))}
        .tk-side{flex:0 0 38%;display:flex;flex-direction:column;background:#0a0c12;padding:10px 12px;gap:8px;overflow-y:auto}
        .tk-head{font-size:12px;color:${C.gold};letter-spacing:1.5px}
        .tk-head .t{color:${C.muted};letter-spacing:0}
        .tk-box{background:${C.panel};border:1px solid ${C.border};border-radius:8px;padding:8px 10px;font-size:11.5px;line-height:1.7}
        .tk-box h5{font-size:10px;letter-spacing:2px;color:${C.muted};margin-bottom:4px}
        .tk-stat{display:flex;justify-content:space-between}
        .tk-stat b{color:${C.text};font-weight:600}
        .tk-meter{display:block;height:5px;border-radius:3px;background:#232a3f;overflow:hidden;margin:3px 0 5px}
        .tk-meter i{display:block;height:100%}
        .tk-badge{display:inline-block;font-size:10px;letter-spacing:.5px;padding:1px 7px;border-radius:8px;margin-left:6px}
        .tk-badge.on{background:rgba(216,198,144,.18);color:${C.gold}}
        .tk-badge.warn{background:rgba(226,118,140,.16);color:${C.red}}
        .tk-badge.wind{background:rgba(57,198,192,.16);color:${C.teal}}
        .tk-log{flex:0 0 84px;overflow-y:auto;padding:7px 12px;border-top:1px solid ${C.border};background:#080a10;font-size:11.5px;line-height:1.55}
        .tk-log .t{color:${C.muted}} .tk-log .latest{background:rgba(216,198,144,.08)}
        .tk-empty{margin:auto;color:${C.muted};font-style:italic;font-size:14px;font-family:Georgia,serif}
        `;
        const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
    }

    class ThreeKingdomsRenderer {
        constructor(container) {
            injectStyles();
            this.container = container;
            container.style.aspectRatio = '8 / 5';
            container.style.height = '100%';
            this.root = document.createElement('div');
            this.root.className = 'tk-root';
            container.appendChild(this.root);

            // Cinematic scene (Viewer 2.0 P4): persistent fx canvas reparented
            // into .tk-art across re-renders — beat art gets a Ken Burns drift,
            // beat-driven particles (wind streaks / fire), typed captions, and
            // a victory ember burst. Silent fallback to static art without fx.js.
            this._fx = null;
            if (window.LxMFX) {
                const FX = window.LxMFX;
                const wrap = document.createElement('div');
                wrap.className = 'tk-scenewrap';
                wrap.innerHTML = '<canvas class="tk-scene"></canvas>';
                const stage = new FX.Stage(wrap.querySelector('canvas'));
                this._fx = {
                    FX, wrap, stage,
                    ken: stage.add(new FX.KenBurnsLayer()),
                    particles: stage.add(new FX.ParticleLayer(null)),
                    vignette: stage.add(new FX.VignetteLayer({ strength: 0.42 })),
                    art: null, preset: null, wonShown: false, tw: null,
                };
                stage.start();
            }
        }

        initialState(matchConfig) {
            const a = (matchConfig && matchConfig.agents) || [];
            return { current: null, context: null, aid: a[0] ? a[0].agent_id : '?', log: [], turn: 0 };
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            if (!post) return state;
            const log = state.log.concat([{
                turn: logEntry.turn,
                action: this.formatMoveSummary(logEntry),
                events: post.last_events || [],
            }]);
            return { current: post, context: logEntry.post_move_context || state.context,
                     aid: state.aid, log, turn: logEntry.turn };
        }

        render(state, turn, lastMove, animate) {
            const cur = state.current;
            if (!cur) {
                this.root.innerHTML = '<div class="tk-empty">Winter, 208 AD. The river waits…</div>';
                return;
            }
            const ctx = state.context || {};
            const p = cur.player || {};
            const cao = cur.cao || {};
            const [art, caption] = beatArt(cur);

            const meter = (v, color) =>
                `<span class="tk-meter"><i style="width:${Math.max(2, Math.min(100, v))}%;background:${color}"></i></span>`;

            const side = `
              <div class="tk-head">RED CLIFFS <span class="t">· turn ${Math.min(cur.turn, ctx.max_turns || 20)}/${ctx.max_turns || 20}</span></div>
              <div class="tk-box">
                <h5>SUN-LIU FORCES</h5>
                <div class="tk-stat"><span>troops</span><b>${(p.troops ?? 0).toLocaleString()}</b></div>
                <div class="tk-stat"><span>morale</span><b>${p.morale ?? 0}</b></div>${meter(p.morale ?? 0, C.green)}
                <div class="tk-stat"><span>gold / food</span><b>${p.gold ?? 0} / ${(p.food ?? 0).toLocaleString()}</b></div>
                <div class="tk-stat"><span>fortification</span><b>${p.fortification ?? 0}/3</b></div>
              </div>
              <div class="tk-box">
                <h5>THE ALLIANCE</h5>
                <div class="tk-stat"><span>Sun Quan</span><b>${cur.alliance ?? 0}/100${cur.allied ? '<span class="tk-badge on">SEALED</span>' : ''}</b></div>
                ${meter(cur.alliance ?? 0, C.gold)}
                <div class="tk-stat"><span>fire ships</span><b>${cur.fire_ready ? 'READY' : '—'}</b></div>
                <div class="tk-stat"><span>wind</span><b>${cur.wind === 'southeast'
                    ? '<span class="tk-badge wind">SOUTHEAST</span>' : 'north'}</b></div>
              </div>
              <div class="tk-box">
                <h5>CAO CAO</h5>
                ${cao.at_chibi
                    ? `<div class="tk-stat"><span>fleet at Red Cliffs</span><b>${(cao.troops ?? 0).toLocaleString()}</b></div>
                       <div class="tk-stat"><span>formation</span><b>${cao.chained ? '<span class="tk-badge warn">CHAINED 연환진</span>' : 'loose'}</b></div>`
                    : '<div>marching south…</div>'}
              </div>`;

            const logHtml = state.log.slice(-10).map((L, i, arr) => {
                const evs = (L.events || []).map(esc).join(' · ');
                return `<div class="${i === arr.length - 1 ? 'latest' : ''}"><span class="t">t${L.turn}</span> ▸ ${esc(L.action)}${evs ? ' — ' + evs : ''}</div>`;
            }).join('') || '<div class="t">(the campaign begins)</div>';

            this.root.innerHTML =
                `<div class="tk-main">
                   <div class="tk-art" style="background-image:url('${ART + art}')">
                     <div class="tk-caption">${caption}</div>
                   </div>
                   <div class="tk-side">${side}</div>
                 </div>
                 <div class="tk-log">${logHtml}</div>`;
            const logEl = this.root.querySelector('.tk-log');
            if (logEl) logEl.scrollTop = logEl.scrollHeight;

            this._updateScene(cur, art, caption, animate);
        }

        _updateScene(cur, art, caption, animate) {
            const fx = this._fx;
            if (!fx) return;
            const artEl = this.root.querySelector('.tk-art');
            if (!artEl) return;
            if (fx.wrap.parentElement !== artEl) artEl.insertBefore(fx.wrap, artEl.firstChild);
            artEl.style.backgroundImage = 'none'; // the canvas paints the art now

            // beat change → crossfade + typed caption
            if (fx.art !== art) {
                fx.art = art;
                fx.ken.show(fx.FX.loadImage(ART + art));
                const cap = this.root.querySelector('.tk-caption');
                if (cap && animate && !fx.FX.REDUCED) {
                    cap.textContent = '';
                    if (!fx.tw) fx.tw = new fx.FX.Typewriter(cap, { cps: 45 });
                    fx.tw.el = cap;
                    fx.tw.queue = [];
                    fx.tw._busy = false;
                    fx.tw.type(caption.replace(/<[^>]*>/g, ''));
                }
            }

            // beat-driven ambience
            const preset = (cur.won || /fire/.test(art)) ? 'fire'
                : (cur.wind === 'southeast') ? 'wind'
                : (cur.cao && cur.cao.at_chibi) ? 'dust' : null;
            if (fx.preset !== preset) {
                fx.preset = preset;
                fx.particles.set(preset);
                fx.vignette.warm = preset === 'fire' ? '255,120,40' : null;
                fx.vignette.strength = preset === 'fire' ? 0.55 : 0.42;
            }

            // victory: ember burst once (scrub-back aware)
            if (cur.won && !fx.wonShown) {
                fx.wonShown = true;
                fx.particles.burst('255,140,60', 120);
                setTimeout(() => fx.particles.burst('255,201,77', 80), 420);
            } else if (!cur.won && fx.wonShown) {
                fx.wonShown = false;
            }
        }

        renderResult(result, state) { /* app renders its own overlay */ }

        formatMoveSummary(logEntry) {
            const m = (logEntry.envelope && logEntry.envelope.move) || {};
            if (!m.verb) return `(${logEntry.result || '?'})`;
            return m.tactic ? `${m.verb} (${m.tactic})` : m.verb;
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['three_kingdoms'] = ThreeKingdomsRenderer;
})();
