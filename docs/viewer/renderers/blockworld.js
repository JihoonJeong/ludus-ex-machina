/**
 * Blockworld renderer for LxM Match Viewer.
 *
 * Draws a 2.5D voxel world as an isometric projection. Each block cell
 * renders as a colored parallelogram diamond; higher layers are drawn
 * on top with a z-offset. The agent is highlighted; their path trail
 * fades over recent turns.
 *
 * Per-turn state is pulled from `post_move_state` (the LxM orchestrator
 * records the full world + agents + ground_items + last_events there).
 */
class BlockworldRenderer {
    constructor(containerElement) {
        this.container = containerElement;
        this.canvas = document.createElement('canvas');
        // Target display ~800×640 — will be scaled to fit.
        this.canvas.width = 1600;
        this.canvas.height = 1280;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.background = '#0f1115';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.ctx.scale(2, 2);

        // Iso projection constants. Tile footprint in px (pre-scale).
        this.tileW = 16;   // half-width of diamond
        this.tileH = 8;    // half-height of diamond
        this.zStep = 12;   // vertical pixel offset per layer up
        this.viewportRadius = 14;  // render radius around agent (cells)

        // Block colors (sides + top shading applied at draw time).
        this.blockColors = {
            air: null,  // not drawn
            stone: '#8a8a8a',
            dirt: '#7a5a3a',
            grass: '#6a9a4a',
            wood: '#8a5a2a',
            water: '#3a6a9a',
            sand: '#d4c27a',
            iron_ore: '#a89080',
            glass: 'rgba(200, 230, 255, 0.55)',
        };

        // Remember past agent positions for trail.
        this.trailHistory = [];
    }

    initialState(matchConfig) {
        return {
            world: null,    // will fill from first log entry's post_move_state
            agents: {},
            ground_items: [],
            last_events: [],
            turn: 0,
        };
    }

    applyMove(state, logEntry) {
        const post = logEntry.post_move_state;
        if (!post) return state;
        // Track agent trail (position history) for fading path overlay.
        if (post.agents) {
            for (const aid in post.agents) {
                const a = post.agents[aid];
                this.trailHistory.push({
                    agent: aid, turn: logEntry.turn,
                    x: a.x, y: a.y, z: a.z,
                });
            }
        }
        // Keep last 30 positions per agent.
        if (this.trailHistory.length > 300) {
            this.trailHistory = this.trailHistory.slice(-300);
        }
        // Merge world state: full `layers` on first turn, cumulative
        // `layer_diffs` on subsequent turns (see export_static.strip_log).
        // Server mode always ships layers; static mode ships layers on the
        // first turn and diffs thereafter.
        let world = state.world;
        if (post.world) {
            if (post.world.layers) {
                world = post.world;
            } else if (world && world.layers && Array.isArray(post.world.layer_diffs)) {
                // Clone layers (outer + inner z-arrays) and apply diffs.
                const newLayers = world.layers.map(layer => layer.map(row => row.slice()));
                for (const d of post.world.layer_diffs) {
                    const [x, y, z, v] = d;
                    if (newLayers[z] && newLayers[z][y]) {
                        newLayers[z][y][x] = v;
                    }
                }
                world = {
                    ...world,
                    ...post.world,
                    layers: newLayers,
                };
                delete world.layer_diffs;
            } else {
                // No layers and no diffs — reuse previous world's layers.
                world = {
                    ...world,
                    ...post.world,
                    layers: world?.layers,
                };
                delete world.layer_diffs;
            }
            if (post.world.placed) world.placed = post.world.placed;
        }
        return {
            world,
            agents: post.agents || {},
            ground_items: post.ground_items || [],
            last_events: post.last_events || [],
            turn: logEntry.turn,
        };
    }

