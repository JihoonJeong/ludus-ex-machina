/**
 * Blockworld 3D renderer (Viewer 2.0, P3) — a real voxel scene in Three.js.
 *
 * Takes over the 'blockworld' slot when WebGL is available; the classic
 * isometric canvas renderer stays registered as 'blockworld2d' and a corner
 * toggle (persisted in localStorage.lxm_bw_mode) switches modes.
 *
 * Scene: instanced voxel terrain (per-block-type InstancedMesh with a little
 * per-instance color jitter), hemisphere sky + shadowed sun, depth fog,
 * Minecraft-ish agent figurines (body+head, name sprite) that LERP between
 * turns, substrate props (trees with apples, the stag, ground items that bob
 * and spin), a hand-rolled orbit camera (drag = rotate, wheel = zoom) that
 * follows the agents' centroid, and a typed subtitle strip for last_events
 * (uses LxMFX.Typewriter when fx.js is present).
 *
 * Contract-identical to the 2D renderer: initialState / applyMove / render.
 * applyMove's world/layer_diff merge mirrors blockworld.js exactly.
 */
(function () {
    'use strict';

    const BLOCK_NAMES = ['air', 'stone', 'dirt', 'grass', 'wood', 'water', 'sand',
                         'iron_ore', 'glass', 'ladder', 'planks', 'stone_brick'];
    const BLOCK_COLORS = {
        stone: 0x8a8a8a, dirt: 0x7a5a3a, grass: 0x6a9a4a, wood: 0x8a5a2a,
        water: 0x3a6a9a, sand: 0xd4c27a, iron_ore: 0xa89080, glass: 0xc8e6ff,
        ladder: 0xa07840, planks: 0xc69a4f, stone_brick: 0x9aa0a8,
    };
    const AGENT_PALETTE = [0xffd86b, 0x7fd1c0, 0xe2768c, 0xcda6e8, 0x7fe0a0, 0xf0b86e];

    function webglOK() {
        try {
            const c = document.createElement('canvas');
            return !!(window.WebGLRenderingContext &&
                (c.getContext('webgl2') || c.getContext('webgl')));
        } catch (e) { return false; }
    }

    class Blockworld3DRenderer {
        constructor(container) {
            this.container = container;
            container.style.position = 'relative';
            container.style.height = '100%';
            container.style.minHeight = '420px';

            const T = window.THREE;
            this.T = T;
            this.renderer = new T.WebGLRenderer({ antialias: true });
            this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
            this.renderer.shadowMap.enabled = true;
            this.renderer.shadowMap.type = T.PCFSoftShadowMap;
            this.renderer.domElement.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;border-radius:6px';
            container.appendChild(this.renderer.domElement);

            this.scene = new T.Scene();
            this.scene.background = new T.Color(0x0f1115);
            this.scene.fog = new T.Fog(0x0f1115, 46, 92);

            this.camera = new T.PerspectiveCamera(46, 1, 0.1, 300);

            // lights
            const hemi = new T.HemisphereLight(0xbdd4ff, 0x33291f, 0.85);
            this.scene.add(hemi);
            const sun = new T.DirectionalLight(0xfff2d8, 1.5);
            sun.position.set(18, 30, 12);
            sun.castShadow = true;
            sun.shadow.mapSize.set(2048, 2048);
            const S = 30;
            sun.shadow.camera.left = -S; sun.shadow.camera.right = S;
            sun.shadow.camera.top = S; sun.shadow.camera.bottom = -S;
            sun.shadow.camera.far = 120;
            sun.shadow.bias = -0.0004;
            this.scene.add(sun);
            this._sun = sun;

            // orbit state (spherical around a followed focus point)
            this.orbit = { theta: -Math.PI / 4, phi: 0.96, radius: 24 };
            this.focus = new T.Vector3(16, 1, 16);
            this._focusTarget = this.focus.clone();
            this._bindControls();

            // world groups
            this.worldGroup = new T.Group();
            this.scene.add(this.worldGroup);
            this.propGroup = new T.Group();
            this.scene.add(this.propGroup);
            this.agentGroup = new T.Group();
            this.scene.add(this.agentGroup);
            this._agents = {};       // id -> {group, target(Vector3), color}
            this._lastLayers = null;
            this._itemMeshes = [];

            // subtitle overlay (typed narration)
            this.sub = document.createElement('div');
            this.sub.style.cssText =
                'position:absolute;left:0;right:0;bottom:10px;text-align:center;' +
                'font:13.5px Georgia,serif;color:#efe6c8;pointer-events:none;' +
                'text-shadow:0 1px 3px #000,0 0 12px rgba(0,0,0,.8);max-height:64px;overflow:hidden;z-index:3';
            container.appendChild(this.sub);
            this.tw = (window.LxMFX && new window.LxMFX.Typewriter(this.sub, { cps: 60 })) || null;

            // 2D/3D toggle
            const btn = document.createElement('button');
            btn.textContent = '2D';
            btn.title = 'Switch to the classic isometric renderer';
            btn.style.cssText =
                'position:absolute;top:10px;right:10px;z-index:4;background:rgba(9,10,18,.8);' +
                'border:1px solid #3a3f63;color:#8a8fb0;border-radius:6px;padding:3px 10px;' +
                'font:12px ui-monospace,monospace;cursor:pointer';
            btn.onclick = () => { localStorage.setItem('lxm_bw_mode', '2d'); location.reload(); };
            container.appendChild(btn);

            // hint (fades out)
            const hint = document.createElement('div');
            hint.textContent = 'drag to orbit · wheel to zoom';
            hint.style.cssText =
                'position:absolute;top:12px;left:14px;z-index:3;color:#8a8fb0;' +
                'font:11.5px ui-monospace,monospace;opacity:.85;transition:opacity 1s;pointer-events:none';
            container.appendChild(hint);
            setTimeout(() => { hint.style.opacity = '0'; }, 5000);

            // size + loop
            this._resize = this._resize.bind(this);
            this._ro = new ResizeObserver(this._resize);
            this._ro.observe(container);
            this._resize();
            this._clock = new T.Clock();
            this._loop = this._loop.bind(this);
            this._raf = requestAnimationFrame(this._loop);
        }

        // ── controls ────────────────────────────────────────────────────────
        _bindControls() {
            const el = this.renderer.domElement;
            let dragging = false, px = 0, py = 0;
            el.style.cursor = 'grab';
            el.addEventListener('mousedown', (e) => { dragging = true; px = e.clientX; py = e.clientY; el.style.cursor = 'grabbing'; });
            window.addEventListener('mousemove', (e) => {
                if (!dragging) return;
                this.orbit.theta -= (e.clientX - px) * 0.0055;
                this.orbit.phi = Math.min(1.42, Math.max(0.25, this.orbit.phi - (e.clientY - py) * 0.004));
                px = e.clientX; py = e.clientY;
            });
            window.addEventListener('mouseup', () => { dragging = false; el.style.cursor = 'grab'; });
            el.addEventListener('wheel', (e) => {
                e.preventDefault();
                this.orbit.radius = Math.min(70, Math.max(10, this.orbit.radius * (1 + e.deltaY * 0.001)));
            }, { passive: false });
        }

        _resize() {
            const w = this.container.clientWidth, h = this.container.clientHeight;
            if (!w || !h) return;
            this.renderer.setSize(w, h, false);
            this.camera.aspect = w / h;
            this.camera.updateProjectionMatrix();
        }

        _loop() {
            // The app may construct the renderer BEFORE attaching the container
            // to the document — only self-destruct once we've been connected
            // and then removed (view switched), never on the pre-attach race.
            const el = this.renderer.domElement;
            if (el.isConnected) this._wasConnected = true;
            else if (this._wasConnected) { this._destroy(); return; }
            const dt = Math.min(0.1, this._clock.getDelta());
            if (!document.hidden) {
                // follow focus, lerp agents, bob items
                this.focus.lerp(this._focusTarget, Math.min(1, dt * 3));
                for (const id in this._agents) {
                    const a = this._agents[id];
                    a.group.position.lerp(a.target, Math.min(1, dt * 5));
                    a.group.rotation.y += (a.rotTarget - a.group.rotation.y) * Math.min(1, dt * 6);
                }
                const t = performance.now() / 1000;
                for (const m of this._itemMeshes) {
                    m.position.y = m.userData.baseY + Math.sin(t * 2 + m.userData.ph) * 0.12;
                    m.rotation.y = t * 1.2 + m.userData.ph;
                }
                this._updateCamera();
                this.renderer.render(this.scene, this.camera);
            }
            this._raf = requestAnimationFrame(this._loop);
        }

        _updateCamera() {
            const { theta, phi, radius } = this.orbit;
            this.camera.position.set(
                this.focus.x + radius * Math.sin(phi) * Math.cos(theta),
                this.focus.y + radius * Math.cos(phi),
                this.focus.z + radius * Math.sin(phi) * Math.sin(theta));
            this.camera.lookAt(this.focus);
            this._sun.target.position.copy(this.focus);
            this._sun.target.updateMatrixWorld();
        }

        /** One synchronous frame — keeps the canvas truthful even when rAF is
         *  frozen (hidden/occluded tab) or while scrubbing with animate=false. */
        _paintOnce(settle) {
            if (settle) {
                this.focus.copy(this._focusTarget);
                for (const id in this._agents) {
                    const a = this._agents[id];
                    a.group.position.copy(a.target);
                    a.group.rotation.y = a.rotTarget;
                }
            }
            this._updateCamera();
            this.renderer.render(this.scene, this.camera);
        }

        _destroy() {
            cancelAnimationFrame(this._raf);
            if (this._ro) this._ro.disconnect();
            this.renderer.dispose();
        }

        // ── contract ────────────────────────────────────────────────────────
        initialState(matchConfig) {
            this.matchConfig = matchConfig || null;
            return { world: null, agents: {}, ground_items: [], last_events: [],
                     trees: null, stag: null, chase: null, meet: null, pd: null,
                     navigate: null, turn: 0 };
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            if (!post) return state;
            let world = state.world;
            if (post.world) {
                if (post.world.layers) {
                    world = post.world;
                } else if (world && world.layers && Array.isArray(post.world.layer_diffs)) {
                    const newLayers = world.layers.map(layer => layer.map(row => row.slice()));
                    for (const d of post.world.layer_diffs) {
                        const [x, y, z, v] = d;
                        if (newLayers[z] && newLayers[z][y]) newLayers[z][y][x] = v;
                    }
                    world = { ...world, ...post.world, layers: newLayers };
                    delete world.layer_diffs;
                } else {
                    world = { ...world, ...post.world, layers: world?.layers };
                    delete world.layer_diffs;
                }
                if (post.world.placed) world.placed = post.world.placed;
            }
            return {
                world,
                agents: post.agents || {},
                ground_items: post.ground_items || [],
                last_events: post.last_events || [],
                trees: post.trees ?? state.trees ?? null,
                stag: post.stag ?? state.stag ?? null,
                chase: post.chase ?? state.chase ?? null,
                meet: post.meet ?? state.meet ?? null,
                pd: post.pd ?? state.pd ?? null,
                navigate: post.navigate ?? state.navigate ?? null,
                turn_order: post.turn_order ?? state.turn_order,
                active_index: post.active_index ?? state.active_index,
                turn: logEntry.turn,
            };
        }

        render(state, turn, lastMove, animate) {
            if (!state.world || !state.world.layers) return;
            if (this._lastLayers !== state.world.layers) {
                this._lastLayers = state.world.layers;
                this._rebuildWorld(state.world);
            }
            this._syncProps(state);
            this._syncAgents(state, animate);

            // focus = centroid of agents (matches the 2D renderer's framing rule)
            const ids = Object.keys(state.agents);
            if (ids.length) {
                let sx = 0, sy = 0, sz = 0;
                for (const id of ids) { const a = state.agents[id]; sx += a.x; sy += (a.z || 0); sz += a.y; }
                this._focusTarget.set(sx / ids.length, sy / ids.length + 0.8, sz / ids.length);
            }

            if (animate && this.tw && state.last_events && state.last_events.length) {
                if (this.sub.childElementCount > 2) this.sub.innerHTML = '';
                for (const e of state.last_events.slice(0, 2)) this.tw.type(String(e));
            }

            // always leave a truthful frame on the canvas; when not animating
            // (scrub / initial jump), also settle agents+camera instantly
            this._paintOnce(!animate);
        }

        // ── world build ─────────────────────────────────────────────────────
        _rebuildWorld(world) {
            const T = this.T;
            this.worldGroup.clear();
            const dims = world.dimensions || { x: 32, y: 32, z: 3 };
            const layers = world.layers, placed = world.placed;
            const byType = {};
            for (let z = 0; z < Math.min(dims.z, layers.length); z++) {
                for (let y = 0; y < dims.y; y++) {
                    for (let x = 0; x < dims.x; x++) {
                        const id = layers[z][y][x];
                        if (!id) continue;
                        const name = BLOCK_NAMES[id] || 'stone';
                        (byType[name] = byType[name] || []).push([x, z, y, placed && placed[z] && placed[z][y] && placed[z][y][x] === 1]);
                    }
                }
            }
            const geo = new T.BoxGeometry(1, 1, 1);
            const tmp = new T.Object3D();
            const col = new T.Color();
            for (const name in byType) {
                const cells = byType[name];
                const base = BLOCK_COLORS[name] || 0x8a8a8a;
                const mat = new T.MeshLambertMaterial({
                    color: 0xffffff,
                    transparent: name === 'water' || name === 'glass',
                    opacity: name === 'water' ? 0.8 : (name === 'glass' ? 0.45 : 1),
                });
                const mesh = new T.InstancedMesh(geo, mat, cells.length);
                mesh.castShadow = name !== 'water';
                mesh.receiveShadow = true;
                for (let i = 0; i < cells.length; i++) {
                    const [x, h, y, isPlaced] = cells[i];
                    const squash = name === 'water' ? 0.85 : 1;
                    tmp.position.set(x, h + squash / 2 - 0.5 + (name === 'water' ? -0.07 : 0), y);
                    tmp.scale.set(1, squash, 1);
                    tmp.updateMatrix();
                    mesh.setMatrixAt(i, tmp.matrix);
                    // organic per-instance shade jitter; placed blocks glow warmer
                    col.setHex(base);
                    const j = 0.92 + ((x * 7 + y * 13 + h * 29) % 10) * 0.016;
                    col.multiplyScalar(j);
                    if (isPlaced) col.lerp(new T.Color(0xffd86b), 0.28);
                    mesh.setColorAt(i, col);
                }
                if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
                this.worldGroup.add(mesh);
            }
        }

        // ── props: trees / stag / ground items ──────────────────────────────
        _syncProps(state) {
            const T = this.T;
            this.propGroup.clear();
            this._itemMeshes = [];
            if (Array.isArray(state.trees)) {
                for (const t of state.trees) {
                    const g = new T.Group();
                    const trunk = new T.Mesh(new T.CylinderGeometry(0.16, 0.2, 1.1, 6),
                                             new T.MeshLambertMaterial({ color: 0x6a4426 }));
                    trunk.position.y = 0.55; trunk.castShadow = true;
                    const crown = new T.Mesh(new T.IcosahedronGeometry(0.62, 0),
                                             new T.MeshLambertMaterial({ color: 0x3e7a34 }));
                    crown.position.y = 1.35; crown.castShadow = true;
                    g.add(trunk, crown);
                    const apples = t.apples ?? t.fruit ?? 0;
                    for (let i = 0; i < Math.min(6, apples); i++) {
                        const a = new T.Mesh(new T.SphereGeometry(0.09, 6, 6),
                                             new T.MeshLambertMaterial({ color: 0xe23b3b, emissive: 0x551111 }));
                        const ang = i * 1.05;
                        a.position.set(Math.cos(ang) * 0.5, 1.25 + (i % 3) * 0.22, Math.sin(ang) * 0.5);
                        g.add(a);
                    }
                    g.position.set(t.x, (t.z || 1), t.y);
                    this.propGroup.add(g);
                }
            }
            if (state.stag && state.stag.x != null && state.stag.alive !== false) {
                const s = new T.Group();
                const body = new T.Mesh(new T.BoxGeometry(0.9, 0.5, 0.45),
                                        new T.MeshLambertMaterial({ color: 0x7a5230 }));
                body.position.y = 0.55; body.castShadow = true;
                const head = new T.Mesh(new T.BoxGeometry(0.3, 0.3, 0.3),
                                        new T.MeshLambertMaterial({ color: 0x8a6238 }));
                head.position.set(0.55, 0.85, 0);
                s.add(body, head);
                s.position.set(state.stag.x, (state.stag.z || 1), state.stag.y);
                this.propGroup.add(s);
            }
            for (const it of (state.ground_items || [])) {
                const m = new T.Mesh(new T.BoxGeometry(0.26, 0.26, 0.26),
                                     new T.MeshLambertMaterial({ color: 0xffd86b, emissive: 0x403008 }));
                m.position.set(it.x, (it.z || 1) + 0.35, it.y);
                m.userData = { baseY: m.position.y, ph: (it.x || 0) * 1.7 };
                m.castShadow = true;
                this.propGroup.add(m);
                this._itemMeshes.push(m);
            }
        }

        // ── agents ──────────────────────────────────────────────────────────
        _syncAgents(state, animate) {
            const T = this.T;
            const order = state.turn_order || Object.keys(state.agents);
            order.forEach((id, idx) => {
                const a = state.agents[id];
                if (!a) return;
                if (!this._agents[id]) {
                    const color = AGENT_PALETTE[idx % AGENT_PALETTE.length];
                    const g = new T.Group();
                    const body = new T.Mesh(new T.BoxGeometry(0.5, 0.62, 0.34),
                                            new T.MeshLambertMaterial({ color }));
                    body.position.y = 0.63; body.castShadow = true;
                    const head = new T.Mesh(new T.BoxGeometry(0.4, 0.4, 0.4),
                                            new T.MeshLambertMaterial({ color: 0xf2d4b0 }));
                    head.position.y = 1.16; head.castShadow = true;
                    const brim = new T.Mesh(new T.BoxGeometry(0.44, 0.12, 0.44),
                                            new T.MeshLambertMaterial({ color }));
                    brim.position.y = 1.4;
                    g.add(body, head, brim, this._nameSprite(id, color));
                    this.agentGroup.add(g);
                    this._agents[id] = { group: g, target: new T.Vector3(), rotTarget: 0, color };
                    g.position.set(a.x, (a.z || 1), a.y);
                }
                const rec = this._agents[id];
                rec.target.set(a.x, (a.z || 1), a.y);
                const FACING = { north: Math.PI, south: 0, east: Math.PI / 2, west: -Math.PI / 2 };
                if (a.facing in FACING) rec.rotTarget = FACING[a.facing];
                if (!animate) rec.group.position.copy(rec.target);
            });
            // remove agents no longer present
            for (const id in this._agents) {
                if (!state.agents[id]) {
                    this.agentGroup.remove(this._agents[id].group);
                    delete this._agents[id];
                }
            }
        }

        _nameSprite(name, colorHex) {
            const T = this.T;
            const c = document.createElement('canvas');
            c.width = 256; c.height = 64;
            const x = c.getContext('2d');
            x.font = 'bold 30px ui-monospace, monospace';
            x.textAlign = 'center';
            const col = '#' + colorHex.toString(16).padStart(6, '0');
            x.fillStyle = 'rgba(10,11,18,0.72)';
            const w = x.measureText(name).width + 26;
            x.beginPath();
            x.roundRect((256 - w) / 2, 8, w, 44, 10);
            x.fill();
            x.fillStyle = col;
            x.fillText(name, 128, 40);
            const tex = new T.CanvasTexture(c);
            const sp = new T.Sprite(new T.SpriteMaterial({ map: tex, depthTest: false }));
            sp.scale.set(2.2, 0.55, 1);
            sp.position.y = 1.95;
            return sp;
        }

        renderResult() { /* the app draws its own result overlay */ }

        formatMoveSummary(logEntry) {
            const m = (logEntry.envelope && logEntry.envelope.move) || {};
            return [m.action || m.verb, m.direction, m.item, m.target,
                    m.say ? `"${m.say}"` : null].filter(Boolean).join(' ');
        }
    }

    // ── registration: 3D takes the slot when possible ───────────────────────
    window.LxMRenderers = window.LxMRenderers || {};
    const classic = window.LxMRenderers['blockworld'];
    if (classic) window.LxMRenderers['blockworld2d'] = classic;
    const want2d = localStorage.getItem('lxm_bw_mode') === '2d';
    if (window.THREE && webglOK() && !want2d) {
        window.LxMRenderers['blockworld'] = Blockworld3DRenderer;
    } else if (want2d && classic && window.THREE && webglOK()) {
        // classic stays, but grows a "3D" button to come back
        class ClassicWithToggle extends classic {
            constructor(container) {
                super(container);
                container.style.position = 'relative';
                const b = document.createElement('button');
                b.textContent = '3D';
                b.title = 'Switch to the voxel 3D renderer';
                b.style.cssText =
                    'position:absolute;top:10px;right:10px;z-index:4;background:rgba(9,10,18,.8);' +
                    'border:1px solid #3a3f63;color:#8a8fb0;border-radius:6px;padding:3px 10px;' +
                    'font:12px ui-monospace,monospace;cursor:pointer';
                b.onclick = () => { localStorage.removeItem('lxm_bw_mode'); location.reload(); };
                container.appendChild(b);
            }
        }
        window.LxMRenderers['blockworld'] = ClassicWithToggle;
    }
})();
