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
        return {
            world: post.world || state.world,
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

        // Pick the first agent as camera center (MVP is single-agent; multi
        // could add agent-switch UI later).
        const agentIds = Object.keys(state.agents);
        const focus = state.agents[agentIds[0]] || {x: 16, y: 16, z: 0};

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
                    this._drawAgent(ctx, p.x, p.y, aid === agentIds[0]);
                }
            }
            for (const item of state.ground_items) {
                if (item.z === z) {
                    const p = this._iso(item.x - focus.x, item.y - focus.y, z, originX, originY);
                    this._drawGroundItem(ctx, p.x, p.y, item.type, item.count);
                }
            }
        }

        // Agent trail overlay (fading).
        this._drawTrail(ctx, focus, originX, originY);

        // HUD — top-left.
        this._drawHUD(ctx, state, focus, turn, agentIds[0]);

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

    _drawAgent(ctx, sx, sy, isFocus) {
        // Agent body: lollipop, bright contrast.
        ctx.fillStyle = isFocus ? '#ffcc33' : '#66ccff';
        ctx.beginPath();
        ctx.arc(sx, sy - 4, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#1a1a1a';
        ctx.lineWidth = 1.5;
        ctx.stroke();
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

    _drawTrail(ctx, focus, originX, originY) {
        // Last N positions of focus agent, rendered as fading dots.
        const recent = this.trailHistory.slice(-20);
        const n = recent.length;
        for (let i = 0; i < n; i++) {
            const t = recent[i];
            const alpha = 0.08 + 0.5 * (i / Math.max(1, n - 1));
            const p = this._iso(t.x - focus.x, t.y - focus.y, t.z, originX, originY);
            ctx.fillStyle = `rgba(255, 204, 51, ${alpha})`;
            ctx.beginPath();
            ctx.arc(p.x, p.y - 2, 2, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    _drawHUD(ctx, state, agent, turn, agentId) {
        const pad = 12;
        const boxW = 230;
        const boxH = 118;
        ctx.fillStyle = 'rgba(20, 24, 32, 0.82)';
        ctx.fillRect(pad, pad, boxW, boxH);
        ctx.strokeStyle = '#444';
        ctx.lineWidth = 1;
        ctx.strokeRect(pad, pad, boxW, boxH);

        ctx.fillStyle = '#d4c27a';
        ctx.font = 'bold 13px sans-serif';
        ctx.fillText(`${agentId} — turn ${turn}`, pad + 10, pad + 20);

        ctx.fillStyle = '#ddd';
        ctx.font = '11px sans-serif';
        ctx.fillText(`pos (${agent.x}, ${agent.y}, ${agent.z}) facing ${agent.facing}`, pad + 10, pad + 40);
        ctx.fillText(`status: ${agent.status}`, pad + 10, pad + 56);

        ctx.fillStyle = '#aac';
        ctx.fillText('Inventory:', pad + 10, pad + 76);
        const inv = agent.inventory || {};
        const entries = Object.entries(inv);
        if (entries.length === 0) {
            ctx.fillStyle = '#666';
            ctx.fillText('  (empty)', pad + 10, pad + 92);
        } else {
            ctx.fillStyle = '#fff';
            let yy = pad + 92;
            for (const [item, count] of entries) {
                ctx.fillText(`  ${item}: ${count}`, pad + 10, yy);
                yy += 12;
            }
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