    render(state, turn, lastMove, animate) {
        const W = this.canvas.width / 2;   // logical space after scale(2,2)
        const H = this.canvas.height / 2;
        const ctx = this.ctx;
        ctx.clearRect(0, 0, W, H);

        if (!state.world) {
            ctx.fillStyle = '#aaa';
            ctx.font = '14px sans-serif';
            ctx.fillText('Waiting for first turn…', 20, 30);
            return;
        }

        // Camera follows the active agent when available, so playback
        // tracks whoever just moved. Fall back to first agent for
        // scenarios without turn_order (e.g. very early replay).
        const turnOrder = state.turn_order && state.turn_order.length
            ? state.turn_order
            : Object.keys(state.agents);
        const activeIdx = Number.isInteger(state.active_index)
            ? ((state.active_index - 1 + turnOrder.length) % turnOrder.length)
            : 0;
        const activeId = turnOrder[activeIdx] || turnOrder[0];
        const focus = state.agents[activeId] || {x: 16, y: 16, z: 0};
        const agentColors = this._agentColors(turnOrder);

        // Iso origin (center of canvas).
        const originX = W * 0.5;
        const originY = H * 0.38;

        // Render cells in painter's order: low z → high z, and within layer,
        // far-to-near (large x+y first from camera perspective).
        const dims = state.world.dimensions;
        const xMin = Math.max(0, focus.x - this.viewportRadius);
        const xMax = Math.min(dims.x - 1, focus.x + this.viewportRadius);
        const yMin = Math.max(0, focus.y - this.viewportRadius);
        const yMax = Math.min(dims.y - 1, focus.y + this.viewportRadius);

        for (let z = 0; z < dims.z; z++) {
            for (let y = yMin; y <= yMax; y++) {
                for (let x = xMin; x <= xMax; x++) {
                    const blockId = state.world.layers[z][y][x];
                    const blockName = this._blockName(state.world, blockId);
                    if (blockName === 'air') continue;
                    const placed = state.world.placed[z][y][x] === 1;
                    const p = this._iso(x - focus.x, y - focus.y, z, originX, originY);
                    this._drawBlock(ctx, p.x, p.y, blockName, placed);
                }
            }
            // After each layer, draw agents + items that live at this layer.
            for (const aid in state.agents) {
                const a = state.agents[aid];
                if (a.z === z) {
                    const p = this._iso(a.x - focus.x, a.y - focus.y, z, originX, originY);
                    this._drawAgent(ctx, p.x, p.y, aid === activeId, agentColors[aid] || '#66ccff', aid);
                }
            }
            for (const item of state.ground_items) {
                if (item.z === z) {
                    const p = this._iso(item.x - focus.x, item.y - focus.y, z, originX, originY);
                    this._drawGroundItem(ctx, p.x, p.y, item.type, item.count);
                }
            }
        }

        // Agent trail overlay (fading) — per-agent color.
        this._drawTrail(ctx, focus, originX, originY, agentColors);

        // HUD — top-left. Shows all agents; active one highlighted.
        this._drawHUD(ctx, state, focus, turn, activeId, turnOrder, agentColors);

        // Events panel — bottom-left.
        this._drawEvents(ctx, state.last_events, H);
    }

    renderResult(result, state) {
        const ctx = this.ctx;
        const W = this.canvas.width / 2;
        const H = this.canvas.height / 2;
        const box = {x: W * 0.25, y: H * 0.35, w: W * 0.5, h: 90};
        ctx.fillStyle = 'rgba(15, 17, 21, 0.85)';
        ctx.fillRect(box.x, box.y, box.w, box.h);
        ctx.strokeStyle = '#d4c27a';
        ctx.lineWidth = 2;
        ctx.strokeRect(box.x, box.y, box.w, box.h);
        ctx.fillStyle = '#d4c27a';
        ctx.font = 'bold 18px sans-serif';
        ctx.fillText(`Outcome: ${result.outcome}`, box.x + 14, box.y + 26);
        ctx.fillStyle = '#eee';
        ctx.font = '12px sans-serif';
        const summary = (result.summary || '').slice(0, 120);
        ctx.fillText(summary, box.x + 14, box.y + 50);
        if (result.validity) {
            ctx.fillText(
                `Volume: ${result.validity.volume}, floor: ${result.validity.floor_area}, placed blocks: ${result.placed_blocks}`,
                box.x + 14, box.y + 70
            );
        }
    }

    formatMoveSummary(entry) {
        const move = entry.envelope?.move;
        if (!move) return `${entry.agent_id}: (${entry.result})`;
        const v = move.verb || '?';
        const d = move.direction ? ` ${move.direction}` : '';
        const b = move.block ? ` ${move.block}` : '';
        return `${entry.agent_id}: ${v}${d}${b}`;
    }

    // ── helpers ──────────────────────────────────────────────────────────

