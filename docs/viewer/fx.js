/**
 * LxM fx — the shared cinematic stage for game renderers (Viewer 2.0, P0).
 *
 * Zero-dependency Canvas-2D scene toolkit: a renderer owns one LxMFX.Stage
 * bound to a <canvas>; the stage runs a single rAF loop and composes layers:
 *
 *   KenBurnsLayer   — an image with a slow camera drift (zoom + pan), and
 *                     direction-aware crossfade to the next image
 *   ParticleLayer   — ambient systems from presets (dust / embers / fireflies /
 *                     alarm / snow) + one-shot bursts (win moments)
 *   VignetteLayer   — breathing edge darkening + warm light pulse
 *
 * Plus DOM helpers that don't need the canvas:
 *   Typewriter      — queued type-on narration with caret
 *   popIn(el)       — scale+glow entrance for map nodes etc.
 *
 * Perf guards: one rAF per stage, auto-pause when the tab is hidden or the
 * canvas leaves the DOM, everything stops on stage.destroy(). Honors
 * prefers-reduced-motion (drift/particles collapse to static render).
 */

(function () {
    'use strict';

    const REDUCED = window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // ── easing ────────────────────────────────────────────────────────────
    const Ease = {
        linear: t => t,
        inOut: t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2,
        out: t => 1 - Math.pow(1 - t, 3),
        outBack: t => 1 + 2.7 * Math.pow(t - 1, 3) + 1.7 * Math.pow(t - 1, 2),
    };

    // ── stage ─────────────────────────────────────────────────────────────
    class Stage {
        constructor(canvas) {
            this.canvas = canvas;
            this.ctx = canvas.getContext('2d');
            this.layers = [];
            this._running = false;
            this._last = 0;
            this._raf = null;
            this._tick = this._tick.bind(this);
            this._onVis = () => { document.hidden ? this._pause() : this._resume(); };
            document.addEventListener('visibilitychange', this._onVis);
        }
        add(layer) { this.layers.push(layer); return layer; }
        start() {
            if (this._running) return;
            this._running = true;
            this._last = performance.now();
            this._raf = requestAnimationFrame(this._tick);
        }
        _pause() { if (this._raf) cancelAnimationFrame(this._raf); this._raf = null; }
        _resume() { if (this._running && !this._raf) { this._last = performance.now(); this._raf = requestAnimationFrame(this._tick); } }
        _tick(now) {
            if (!this._running) return;
            // Only self-destruct after having been attached once — renderers may
            // be constructed before their container reaches the document.
            if (this.canvas.isConnected) this._wasConnected = true;
            else if (this._wasConnected) { this.destroy(); return; }
            const dt = Math.min(0.1, (now - this._last) / 1000);
            this._last = now;
            const { canvas, ctx } = this;
            // keep backing store matched to CSS size (containers resize)
            const w = canvas.clientWidth, h = canvas.clientHeight;
            if (w && h && (canvas.width !== w || canvas.height !== h)) {
                canvas.width = w; canvas.height = h;
            }
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            for (const layer of this.layers) layer.draw(ctx, canvas.width, canvas.height, dt);
            this._raf = requestAnimationFrame(this._tick);
        }
        destroy() {
            this._running = false;
            this._pause();
            document.removeEventListener('visibilitychange', this._onVis);
            this.layers = [];
        }
    }

    // ── Ken Burns image layer with crossfade ──────────────────────────────
    class KenBurnsLayer {
        constructor() {
            this.cur = null;   // {img, t0, zoomFrom, zoomTo, panX, panY, dur}
            this.prev = null;  // fading out
            this.fadeT = 1;    // 0..1 crossfade progress
            this.fadeDur = 0.9;
            this.slide = [0, 0]; // direction-aware entrance offset (px fraction)
            this._n = 0;
        }
        /** Show an image (HTMLImageElement, may still be loading). dir = 'north'|'south'|... */
        show(img, dir) {
            const DIRV = { north: [0, -1], south: [0, 1], east: [1, 0], west: [-1, 0],
                           up: [0, -1], down: [0, 1], in: [0.5, 0.5], out: [-0.5, -0.5] };
            this.prev = this.cur;
            this.fadeT = this.prev ? 0 : 1;
            const n = this._n++;
            this.cur = {
                img,
                t: 0,
                dur: 14 + (n % 3) * 3,
                zoomFrom: 1.03, zoomTo: 1.09,
                // alternate drift heading so consecutive rooms feel distinct
                panX: (n % 2 ? 1 : -1) * 0.018,
                panY: (n % 3 === 1 ? 1 : -1) * 0.012,
            };
            this.slide = (dir && DIRV[dir]) ? DIRV[dir] : [0, 0];
        }
        _drawOne(ctx, w, h, s, alpha, slideK) {
            const img = s.img;
            if (!img || !img.complete || !img.naturalWidth) return;
            const p = REDUCED ? 0 : Math.min(1, s.t / s.dur);
            const zoom = s.zoomFrom + (s.zoomTo - s.zoomFrom) * Ease.inOut(p);
            // cover-fit
            const ir = img.naturalWidth / img.naturalHeight, cr = w / h;
            let dw, dh;
            if (ir > cr) { dh = h * zoom; dw = dh * ir; } else { dw = w * zoom; dh = dw / ir; }
            const panX = w * s.panX * Ease.inOut(p), panY = h * s.panY * Ease.inOut(p);
            const slX = this.slide[0] * w * 0.04 * slideK, slY = this.slide[1] * h * 0.04 * slideK;
            ctx.save();
            ctx.globalAlpha = alpha;
            ctx.drawImage(img, (w - dw) / 2 + panX + slX, (h - dh) / 2 + panY + slY, dw, dh);
            ctx.restore();
        }
        draw(ctx, w, h, dt) {
            if (this.cur) this.cur.t += dt;
            if (this.fadeT < 1) this.fadeT = Math.min(1, this.fadeT + dt / this.fadeDur);
            const f = Ease.inOut(this.fadeT);
            if (this.prev && f < 1) this._drawOne(ctx, w, h, this.prev, 1 - f, 0);
            if (this.cur) this._drawOne(ctx, w, h, this.cur, this.prev ? f : 1, 1 - f);
            if (f >= 1) this.prev = null;
        }
    }

    // ── particles ─────────────────────────────────────────────────────────
    const PRESETS = {
        dust: { // sunlit archive motes — tower
            n: 45, size: [0.6, 1.8], alpha: [0.08, 0.3], color: '255,235,190',
            vx: [-2, 4], vy: [-3, 3], wobble: 0.6, glow: false,
        },
        embers: { // rising sparks — grimhold
            n: 34, size: [0.8, 2.4], alpha: [0.2, 0.7], color: '255,140,60',
            vx: [-4, 4], vy: [-26, -10], wobble: 1.4, glow: true, flicker: true,
        },
        fireflies: { // cove dusk
            n: 22, size: [1.2, 2.6], alpha: [0.15, 0.85], color: '190,255,150',
            vx: [-6, 6], vy: [-5, 5], wobble: 2.2, glow: true, pulse: true,
        },
        debris: { // dead-ship micro-debris — erebus
            n: 30, size: [0.5, 1.6], alpha: [0.1, 0.4], color: '170,200,255',
            vx: [-3, 3], vy: [-2, 2], wobble: 0.3, glow: false,
        },
        snow: { n: 60, size: [0.8, 2.2], alpha: [0.2, 0.6], color: '235,240,255',
                vx: [-6, 6], vy: [8, 26], wobble: 1.2, glow: false },
    };
    const rand = (a, b) => a + Math.random() * (b - a);

    class ParticleLayer {
        constructor(presetName) {
            this.set(presetName);
            this.bursts = [];
            this._t = 0;
        }
        set(presetName) {
            this.preset = PRESETS[presetName] || null;
            this.parts = [];
            if (this.preset && !REDUCED) {
                for (let i = 0; i < this.preset.n; i++) this.parts.push(this._spawn(true));
            }
        }
        _spawn(anywhere) {
            const p = this.preset;
            return {
                x: Math.random(), y: anywhere ? Math.random() : 1.05,
                vx: rand(p.vx[0], p.vx[1]) / 1000, vy: rand(p.vy[0], p.vy[1]) / 1000,
                r: rand(p.size[0], p.size[1]), a: rand(p.alpha[0], p.alpha[1]),
                ph: Math.random() * Math.PI * 2,
            };
        }
        /** One-shot celebratory burst (win moment). */
        burst(color, count) {
            if (REDUCED) return;
            const parts = [];
            for (let i = 0; i < (count || 90); i++) {
                const ang = Math.random() * Math.PI * 2, sp = rand(0.12, 0.55);
                parts.push({ x: 0.5, y: 0.55, vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp - 0.18,
                             r: rand(1, 3.2), life: 1, decay: rand(0.35, 0.7) });
            }
            this.bursts.push({ parts, color: color || '255,216,107' });
        }
        draw(ctx, w, h, dt) {
            this._t += dt;
            const p = this.preset;
            if (p && this.parts.length) {
                for (const pt of this.parts) {
                    pt.ph += dt * p.wobble;
                    pt.x += pt.vx * dt * 60 + Math.sin(pt.ph) * 0.0004;
                    pt.y += pt.vy * dt * 60;
                    if (pt.x < -0.02) pt.x = 1.02; if (pt.x > 1.02) pt.x = -0.02;
                    if (pt.y < -0.04) { Object.assign(pt, this._spawn(false)); pt.y = 1.03; }
                    if (pt.y > 1.04) { Object.assign(pt, this._spawn(false)); pt.y = -0.03; }
                    let a = pt.a;
                    if (p.pulse) a *= 0.45 + 0.55 * (0.5 + Math.sin(pt.ph * 1.7) / 2);
                    if (p.flicker) a *= 0.7 + 0.3 * Math.random();
                    ctx.beginPath();
                    ctx.arc(pt.x * w, pt.y * h, pt.r, 0, Math.PI * 2);
                    ctx.fillStyle = `rgba(${p.color},${a.toFixed(3)})`;
                    if (p.glow) { ctx.shadowColor = `rgba(${p.color},0.9)`; ctx.shadowBlur = pt.r * 4; }
                    ctx.fill();
                    ctx.shadowBlur = 0;
                }
            }
            for (let bi = this.bursts.length - 1; bi >= 0; bi--) {
                const b = this.bursts[bi];
                let alive = 0;
                for (const pt of b.parts) {
                    if (pt.life <= 0) continue;
                    alive++;
                    pt.life -= pt.decay * dt;
                    pt.vy += 0.25 * dt; // gravity
                    pt.x += pt.vx * dt; pt.y += pt.vy * dt;
                    ctx.beginPath();
                    ctx.arc(pt.x * w, pt.y * h, pt.r * Math.max(0, pt.life), 0, Math.PI * 2);
                    ctx.fillStyle = `rgba(${b.color},${Math.max(0, pt.life).toFixed(3)})`;
                    ctx.shadowColor = `rgba(${b.color},0.9)`; ctx.shadowBlur = 8;
                    ctx.fill(); ctx.shadowBlur = 0;
                }
                if (!alive) this.bursts.splice(bi, 1);
            }
        }
    }

    // ── vignette + light pulse ────────────────────────────────────────────
    class VignetteLayer {
        constructor(opts) {
            this.strength = (opts && opts.strength) || 0.55;
            this.warm = (opts && opts.warm) || null;   // e.g. '255,190,90' candle pulse
            this.alarm = (opts && opts.alarm) || null; // e.g. '255,60,50' slow red sweep
            this._t = Math.random() * 10;
        }
        draw(ctx, w, h, dt) {
            this._t += dt;
            const breathe = REDUCED ? 0 : Math.sin(this._t * 0.6) * 0.04;
            const g = ctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.38,
                                               w / 2, h / 2, Math.max(w, h) * 0.72);
            g.addColorStop(0, 'rgba(0,0,0,0)');
            g.addColorStop(1, `rgba(0,0,0,${(this.strength + breathe).toFixed(3)})`);
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, w, h);
            if (this.warm && !REDUCED) {
                const a = 0.05 + 0.03 * Math.sin(this._t * 2.3) + 0.02 * Math.sin(this._t * 5.7);
                const wg = ctx.createRadialGradient(w * 0.5, h * 0.62, 10, w * 0.5, h * 0.62, Math.max(w, h) * 0.55);
                wg.addColorStop(0, `rgba(${this.warm},${Math.max(0, a).toFixed(3)})`);
                wg.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = wg;
                ctx.fillRect(0, 0, w, h);
            }
            if (this.alarm && !REDUCED) {
                const a = Math.max(0, Math.sin(this._t * 1.1)) * 0.09;
                ctx.fillStyle = `rgba(${this.alarm},${a.toFixed(3)})`;
                ctx.fillRect(0, 0, w, h);
            }
        }
    }

    // ── typewriter (DOM) ──────────────────────────────────────────────────
    class Typewriter {
        constructor(el, opts) {
            this.el = el;
            this.cps = (opts && opts.cps) || 55;
            this.queue = [];
            this._busy = false;
        }
        type(text, cls) {
            this.queue.push({ text, cls });
            if (!this._busy) this._next();
        }
        clear() { this.queue = []; this.el.innerHTML = ''; this._busy = false; }
        _next() {
            const item = this.queue.shift();
            if (!item) { this._busy = false; return; }
            this._busy = true;
            const line = document.createElement('div');
            if (item.cls) line.className = item.cls;
            this.el.appendChild(line);
            this.el.scrollTop = this.el.scrollHeight;
            if (REDUCED) { line.textContent = item.text; this._next(); return; }
            let i = 0;
            const step = () => {
                if (!line.isConnected) { this._busy = false; return; }
                i = Math.min(item.text.length, i + Math.max(1, Math.round(this.cps / 30)));
                line.textContent = item.text.slice(0, i);
                this.el.scrollTop = this.el.scrollHeight;
                if (i < item.text.length) setTimeout(step, 1000 / 30);
                else this._next();
            };
            step();
        }
    }

    // ── DOM pop-in ────────────────────────────────────────────────────────
    function popIn(el, glowColor) {
        if (REDUCED || !el) return;
        el.style.transition = 'none';
        el.style.transform = 'scale(0.2)';
        el.style.opacity = '0';
        requestAnimationFrame(() => requestAnimationFrame(() => {
            el.style.transition = 'transform .45s cubic-bezier(.34,1.56,.64,1), opacity .3s ease-out, box-shadow .8s ease-out';
            el.style.transform = 'scale(1)';
            el.style.opacity = '1';
            if (glowColor) {
                el.style.boxShadow = `0 0 14px ${glowColor}`;
                setTimeout(() => { if (el.isConnected) el.style.boxShadow = ''; }, 900);
            }
        }));
    }

    // image cache shared by renderers
    const _imgCache = {};
    function loadImage(src) {
        if (!_imgCache[src]) {
            const img = new Image();
            img.src = src;
            _imgCache[src] = img;
        }
        return _imgCache[src];
    }

    window.LxMFX = { Stage, KenBurnsLayer, ParticleLayer, VignetteLayer,
                     Typewriter, popIn, loadImage, Ease, REDUCED };
})();