    _blockName(world, id) {
        // Canonical list mirroring games/blockworld/world.py BLOCK_TYPES.
        const names = ['air', 'stone', 'dirt', 'grass', 'wood', 'water', 'sand', 'iron_ore', 'glass'];
        return names[id] || 'air';
    }

    _iso(dx, dy, z, originX, originY) {
        // (dx, dy) are cell offsets from focus. Iso projection:
        //   sx = (dx - dy) * tileW
        //   sy = (dx + dy) * tileH  - z * zStep
        return {
            x: originX + (dx - dy) * this.tileW,
            y: originY + (dx + dy) * this.tileH - z * this.zStep,
        };
    }

    _drawBlock(ctx, sx, sy, blockName, placed) {
        const color = this.blockColors[blockName];
        if (!color) return;
        const tw = this.tileW;
        const th = this.tileH;
        const zh = this.zStep;  // block's apparent vertical extent

        // Left face (darker).
        ctx.fillStyle = this._shade(color, -0.25);
        ctx.beginPath();
        ctx.moveTo(sx - tw, sy);
        ctx.lineTo(sx, sy + th);
        ctx.lineTo(sx, sy + th + zh);
        ctx.lineTo(sx - tw, sy + zh);
        ctx.closePath();
        ctx.fill();

        // Right face (medium).
        ctx.fillStyle = this._shade(color, -0.05);
        ctx.beginPath();
        ctx.moveTo(sx + tw, sy);
        ctx.lineTo(sx, sy + th);
        ctx.lineTo(sx, sy + th + zh);
        ctx.lineTo(sx + tw, sy + zh);
        ctx.closePath();
        ctx.fill();

        // Top face (brightest + placed-by-agent outline).
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(sx, sy - th);
        ctx.lineTo(sx + tw, sy);
        ctx.lineTo(sx, sy + th);
        ctx.lineTo(sx - tw, sy);
        ctx.closePath();
        ctx.fill();

        if (placed) {
            ctx.strokeStyle = '#e6c55a';
            ctx.lineWidth = 1.2;
            ctx.stroke();
        }
    }

    _drawAgent(ctx, sx, sy, isFocus, color, agentId) {
        // Agent body: lollipop in its assigned color. Active agent
        // gets a gold halo so the viewer immediately spots whose
        // turn just resolved.
        if (isFocus) {
            ctx.fillStyle = 'rgba(255, 204, 51, 0.35)';
            ctx.beginPath();
            ctx.arc(sx, sy - 4, 9, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.fillStyle = color || '#66ccff';
        ctx.beginPath();
        ctx.arc(sx, sy - 4, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#1a1a1a';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        if (agentId) {
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 9px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText((agentId[0] || '?').toUpperCase(), sx, sy - 2);
            ctx.textAlign = 'left';
        }
    }

    _drawGroundItem(ctx, sx, sy, type, count) {
        ctx.fillStyle = this._shade(this.blockColors[type] || '#ccc', 0.2);
        ctx.beginPath();
        ctx.rect(sx - 3, sy + 2, 6, 6);
        ctx.fill();
        ctx.font = '9px sans-serif';
        ctx.fillStyle = '#fff';
        ctx.fillText(`×${count}`, sx + 4, sy + 2);
    }

    _drawTrail(ctx, focus, originX, originY, agentColors) {
        // Last N positions per agent, each in its own color.
        const recent = this.trailHistory.slice(-60);
        // Group by agent so fade windows are independent.
        const byAgent = {};
        for (const t of recent) {
            (byAgent[t.agent] = byAgent[t.agent] || []).push(t);
        }
        for (const aid of Object.keys(byAgent)) {
            const ts = byAgent[aid].slice(-20);
            const n = ts.length;
            const rgb = this._hexToRgb(agentColors?.[aid] || '#ffcc33');
            for (let i = 0; i < n; i++) {
                const t = ts[i];
                const alpha = 0.08 + 0.5 * (i / Math.max(1, n - 1));
                const p = this._iso(t.x - focus.x, t.y - focus.y, t.z, originX, originY);
                ctx.fillStyle = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
                ctx.beginPath();
                ctx.arc(p.x, p.y - 2, 2, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    _agentColors(turnOrder) {
        const palette = [
            '#ffcc33', // gold (a)
            '#66ccff', // blue (b)
            '#77dd77', // green (c)
            '#ff6b9d', // pink (d)
        ];
        const out = {};
        turnOrder.forEach((aid, i) => {
            out[aid] = palette[i % palette.length];
        });
        return out;
    }

    _hexToRgb(hex) {
        const m = /^#([0-9a-f]{6})$/i.exec(hex);
        if (!m) return {r: 255, g: 204, b: 51};
        const n = parseInt(m[1], 16);
        return {r: (n >> 16) & 0xff, g: (n >> 8) & 0xff, b: n & 0xff};
    }

    _drawHUD(ctx, state, focus, turn, activeId, turnOrder, agentColors) {
        const pad = 12;
        const boxW = 260;
        const rowH = 56;
        const headerH = 28;
        const boxH = headerH + rowH * (turnOrder?.length || 1) + 8;
        ctx.fillStyle = 'rgba(20, 24, 32, 0.82)';
        ctx.fillRect(pad, pad, boxW, boxH);
        ctx.strokeStyle = '#444';
        ctx.lineWidth = 1;
        ctx.strokeRect(pad, pad, boxW, boxH);

        ctx.fillStyle = '#d4c27a';
        ctx.font = 'bold 13px sans-serif';
        ctx.fillText(`turn ${turn}`, pad + 10, pad + 20);

        let yy = pad + headerH;
        for (const aid of turnOrder || []) {
            const a = state.agents[aid];
            if (!a) continue;
            const isActive = aid === activeId;
            const color = agentColors?.[aid] || '#66ccff';
            // Color swatch
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(pad + 18, yy + 10, 5, 0, Math.PI * 2);
            ctx.fill();
            // Agent id + active marker
            ctx.fillStyle = isActive ? '#ffcc33' : '#ddd';
            ctx.font = isActive ? 'bold 12px sans-serif' : '12px sans-serif';
            ctx.fillText(
                `${aid}${isActive ? ' ◀' : ''}`,
                pad + 30, yy + 14
            );
            // Position / status
            ctx.fillStyle = '#aac';
            ctx.font = '10px sans-serif';
            ctx.fillText(
                `(${a.x},${a.y},${a.z}) ${a.facing} · ${a.status}`,
                pad + 30, yy + 28
            );
            // Inventory brief
            const inv = a.inventory || {};
            const entries = Object.entries(inv);
            const invStr = entries.length === 0
                ? '(empty)'
                : entries.map(([k, v]) => `${k}×${v}`).join(' ');
            ctx.fillStyle = '#fff';
            ctx.fillText(`inv: ${invStr.slice(0, 32)}`, pad + 30, yy + 42);
            yy += rowH;
        }
    }

    _drawEvents(ctx, events, H) {
        if (!events || events.length === 0) return;
        const pad = 12;
        const boxW = 260;
        const boxH = Math.min(80, 16 + events.length * 14);
        const top = H - pad - boxH;
        ctx.fillStyle = 'rgba(20, 24, 32, 0.82)';
        ctx.fillRect(pad, top, boxW, boxH);
        ctx.strokeStyle = '#444';
        ctx.strokeRect(pad, top, boxW, boxH);
        ctx.fillStyle = '#d4c27a';
        ctx.font = 'bold 11px sans-serif';
        ctx.fillText('Recent events', pad + 8, top + 16);
        ctx.fillStyle = '#ddd';
        ctx.font = '10px monospace';
        let yy = top + 30;
        for (const e of events.slice(-4)) {
            ctx.fillText(`· ${String(e).slice(0, 56)}`, pad + 8, yy);
            yy += 13;
        }
    }

    _shade(color, amount) {
        // amount > 0 lightens, < 0 darkens.
        if (color.startsWith('rgba')) return color;  // glass: leave as is
        const m = color.match(/^#([0-9a-f]{6})$/i);
        if (!m) return color;
        const r = parseInt(m[1].slice(0, 2), 16);
        const g = parseInt(m[1].slice(2, 4), 16);
        const b = parseInt(m[1].slice(4, 6), 16);
        const adj = (v) => Math.max(0, Math.min(255, Math.round(v + amount * 255)));
        return `rgb(${adj(r)}, ${adj(g)}, ${adj(b)})`;
    }
}

window.LxMRenderers = window.LxMRenderers || {};
window.LxMRenderers['blockworld'] = BlockworldRenderer;
