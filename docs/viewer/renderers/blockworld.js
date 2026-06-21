/**
 * Blockworld renderer for LxM Match Viewer.
 *
 * Draws a 2.5D voxel world as an isometric projection. Each block cell
 * renders as a colored parallelogram diamond; higher layers are drawn
 * on top with a z-offset. Substrate-aware overlays render trees,
 * stag, ground items by type, speech bubbles, event flashes, and a
 * scenario-specific status panel.
 *
 * Per-turn state is pulled from `post_move_state` (the LxM orchestrator
 * records the full world + agents + ground_items + last_events +
 * substrate-specific fields like trees/stag/chase/meet/pd/navigate).
 */
class BlockworldRenderer {
    constructor(containerElement) {
        this.container = containerElement;
        this.canvas = document.createElement('canvas');
        this.canvas.width = 1600;
        this.canvas.height = 1280;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.background = '#0f1115';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.ctx.scale(2, 2);

        // Iso projection constants. Tile footprint in px (pre-scale).
        this.tileW = 16;
        this.tileH = 8;
        this.zStep = 12;
        this.viewportRadius = 14;

        // Block palette — full BLOCK_TYPES coverage (world.py id 0..11).
        this.blockColors = {
            air: null,
            stone: '#8a8a8a',
            dirt: '#7a5a3a',
            grass: '#6a9a4a',
            wood: '#8a5a2a',
            water: '#3a6a9a',
            sand: '#d4c27a',
            iron_ore: '#a89080',
            glass: 'rgba(200, 230, 255, 0.55)',
            ladder: '#a07840',
            planks: '#c69a4f',
            stone_brick: '#9aa0a8',
        };

        this.trailHistory = [];
        this.matchConfig = null;
        // Track last-seen events to drive 1-turn flash cues.
        this._flash = null;  // {kind, ttl}
    }

    initialState(matchConfig) {
        this.matchConfig = matchConfig || null;
        this.trailHistory = [];
        this._flash = null;
        return {
            world: null,
            agents: {},
            ground_items: [],
            last_events: [],
            trees: null,
            stag: null,
            chase: null,
            meet: null,
            pd: null,
            navigate: null,
            turn: 0,
        };
    }

    applyMove(state, logEntry) {
        const post = logEntry.post_move_state;
        if (!post) return state;

        // Trail: keep last 30 positions per agent.
        if (post.agents) {
            for (const aid in post.agents) {
                const a = post.agents[aid];
                this.trailHistory.push({
                    agent: aid, turn: logEntry.turn,
                    x: a.x, y: a.y, z: a.z,
                });
            }
        }
        if (this.trailHistory.length > 300) {
            this.trailHistory = this.trailHistory.slice(-300);
        }

        // World layers: full or diff-merged.
        let world = state.world;
        if (post.world) {
            if (post.world.layers) {
                world = post.world;
            } else if (world && world.layers && Array.isArray(post.world.layer_diffs)) {
                const newLayers = world.layers.map(layer => layer.map(row => row.slice()));
                for (const d of post.world.layer_diffs) {
                    const [x, y, z, v] = d;
                    if (newLayers[z] && newLayers[z][y]) {
                        newLayers[z][y][x] = v;
                    }
                }
                world = { ...world, ...post.world, layers: newLayers };
                delete world.layer_diffs;
            } else {
                world = { ...world, ...post.world, layers: world?.layers };
                delete world.layer_diffs;
            }
            if (post.world.placed) world.placed = post.world.placed;
        }

        // Compute event-driven flash for this turn.
        this._flash = this._detectFlash(post.last_events || [], post);

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
        const W = this.canvas.width / 2;
        const H = this.canvas.height / 2;
        const ctx = this.ctx;
        ctx.clearRect(0, 0, W, H);

        if (!state.world) {
            ctx.fillStyle = '#aaa';
            ctx.font = '14px sans-serif';
            ctx.fillText('Waiting for first turn…', 20, 30);
            return;
        }

        const turnOrder = state.turn_order && state.turn_order.length
            ? state.turn_order
            : Object.keys(state.agents);
        const activeIdx = Number.isInteger(state.active_index)
            ? ((state.active_index - 1 + turnOrder.length) % turnOrder.length)
            : 0;
        const activeId = turnOrder[activeIdx] || turnOrder[0];
        // Camera focus = centroid of ALL agents, so every creature in a shared
        // world stays framed at once. (Was the active agent — that snapped the
        // camera to whoever just moved and pushed a far-apart partner off-screen,
        // e.g. PD seats the two ~15 cells apart on a 24×24 grid, beyond
        // viewportRadius, so the view alternated one creature per turn.) Solo
        // (1 agent) => centroid is that agent, unchanged; the active agent is
        // still highlighted separately via `activeId`.
        const focusIds = Object.keys(state.agents);
        let focus;
        if (focusIds.length) {
            const sum = focusIds.reduce((a, id) => {
                const ag = state.agents[id];
                return {x: a.x + ag.x, y: a.y + ag.y, z: a.z + (ag.z || 0)};
            }, {x: 0, y: 0, z: 0});
            focus = {x: Math.round(sum.x / focusIds.length),
                     y: Math.round(sum.y / focusIds.length),
                     z: Math.round(sum.z / focusIds.length)};
        } else {
            focus = {x: 16, y: 16, z: 0};
        }
        const agentColors = this._agentColors(turnOrder);

        const originX = W * 0.5;
        const originY = H * 0.40;

        const dims = state.world.dimensions;
        const xMin = Math.max(0, focus.x - this.viewportRadius);
        const xMax = Math.min(dims.x - 1, focus.x + this.viewportRadius);
        const yMin = Math.max(0, focus.y - this.viewportRadius);
        const yMax = Math.min(dims.y - 1, focus.y + this.viewportRadius);

        // ── Painter's order: low z → high z; in each layer, far-to-near.
        for (let z = 0; z < dims.z; z++) {
            for (let y = yMin; y <= yMax; y++) {
                for (let x = xMin; x <= xMax; x++) {
                    const blockId = state.world.layers[z][y][x];
                    const blockName = this._blockName(blockId);
                    if (blockName === 'air') continue;
                    const placed = state.world.placed[z][y][x] === 1;
                    const p = this._iso(x - focus.x, y - focus.y, z, originX, originY);
                    this._drawBlock(ctx, p.x, p.y, blockName, placed);
                }
            }
            // Trees (commons_harvest) — leafy crown + apple count above wood.
            if (Array.isArray(state.trees)) {
                for (const t of state.trees) {
                    if (t.z !== z) continue;
                    if (t.x < xMin || t.x > xMax || t.y < yMin || t.y > yMax) continue;
                    const p = this._iso(t.x - focus.x, t.y - focus.y, z, originX, originY);
                    this._drawTree(ctx, p.x, p.y, t);
                }
            }
            // Stag (stag_hunt) — golden silhouette if alive.
            if (state.stag && !state.stag.captured && state.stag.z === z) {
                if (state.stag.x >= xMin && state.stag.x <= xMax
                    && state.stag.y >= yMin && state.stag.y <= yMax) {
                    const p = this._iso(state.stag.x - focus.x, state.stag.y - focus.y, z, originX, originY);
                    this._drawStag(ctx, p.x, p.y);
                }
            }
            // Ground items (apple/hare/mushroom/tokens) at this layer.
            for (const item of state.ground_items) {
                if (item.z === z) {
                    const p = this._iso(item.x - focus.x, item.y - focus.y, z, originX, originY);
                    this._drawGroundItem(ctx, p.x, p.y, item.type, item.count);
                }
            }
            // Agents at this layer.
            for (const aid in state.agents) {
                const a = state.agents[aid];
                if (a.z === z) {
                    const p = this._iso(a.x - focus.x, a.y - focus.y, z, originX, originY);
                    this._drawAgent(ctx, p.x, p.y, aid === activeId, agentColors[aid] || '#66ccff', aid, a.facing);
                }
            }
        }

        // Trail overlay.
        this._drawTrail(ctx, focus, originX, originY, agentColors);

        // Speech bubbles for "X says: ..." in this turn's events.
        this._drawSpeechBubbles(ctx, state, focus, originX, originY, agentColors);

        // Mode detection — purely state-derived, independent of matchConfig.
        const mode = this._detectMode(state);

        // HUDs.
        this._drawHUD(ctx, state, focus, turn, activeId, turnOrder, agentColors);
        this._drawGoalPanel(ctx, W, mode);
        this._drawSubstratePanel(ctx, W, H, state, mode);
        this._drawCompass(ctx, W, focus);
        this._drawLegend(ctx, W, H, state, mode);
        this._drawEvents(ctx, state.last_events, H);

        // Event flash border (1-turn highlight).
        this._drawEventFlash(ctx, W, H);
    }

    renderResult(result, state) {
        const ctx = this.ctx;
        const W = this.canvas.width / 2;
        const H = this.canvas.height / 2;
        const box = {x: W * 0.22, y: H * 0.32, w: W * 0.56, h: 110};
        ctx.fillStyle = 'rgba(15, 17, 21, 0.92)';
        ctx.fillRect(box.x, box.y, box.w, box.h);
        ctx.strokeStyle = '#d4c27a';
        ctx.lineWidth = 2;
        ctx.strokeRect(box.x, box.y, box.w, box.h);
        ctx.fillStyle = '#d4c27a';
        ctx.font = 'bold 18px sans-serif';
        ctx.fillText(`Outcome: ${result.outcome}`, box.x + 14, box.y + 26);
        ctx.fillStyle = '#eee';
        ctx.font = '12px sans-serif';
        const summary = (result.summary || '').slice(0, 160);
        const lines = this._wrap(ctx, summary, box.w - 28);
        let yy = box.y + 50;
        for (const ln of lines.slice(0, 3)) {
            ctx.fillText(ln, box.x + 14, yy);
            yy += 16;
        }
        if (result.validity) {
            ctx.fillStyle = '#aac';
            ctx.fillText(
                `volume: ${result.validity.volume}, floor: ${result.validity.floor_area}, placed: ${result.placed_blocks}`,
                box.x + 14, box.y + box.h - 14
            );
        }
    }

    formatMoveSummary(entry) {
        const move = entry.envelope?.move;
        if (!move) return `${entry.agent_id}: (${entry.result})`;
        const v = move.verb || '?';
        const d = move.direction ? ` ${move.direction}` : '';
        const b = move.block ? ` ${move.block}` : '';
        const r = move.recipe ? ` [${move.recipe}]` : '';
        const m = move.message ? ` "${String(move.message).slice(0, 24)}"` : '';
        return `${entry.agent_id}: ${v}${d}${b}${r}${m}`;
    }

    // ── helpers: world ─────────────────────────────────────────────────

    _blockName(id) {
        const names = ['air', 'stone', 'dirt', 'grass', 'wood', 'water', 'sand', 'iron_ore', 'glass', 'ladder', 'planks', 'stone_brick'];
        return names[id] || 'air';
    }

    _iso(dx, dy, z, originX, originY) {
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
        const zh = this.zStep;

        // Left face.
        ctx.fillStyle = this._shade(color, -0.25);
        ctx.beginPath();
        ctx.moveTo(sx - tw, sy);
        ctx.lineTo(sx, sy + th);
        ctx.lineTo(sx, sy + th + zh);
        ctx.lineTo(sx - tw, sy + zh);
        ctx.closePath();
        ctx.fill();

        // Right face.
        ctx.fillStyle = this._shade(color, -0.05);
        ctx.beginPath();
        ctx.moveTo(sx + tw, sy);
        ctx.lineTo(sx, sy + th);
        ctx.lineTo(sx, sy + th + zh);
        ctx.lineTo(sx + tw, sy + zh);
        ctx.closePath();
        ctx.fill();

        // Top face.
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(sx, sy - th);
        ctx.lineTo(sx + tw, sy);
        ctx.lineTo(sx, sy + th);
        ctx.lineTo(sx - tw, sy);
        ctx.closePath();
        ctx.fill();

        // Block-specific texture overlays.
        if (blockName === 'ladder') {
            // Three rungs on the right face for visual cue.
            ctx.strokeStyle = this._shade(color, -0.45);
            ctx.lineWidth = 1;
            for (let i = 1; i <= 3; i++) {
                const ry = sy + (zh * i) / 4;
                ctx.beginPath();
                ctx.moveTo(sx + 2, ry + 2);
                ctx.lineTo(sx + tw - 2, ry + (tw - 4) / 2 + 2);
                ctx.stroke();
            }
        } else if (blockName === 'planks') {
            // Two horizontal grain lines on top face.
            ctx.strokeStyle = this._shade(color, -0.30);
            ctx.lineWidth = 0.8;
            for (let i = 1; i <= 2; i++) {
                const ty = sy - th + (th * i) / 1.5;
                ctx.beginPath();
                ctx.moveTo(sx - tw + 3, ty);
                ctx.lineTo(sx + tw - 3, ty);
                ctx.stroke();
            }
        } else if (blockName === 'stone_brick') {
            // Brick mortar lines on top face.
            ctx.strokeStyle = this._shade(color, -0.35);
            ctx.lineWidth = 0.6;
            ctx.beginPath();
            ctx.moveTo(sx - tw / 2, sy - th / 2);
            ctx.lineTo(sx + tw / 2, sy + th / 2);
            ctx.moveTo(sx, sy - th);
            ctx.lineTo(sx, sy + th);
            ctx.stroke();
        } else if (blockName === 'iron_ore') {
            // Specks for ore.
            ctx.fillStyle = this._shade(color, -0.4);
            for (let i = 0; i < 3; i++) {
                ctx.beginPath();
                ctx.arc(sx + (i - 1) * 4, sy - 1 + (i % 2) * 2, 1.2, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        if (placed) {
            ctx.strokeStyle = '#e6c55a';
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(sx, sy - th);
            ctx.lineTo(sx + tw, sy);
            ctx.lineTo(sx, sy + th);
            ctx.lineTo(sx - tw, sy);
            ctx.closePath();
            ctx.stroke();
        }
    }

    // ── helpers: agents ────────────────────────────────────────────────

    _drawAgent(ctx, sx, sy, isFocus, color, agentId, facing) {
        const idx = this._agentIndex(agentId);
        const archetype = this._characterArchetypes[idx % this._characterArchetypes.length];
        const cy = sy - 6;  // body center
        // Focus halo.
        if (isFocus) {
            ctx.fillStyle = 'rgba(255, 204, 51, 0.32)';
            ctx.beginPath();
            ctx.arc(sx, cy, 13, 0, Math.PI * 2);
            ctx.fill();
        }
        // Shadow at feet.
        ctx.fillStyle = 'rgba(0,0,0,0.30)';
        ctx.beginPath();
        ctx.ellipse(sx, sy + 4, 6, 2, 0, 0, Math.PI * 2);
        ctx.fill();

        // Body — torso lozenge in agent color.
        ctx.fillStyle = color || '#66ccff';
        ctx.strokeStyle = '#1a1a1a';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.ellipse(sx, cy + 1, 4, 5, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Head — base circle.
        const headY = cy - 5;
        ctx.fillStyle = this._shade(color || '#ccc', 0.18);
        ctx.beginPath();
        ctx.arc(sx, headY, 3.6, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#1a1a1a';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Archetype-specific accessory drawn over the head.
        this._drawArchetypeAccessory(ctx, sx, headY, archetype, color);

        // Facing eye-dot (small black dot offset toward facing direction).
        const fv = {north: [0, -0.6], south: [0, 0.7], east: [1, 0.2], west: [-1, 0.2]}[facing] || [0, 0.2];
        ctx.fillStyle = '#1a1a1a';
        ctx.beginPath();
        ctx.arc(sx + fv[0] * 1.6, headY + fv[1] * 1.6, 0.9, 0, Math.PI * 2);
        ctx.fill();

        // Agent letter on torso (high-contrast).
        if (agentId) {
            ctx.fillStyle = this._textOn(color);
            ctx.font = 'bold 7px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText((agentId[0] || '?').toUpperCase(), sx, cy + 2);
            ctx.textBaseline = 'alphabetic';
            ctx.textAlign = 'left';
        }
    }

    _drawArchetypeAccessory(ctx, sx, hy, archetype, color) {
        const dark = '#1a1a1a';
        const accent = this._shade(color || '#ccc', -0.30);
        ctx.strokeStyle = dark;
        ctx.lineWidth = 1;
        switch (archetype) {
            case 'knight': {
                // Visor band across head.
                ctx.fillStyle = dark;
                ctx.fillRect(sx - 3.2, hy - 0.8, 6.4, 1.4);
                // Plume nub.
                ctx.fillStyle = accent;
                ctx.fillRect(sx - 0.6, hy - 5.2, 1.2, 1.6);
                break;
            }
            case 'mage': {
                // Tall pointy hat.
                ctx.fillStyle = accent;
                ctx.beginPath();
                ctx.moveTo(sx - 4, hy - 2);
                ctx.lineTo(sx, hy - 8);
                ctx.lineTo(sx + 4, hy - 2);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();
                // Star tip.
                ctx.fillStyle = '#ffeb88';
                ctx.beginPath();
                ctx.arc(sx, hy - 8, 1, 0, Math.PI * 2);
                ctx.fill();
                break;
            }
            case 'hooded': {
                // Pointed hood drape (down-pointing triangle wrapping head).
                ctx.fillStyle = accent;
                ctx.beginPath();
                ctx.moveTo(sx - 4.5, hy - 3);
                ctx.lineTo(sx + 4.5, hy - 3);
                ctx.lineTo(sx + 5, hy + 2);
                ctx.lineTo(sx, hy + 4);
                ctx.lineTo(sx - 5, hy + 2);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();
                // Dark face shadow inside hood.
                ctx.fillStyle = 'rgba(0,0,0,0.35)';
                ctx.beginPath();
                ctx.arc(sx, hy + 0.3, 2.6, 0, Math.PI * 2);
                ctx.fill();
                break;
            }
            case 'crown': {
                // 3-spike crown.
                ctx.fillStyle = '#ffd84a';
                ctx.beginPath();
                ctx.moveTo(sx - 3.5, hy - 3);
                ctx.lineTo(sx - 3, hy - 6);
                ctx.lineTo(sx - 1.5, hy - 4);
                ctx.lineTo(sx, hy - 6.5);
                ctx.lineTo(sx + 1.5, hy - 4);
                ctx.lineTo(sx + 3, hy - 6);
                ctx.lineTo(sx + 3.5, hy - 3);
                ctx.closePath();
                ctx.fill();
                ctx.strokeStyle = '#8a6a10';
                ctx.stroke();
                break;
            }
            case 'cat': {
                // Two triangular ears.
                ctx.fillStyle = accent;
                ctx.beginPath();
                ctx.moveTo(sx - 3.6, hy - 2.6);
                ctx.lineTo(sx - 2.4, hy - 5.8);
                ctx.lineTo(sx - 1.4, hy - 2.4);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(sx + 1.4, hy - 2.4);
                ctx.lineTo(sx + 2.4, hy - 5.8);
                ctx.lineTo(sx + 3.6, hy - 2.6);
                ctx.closePath();
                ctx.fill();
                ctx.stroke();
                // Inner ear pink.
                ctx.fillStyle = '#ff9ab8';
                ctx.beginPath();
                ctx.moveTo(sx - 2.9, hy - 3.0); ctx.lineTo(sx - 2.4, hy - 4.6); ctx.lineTo(sx - 2.0, hy - 3.0); ctx.closePath();
                ctx.fill();
                ctx.beginPath();
                ctx.moveTo(sx + 2.0, hy - 3.0); ctx.lineTo(sx + 2.4, hy - 4.6); ctx.lineTo(sx + 2.9, hy - 3.0); ctx.closePath();
                ctx.fill();
                break;
            }
            case 'tophat': {
                // Brim + cylinder.
                ctx.fillStyle = '#1a1a1a';
                ctx.fillRect(sx - 4, hy - 3, 8, 0.9);
                ctx.fillRect(sx - 2.4, hy - 7, 4.8, 4);
                // Band.
                ctx.fillStyle = accent;
                ctx.fillRect(sx - 2.4, hy - 4.2, 4.8, 0.8);
                break;
            }
            case 'horned': {
                // Round helm + two upward-curving horns.
                ctx.fillStyle = accent;
                ctx.beginPath();
                ctx.arc(sx, hy - 0.5, 3.6, Math.PI, 0);
                ctx.fill();
                ctx.stroke();
                ctx.strokeStyle = '#e9e6d8';
                ctx.lineWidth = 1.4;
                ctx.beginPath();
                ctx.moveTo(sx - 3, hy - 2.4);
                ctx.quadraticCurveTo(sx - 5.5, hy - 4.5, sx - 4.2, hy - 6.6);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(sx + 3, hy - 2.4);
                ctx.quadraticCurveTo(sx + 5.5, hy - 4.5, sx + 4.2, hy - 6.6);
                ctx.stroke();
                break;
            }
            case 'plumed': {
                // Round cap + tall feather plume curving back.
                ctx.fillStyle = accent;
                ctx.beginPath();
                ctx.arc(sx, hy - 1.4, 3.4, Math.PI, 0);
                ctx.fill();
                ctx.stroke();
                // Feather.
                ctx.fillStyle = '#5fbf6a';
                ctx.beginPath();
                ctx.moveTo(sx + 0.5, hy - 4);
                ctx.quadraticCurveTo(sx + 3, hy - 9, sx + 1, hy - 11);
                ctx.quadraticCurveTo(sx - 0.5, hy - 8, sx - 0.5, hy - 4);
                ctx.closePath();
                ctx.fill();
                ctx.strokeStyle = '#2a5a2a';
                ctx.lineWidth = 0.6;
                ctx.stroke();
                break;
            }
            default:
                break;
        }
    }

    _drawCharacterIcon(ctx, sx, sy, idx, color) {
        // Compact 14×14 character preview for HUDs and legends.
        const archetype = this._characterArchetypes[idx % this._characterArchetypes.length];
        // Body.
        ctx.fillStyle = color;
        ctx.strokeStyle = '#1a1a1a';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.ellipse(sx, sy + 1, 3.2, 4, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        // Head.
        ctx.fillStyle = this._shade(color, 0.18);
        ctx.beginPath();
        ctx.arc(sx, sy - 4, 2.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        // Accessory (smaller scale).
        this._drawArchetypeAccessory(ctx, sx, sy - 4, archetype, color);
    }

    _agentColors(turnOrder) {
        const out = {};
        turnOrder.forEach((aid, i) => {
            const idx = this._agentIndex(aid, i);
            out[aid] = this._characterPalette[idx % this._characterPalette.length];
        });
        return out;
    }

    _agentIndex(agentId, fallbackIdx) {
        // Stable per-agent index. Single-letter IDs (a/b/c/d/e/f/g/h)
        // map to 0..7 directly so character/color stay consistent across
        // matches. Multi-char IDs hash by character codes.
        if (!agentId) return fallbackIdx || 0;
        const c = agentId.toLowerCase().charCodeAt(0);
        if (c >= 97 && c <= 122) return (c - 97) % this._characterArchetypes.length;
        let h = 0;
        for (const ch of agentId) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
        return h % this._characterArchetypes.length;
    }

    get _characterArchetypes() {
        // Index 0..7 → archetype id used by _drawArchetypeAccessory.
        return ['knight', 'mage', 'hooded', 'crown', 'cat', 'tophat', 'horned', 'plumed'];
    }

    get _characterPalette() {
        // Hand-tuned for max distinguishability against grass/stone/dirt
        // bases. Index aligns with _characterArchetypes.
        return [
            '#ffcc33', // knight  — gold
            '#66ccff', // mage    — sky blue
            '#77dd77', // hooded  — mint
            '#ff6b9d', // crown   — pink
            '#c89cff', // cat     — lavender
            '#ffaa66', // tophat  — peach
            '#66e6c0', // horned  — teal
            '#f06868', // plumed  — coral red
        ];
    }

    _textOn(color) {
        // Choose readable letter color for an agent body in `color`.
        if (!color || !color.startsWith('#')) return '#fff';
        const m = color.match(/^#([0-9a-f]{6})$/i);
        if (!m) return '#fff';
        const r = parseInt(m[1].slice(0, 2), 16);
        const g = parseInt(m[1].slice(2, 4), 16);
        const b = parseInt(m[1].slice(4, 6), 16);
        const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        return lum > 0.6 ? '#1a1a1a' : '#fff';
    }

    // ── helpers: substrate-specific items ──────────────────────────────

    _drawGroundItem(ctx, sx, sy, type, count) {
        const cy = sy + 4;
        switch (type) {
            case 'apple': {
                ctx.fillStyle = '#d24545';
                ctx.beginPath(); ctx.arc(sx, cy, 3.4, 0, Math.PI * 2); ctx.fill();
                ctx.fillStyle = '#5a8a3a';
                ctx.fillRect(sx - 0.6, cy - 4.5, 1.2, 1.6);
                ctx.strokeStyle = '#6a1a1a'; ctx.lineWidth = 0.6; ctx.stroke();
                break;
            }
            case 'hare': {
                ctx.fillStyle = '#a08566';
                ctx.beginPath(); ctx.ellipse(sx, cy + 1, 4, 2.6, 0, 0, Math.PI * 2); ctx.fill();
                // Ears.
                ctx.fillRect(sx - 2, cy - 3.5, 1, 3);
                ctx.fillRect(sx + 1, cy - 3.5, 1, 3);
                ctx.fillStyle = '#fff';
                ctx.beginPath(); ctx.arc(sx + 3.5, cy + 1, 1, 0, Math.PI * 2); ctx.fill();
                break;
            }
            case 'public_mushroom': {
                this._drawMushroom(ctx, sx, cy, '#f5d24a', '#fff8d0');
                break;
            }
            case 'selfish_mushroom': {
                this._drawMushroom(ctx, sx, cy, '#c64545', '#fff');
                break;
            }
            case 'mushroom': {
                this._drawMushroom(ctx, sx, cy, '#9a7af5', '#e0d0ff');
                break;
            }
            case 'coop_token': {
                this._drawTokenDiamond(ctx, sx, cy, '#5fbf6a', 'C');
                break;
            }
            case 'defect_token': {
                this._drawTokenDiamond(ctx, sx, cy, '#d24545', 'D');
                break;
            }
            default: {
                ctx.fillStyle = this._shade(this.blockColors[type] || '#bbb', 0.15);
                ctx.fillRect(sx - 3, cy, 6, 6);
                ctx.strokeStyle = '#222'; ctx.lineWidth = 0.6; ctx.strokeRect(sx - 3, cy, 6, 6);
            }
        }
        if (count && count > 1) {
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 8px sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(`×${count}`, sx + 5, cy + 2);
        }
    }

    _drawMushroom(ctx, cx, cy, capColor, dotColor) {
        // Stem.
        ctx.fillStyle = '#e8e0c8';
        ctx.fillRect(cx - 1.2, cy - 1, 2.4, 4);
        // Cap.
        ctx.fillStyle = capColor;
        ctx.beginPath();
        ctx.arc(cx, cy - 1, 3.4, Math.PI, 0);
        ctx.closePath();
        ctx.fill();
        // Dots.
        ctx.fillStyle = dotColor;
        ctx.beginPath(); ctx.arc(cx - 1.4, cy - 1.6, 0.8, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 1.4, cy - 2.0, 0.8, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath(); ctx.arc(cx + 0.2, cy - 0.8, 0.7, 0, Math.PI * 2); ctx.fill();
    }

    _drawTokenDiamond(ctx, cx, cy, color, letter) {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(cx, cy - 4);
        ctx.lineTo(cx + 4, cy);
        ctx.lineTo(cx, cy + 4);
        ctx.lineTo(cx - 4, cy);
        ctx.closePath();
        ctx.fill();
        ctx.strokeStyle = this._shade(color, -0.35);
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 7px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(letter, cx, cy + 0.3);
        ctx.textBaseline = 'alphabetic';
        ctx.textAlign = 'left';
    }

    _drawTree(ctx, sx, sy, tree) {
        // Crown (canopy) above the wood block.
        const crownY = sy - this.zStep - 2;
        const dead = !!tree.dead;
        const crownFill = dead ? '#5a544a' : '#3e7a3e';
        const crownEdge = dead ? '#3a342a' : '#2a5a2a';
        ctx.fillStyle = crownFill;
        ctx.beginPath();
        ctx.arc(sx - 4, crownY, 5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath();
        ctx.arc(sx + 4, crownY, 5, 0, Math.PI * 2); ctx.fill();
        ctx.beginPath();
        ctx.arc(sx, crownY - 4, 6, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = crownEdge;
        ctx.lineWidth = 0.8;
        ctx.stroke();
        // Apples on crown.
        const apples = Math.max(0, Math.min(5, tree.apples || 0));
        const appleSpots = [
            [sx - 4, crownY - 1], [sx + 4, crownY - 1], [sx, crownY - 6],
            [sx - 6, crownY + 2], [sx + 6, crownY + 2],
        ];
        ctx.fillStyle = '#d24545';
        for (let i = 0; i < apples; i++) {
            const [ax, ay] = appleSpots[i];
            ctx.beginPath(); ctx.arc(ax, ay, 1.4, 0, Math.PI * 2); ctx.fill();
        }
        // Apple count badge.
        if (!dead && (tree.apples ?? 0) > 0) {
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 9px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`${tree.apples}`, sx, crownY + 4);
            ctx.textAlign = 'left';
        }
        if (dead) {
            ctx.fillStyle = '#888';
            ctx.font = '8px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('†', sx, crownY + 4);
            ctx.textAlign = 'left';
        }
    }

    _drawStag(ctx, sx, sy) {
        const cy = sy - 2;
        // Body.
        ctx.fillStyle = '#a07a3a';
        ctx.beginPath();
        ctx.ellipse(sx, cy, 7, 4, 0, 0, Math.PI * 2);
        ctx.fill();
        // Head.
        ctx.beginPath();
        ctx.arc(sx + 5, cy - 3, 2.6, 0, Math.PI * 2);
        ctx.fill();
        // Antlers.
        ctx.strokeStyle = '#5a3a1a';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(sx + 5, cy - 5); ctx.lineTo(sx + 3, cy - 9);
        ctx.moveTo(sx + 5, cy - 5); ctx.lineTo(sx + 7, cy - 9);
        ctx.moveTo(sx + 3, cy - 9); ctx.lineTo(sx + 1, cy - 11);
        ctx.moveTo(sx + 7, cy - 9); ctx.lineTo(sx + 9, cy - 11);
        ctx.stroke();
        // Legs.
        ctx.strokeStyle = '#7a5520';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(sx - 4, cy + 3); ctx.lineTo(sx - 4, cy + 7);
        ctx.moveTo(sx - 1, cy + 3); ctx.lineTo(sx - 1, cy + 7);
        ctx.moveTo(sx + 2, cy + 3); ctx.lineTo(sx + 2, cy + 7);
        ctx.moveTo(sx + 5, cy + 3); ctx.lineTo(sx + 5, cy + 7);
        ctx.stroke();
        // Glow.
        ctx.fillStyle = 'rgba(255, 204, 51, 0.18)';
        ctx.beginPath();
        ctx.arc(sx, cy, 14, 0, Math.PI * 2);
        ctx.fill();
        // Label.
        ctx.fillStyle = '#ffcc33';
        ctx.font = 'bold 8px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('STAG', sx, cy + 12);
        ctx.textAlign = 'left';
    }

    // ── helpers: trail / speech ────────────────────────────────────────

    _drawTrail(ctx, focus, originX, originY, agentColors) {
        const recent = this.trailHistory.slice(-60);
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

    _drawSpeechBubbles(ctx, state, focus, originX, originY, agentColors) {
        // Parse "<aid> says: <text>" patterns from this turn's events.
        const bubbles = {};
        for (const e of (state.last_events || [])) {
            const m = String(e).match(/^(\w+) says: (.+)$/);
            if (!m) continue;
            const [, aid, text] = m;
            // Latest say wins per agent (one bubble each).
            bubbles[aid] = text.replace(/\s+/g, ' ').slice(0, 64);
        }
        for (const aid of Object.keys(bubbles)) {
            const a = state.agents[aid];
            if (!a) continue;
            const p = this._iso(a.x - focus.x, a.y - focus.y, a.z, originX, originY);
            this._drawSpeechBubble(ctx, p.x, p.y - 14, bubbles[aid], agentColors[aid] || '#fff');
        }
    }

    _drawSpeechBubble(ctx, sx, sy, text, accent) {
        ctx.font = '9px sans-serif';
        const tw = Math.min(ctx.measureText(text).width + 10, 180);
        const th = 14;
        const x = sx - tw / 2;
        const y = sy - th;
        // Body.
        ctx.fillStyle = 'rgba(245, 245, 250, 0.94)';
        ctx.strokeStyle = accent;
        ctx.lineWidth = 1;
        this._roundRect(ctx, x, y, tw, th, 4);
        ctx.fill();
        ctx.stroke();
        // Tail.
        ctx.beginPath();
        ctx.moveTo(sx - 3, y + th);
        ctx.lineTo(sx, y + th + 4);
        ctx.lineTo(sx + 3, y + th);
        ctx.closePath();
        ctx.fillStyle = 'rgba(245, 245, 250, 0.94)';
        ctx.fill();
        ctx.strokeStyle = accent;
        ctx.stroke();
        // Text.
        ctx.fillStyle = '#1a1a1a';
        ctx.textAlign = 'left';
        ctx.fillText(text.length > 32 ? text.slice(0, 32) + '…' : text, x + 5, y + 10);
    }

    _hexToRgb(hex) {
        const m = /^#([0-9a-f]{6})$/i.exec(hex);
        if (!m) return {r: 255, g: 204, b: 51};
        const n = parseInt(m[1], 16);
        return {r: (n >> 16) & 0xff, g: (n >> 8) & 0xff, b: n & 0xff};
    }

    // ── helpers: HUD / panels ──────────────────────────────────────────

    _drawHUD(ctx, state, focus, turn, activeId, turnOrder, agentColors) {
        const pad = 12;
        const boxW = 260;
        const rowH = 56;
        const headerH = 28;
        const boxH = headerH + rowH * (turnOrder?.length || 1) + 8;
        ctx.fillStyle = 'rgba(20, 24, 32, 0.85)';
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
            // Tiny character icon for the agent.
            this._drawCharacterIcon(ctx, pad + 20, yy + 16, this._agentIndex(aid), color);
            ctx.fillStyle = isActive ? '#ffcc33' : '#ddd';
            ctx.font = isActive ? 'bold 12px sans-serif' : '12px sans-serif';
            ctx.fillText(`${aid}${isActive ? ' ◀' : ''}`, pad + 36, yy + 14);
            ctx.fillStyle = '#aac';
            ctx.font = '10px sans-serif';
            ctx.fillText(`(${a.x},${a.y},${a.z}) ${a.facing} · ${a.status}`, pad + 36, yy + 28);
            const inv = a.inventory || {};
            const entries = Object.entries(inv);
            const invStr = entries.length === 0
                ? '(empty)'
                : entries.map(([k, v]) => `${k}×${v}`).join(' ');
            ctx.fillStyle = '#fff';
            ctx.fillText(`inv: ${invStr.slice(0, 32)}`, pad + 36, yy + 42);
            yy += rowH;
        }
    }

    _drawGoalPanel(ctx, W, mode) {
        const scenarioId = this.matchConfig?.scenario_id;
        const goal = this._goalText(scenarioId, mode);
        if (!goal) return;
        const pad = 12;
        const boxW = 280;
        const boxH = 56;
        const x = W - boxW - pad;
        const y = pad;
        ctx.fillStyle = 'rgba(20, 24, 32, 0.85)';
        ctx.fillRect(x, y, boxW, boxH);
        ctx.strokeStyle = '#444';
        ctx.strokeRect(x, y, boxW, boxH);
        ctx.fillStyle = '#d4c27a';
        ctx.font = 'bold 11px sans-serif';
        ctx.fillText(`${mode || 'scenario'}${scenarioId ? '  ·  ' + scenarioId : ''}`, x + 10, y + 16);
        ctx.fillStyle = '#ddd';
        ctx.font = '10px sans-serif';
        const lines = this._wrap(ctx, goal, boxW - 20).slice(0, 3);
        let yy = y + 30;
        for (const ln of lines) {
            ctx.fillText(ln, x + 10, yy);
            yy += 12;
        }
    }

    _drawSubstratePanel(ctx, W, H, state, mode) {
        const lines = this._substrateLines(state, mode);
        if (!lines.length) return;
        const pad = 12;
        const boxW = 260;
        const boxH = 22 + lines.length * 14 + 8;
        const x = W - boxW - pad;
        const y = H - boxH - pad - 88;  // sits above legend
        ctx.fillStyle = 'rgba(20, 24, 32, 0.85)';
        ctx.fillRect(x, y, boxW, boxH);
        ctx.strokeStyle = '#444';
        ctx.strokeRect(x, y, boxW, boxH);
        ctx.fillStyle = '#d4c27a';
        ctx.font = 'bold 11px sans-serif';
        ctx.fillText('substrate state', x + 10, y + 16);
        ctx.fillStyle = '#fff';
        ctx.font = '10px monospace';
        let yy = y + 32;
        for (const ln of lines) {
            ctx.fillText(ln, x + 10, yy);
            yy += 14;
        }
    }

    _substrateLines(state, mode) {
        const out = [];
        if (mode === 'commons_harvest' && Array.isArray(state.trees)) {
            const alive = state.trees.filter(t => !t.dead);
            const totalApples = alive.reduce((s, t) => s + (t.apples || 0), 0);
            const dead = state.trees.length - alive.length;
            out.push(`trees: ${alive.length} alive · ${dead} dead`);
            out.push(`apples on trees: ${totalApples}`);
            const ground = (state.ground_items || []).filter(i => i.type === 'apple')
                .reduce((s, i) => s + (i.count || 1), 0);
            out.push(`apples on ground: ${ground}`);
        } else if (mode === 'stag_hunt' || mode === 'stag_hunt_repeated') {
            const s = state.stag || {};
            out.push(`stag: ${s.captured ? `captured by ${s.captured_by} @ T${s.respawn_at_turn ?? '?'}` : `alive @ (${s.x},${s.y})`}`);
            const hares = (state.ground_items || []).filter(i => i.type === 'hare').length;
            out.push(`hares on ground: ${hares}`);
        } else if (mode === 'pure_coord') {
            const m = state.meet || {};
            if (m.met) {
                out.push(`MET ✓ at T${m.at_turn} · cell (${m.cell?.x},${m.cell?.y},${m.cell?.z})`);
            } else {
                const aids = Object.keys(state.agents);
                if (aids.length >= 2) {
                    const a = state.agents[aids[0]], b = state.agents[aids[1]];
                    const md = Math.abs(a.x - b.x) + Math.abs(a.y - b.y) + Math.abs(a.z - b.z);
                    out.push(`not met yet · manhattan dist: ${md}`);
                }
            }
        } else if (mode === 'prisoners_dilemma') {
            const pd = state.pd || {};
            const log = pd.encounter_log || [];
            const tally = {CC: 0, CD: 0, DC: 0, DD: 0};
            for (const e of log) tally[e.outcome] = (tally[e.outcome] || 0) + 1;
            out.push(`encounters: ${log.length} · CC=${tally.CC} CD=${tally.CD} DC=${tally.DC} DD=${tally.DD}`);
            const coop = (state.ground_items || []).filter(i => i.type === 'coop_token')
                .reduce((s, i) => s + (i.count || 1), 0);
            const def = (state.ground_items || []).filter(i => i.type === 'defect_token')
                .reduce((s, i) => s + (i.count || 1), 0);
            out.push(`tokens on ground: C×${coop}  D×${def}`);
        } else if (mode === 'externality_mushrooms') {
            const sel = (state.ground_items || []).filter(i => i.type === 'selfish_mushroom').length;
            const pub = (state.ground_items || []).filter(i => i.type === 'public_mushroom').length;
            out.push(`mushrooms: selfish=${sel}  public=${pub}`);
        } else if (mode === 'predator_prey') {
            const c = state.chase || {};
            const roles = c.roles || {};
            const rolesStr = Object.entries(roles).map(([k, v]) => `${k}=${v}`).join(' ');
            out.push(`roles: ${rolesStr}`);
            if (c.captured) {
                out.push(`CAUGHT ✗ ${c.captor} → ${c.victim} @ T${c.captured_at_turn}`);
            } else {
                out.push(`ongoing chase · escape clock running`);
            }
        } else if (mode === 'single_navigate') {
            const n = state.navigate || {};
            const t = n.target_cell || {};
            if (n.reached) {
                out.push(`REACHED ✓ ${n.target_landmark_name} @ T${n.at_turn}`);
            } else {
                const aids = Object.keys(state.agents);
                if (aids[0]) {
                    const a = state.agents[aids[0]];
                    const md = Math.abs(a.x - t.x) + Math.abs(a.y - t.y);
                    out.push(`target: ${n.target_landmark_name} (${t.x},${t.y})`);
                    out.push(`manhattan dist: ${md}`);
                }
            }
        } else if (mode === 'sandbox') {
            // Aggregate placed-block counts and inventory totals as ambient stats.
            let placedCount = 0;
            if (state.world?.placed) {
                for (const layer of state.world.placed) {
                    for (const row of layer) {
                        for (const v of row) if (v === 1) placedCount++;
                    }
                }
            }
            const totalInv = Object.values(state.agents || {})
                .reduce((s, a) => s + Object.values(a.inventory || {}).reduce((t, n) => t + n, 0), 0);
            out.push(`placed blocks: ${placedCount}`);
            out.push(`total carried: ${totalInv}`);
        }
        return out;
    }

    _detectMode(state) {
        if (Array.isArray(state.trees) && state.trees.length) return 'commons_harvest';
        if (state.stag) {
            // stag_hunt vs stag_hunt_repeated indistinguishable from state alone;
            // use scenario_id hint if available.
            const sid = this.matchConfig?.scenario_id || '';
            return sid.includes('repeated') ? 'stag_hunt_repeated' : 'stag_hunt';
        }
        if (state.chase) return 'predator_prey';
        if (state.pd) return 'prisoners_dilemma';
        if (state.navigate) return 'single_navigate';
        if (state.meet) return 'pure_coord';
        const giTypes = new Set((state.ground_items || []).map(i => i.type));
        if (giTypes.has('public_mushroom') || giTypes.has('selfish_mushroom')) return 'externality_mushrooms';
        return 'sandbox';
    }

    _goalText(scenarioId, mode) {
        const map = {
            pure_coord_01: 'Silent meeting — converge on the same cell within 40 turns. No verbal channel.',
            pure_coord_02: 'Chat-allowed meeting — standalone `say` transmitted. Talk to coordinate.',
            pure_coord_03: 'Talk-while-acting — `say` disabled, `message` only attached to action verbs.',
            single_navigate_01: 'Navigate solo to the named landmark. Test of basic spatial action.',
            stag_hunt_01: 'Cooperate to capture the stag (high reward) or pick a hare alone (low reward).',
            stag_hunt_repeated_01: 'Repeated Stag Hunt — stag and hares respawn; play to turn limit.',
            commons_harvest_01: 'Shared apple trees with regen + depletion. Sustain the commons or deplete it.',
            externality_mushrooms_01: 'Selfish vs public mushrooms — selfish picks impose externality on partner.',
            prisoners_dilemma_01: 'Pick coop/defect tokens; encounters apply canonical PD payoffs.',
            predator_prey_01: 'Asymmetric chase — predator wins on capture, prey wins on escape to turn limit.',
            predator_prey_02: 'Asymmetric chase — predator wins on capture, prey wins on escape to turn limit.',
            sandbox_01: 'Open observational mode — no win condition. Observe what the agent does.',
            sandbox_open_01: '64×64 open world, 200 turns. Explore, gather, build, climb, dig, craft, or wander.',
            shelter_04_minimal: 'Minecraft-style free-form shelter — dig a pit, wall a corner, build a tower.',
        };
        return map[scenarioId] || (mode ? `Mode: ${mode}` : '');
    }

    _drawCompass(ctx, W, focus) {
        const cx = W - 38;
        const cy = 86;
        ctx.fillStyle = 'rgba(20, 24, 32, 0.6)';
        ctx.beginPath(); ctx.arc(cx, cy, 22, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = '#666'; ctx.lineWidth = 1; ctx.stroke();
        // Iso-aligned arrows. North = -y in world, which projects to (-tileW, -tileH) iso.
        const dirs = [
            ['N', -this.tileW, -this.tileH, '#ff7777'],
            ['S',  this.tileW,  this.tileH, '#aaa'],
            ['E',  this.tileW, -this.tileH, '#aaa'],
            ['W', -this.tileW,  this.tileH, '#aaa'],
        ];
        for (const [label, dx, dy, color] of dirs) {
            const len = 14;
            const m = Math.hypot(dx, dy);
            const ux = dx / m, uy = dy / m;
            ctx.strokeStyle = color; ctx.lineWidth = label === 'N' ? 2 : 1;
            ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + ux * len, cy + uy * len); ctx.stroke();
            ctx.fillStyle = color;
            ctx.font = 'bold 9px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(label, cx + ux * (len + 6), cy + uy * (len + 6) + 3);
        }
        ctx.textAlign = 'left';
        // Coords below.
        ctx.fillStyle = '#aac';
        ctx.font = '9px monospace';
        ctx.fillText(`focus (${focus.x},${focus.y},${focus.z})`, cx - 38, cy + 36);
    }

    _drawLegend(ctx, W, H, state, mode) {
        const pad = 12;
        const boxW = 260;
        const boxH = 80;
        const x = W - boxW - pad;
        const y = H - boxH - pad;
        ctx.fillStyle = 'rgba(20, 24, 32, 0.82)';
        ctx.fillRect(x, y, boxW, boxH);
        ctx.strokeStyle = '#444';
        ctx.strokeRect(x, y, boxW, boxH);
        ctx.fillStyle = '#d4c27a';
        ctx.font = 'bold 11px sans-serif';
        ctx.fillText('legend', x + 10, y + 14);
        ctx.font = '9px sans-serif';
        // Block-type swatches present in viewport.
        const seen = new Set();
        if (state.world?.layers) {
            for (const layer of state.world.layers) {
                for (const row of layer) {
                    for (const v of row) {
                        const n = this._blockName(v);
                        if (n !== 'air') seen.add(n);
                    }
                }
            }
        }
        const blocks = Array.from(seen).slice(0, 8);
        let cx = x + 10, cy = y + 24;
        for (const b of blocks) {
            const color = this.blockColors[b] || '#888';
            ctx.fillStyle = color;
            ctx.fillRect(cx, cy, 8, 8);
            ctx.strokeStyle = '#222'; ctx.lineWidth = 0.6; ctx.strokeRect(cx, cy, 8, 8);
            ctx.fillStyle = '#ddd';
            ctx.fillText(b, cx + 11, cy + 7);
            cx += 11 + ctx.measureText(b).width + 12;
            if (cx > x + boxW - 50) { cx = x + 10; cy += 14; }
        }
        // Item glyph hints by detected mode.
        const items = this._modeLegendItems(mode);
        if (items.length) {
            cy = y + boxH - 22;
            cx = x + 10;
            ctx.fillStyle = '#ddd';
            ctx.fillText('items:', cx, cy + 7);
            cx += 36;
            for (const it of items) {
                this._drawGroundItem(ctx, cx, cy + 4, it.type, 0);
                ctx.fillStyle = '#ddd';
                ctx.font = '9px sans-serif';
                ctx.fillText(it.label, cx + 8, cy + 7);
                cx += 12 + ctx.measureText(it.label).width + 10;
            }
        }
    }

    _modeLegendItems(mode) {
        if (mode === 'commons_harvest') return [{type: 'apple', label: 'apple'}];
        if (mode === 'stag_hunt' || mode === 'stag_hunt_repeated') return [{type: 'hare', label: 'hare'}];
        if (mode === 'externality_mushrooms') return [
            {type: 'public_mushroom', label: 'pub'},
            {type: 'selfish_mushroom', label: 'self'},
        ];
        if (mode === 'prisoners_dilemma') return [
            {type: 'coop_token', label: 'C'},
            {type: 'defect_token', label: 'D'},
        ];
        return [];
    }

    _drawEvents(ctx, events, H) {
        if (!events || events.length === 0) return;
        const pad = 12;
        const boxW = 360;
        const visible = events.slice(-5);
        const boxH = 22 + visible.length * 14;
        const top = H - pad - boxH;
        ctx.fillStyle = 'rgba(20, 24, 32, 0.85)';
        ctx.fillRect(pad, top, boxW, boxH);
        ctx.strokeStyle = '#444';
        ctx.strokeRect(pad, top, boxW, boxH);
        ctx.fillStyle = '#d4c27a';
        ctx.font = 'bold 11px sans-serif';
        ctx.fillText('recent events', pad + 8, top + 16);
        ctx.font = '10px monospace';
        let yy = top + 32;
        for (const e of visible) {
            const s = String(e);
            const isSay = /\bsays:\b/.test(s);
            const isOutcome = /\b(MET|caught|captured|encounter|tree died|stag captured)\b/i.test(s);
            ctx.fillStyle = isOutcome ? '#ffcc33' : (isSay ? '#9ad' : '#ddd');
            ctx.fillText(`· ${s.slice(0, 64)}`, pad + 8, yy);
            yy += 13;
        }
    }

    // ── helpers: event flash ───────────────────────────────────────────

    _detectFlash(events, post) {
        // Prioritise outcome events; null if none.
        for (const e of events) {
            const s = String(e).toLowerCase();
            if (s.includes('met') && (post.meet?.met)) return {kind: 'met', color: '#5fbf6a'};
            if (s.includes('stag captured') || (post.stag?.captured && s.includes('stag'))) return {kind: 'stag', color: '#ffcc33'};
            if (s.includes('captured') && post.chase?.captured) return {kind: 'chase', color: '#ff6b6b'};
            if (s.includes('encounter') && /\b(cc|cd|dc|dd)\b/i.test(s)) return {kind: 'pd', color: '#c89cff'};
            if (s.includes('tree died')) return {kind: 'depletion', color: '#999'};
        }
        return null;
    }

    _drawEventFlash(ctx, W, H) {
        if (!this._flash) return;
        const {color, kind} = this._flash;
        // Border pulse + label badge.
        const rgb = this._hexToRgb(color);
        ctx.strokeStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},0.85)`;
        ctx.lineWidth = 6;
        ctx.strokeRect(3, 3, W - 6, H - 6);
        ctx.fillStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},0.25)`;
        ctx.fillRect(3, 3, W - 6, H - 6);
        // Badge top center.
        const label = ({
            met: 'MEETING',
            stag: 'STAG CAPTURED',
            chase: 'CAUGHT',
            pd: 'PD ENCOUNTER',
            depletion: 'TREE DIED',
        })[kind] || kind.toUpperCase();
        ctx.font = 'bold 14px sans-serif';
        const tw = ctx.measureText(label).width + 28;
        const bx = W / 2 - tw / 2;
        const by = 8;
        ctx.fillStyle = `rgba(${rgb.r},${rgb.g},${rgb.b},0.95)`;
        this._roundRect(ctx, bx, by, tw, 24, 6);
        ctx.fill();
        ctx.fillStyle = '#1a1a1a';
        ctx.textAlign = 'center';
        ctx.fillText(label, W / 2, by + 16);
        ctx.textAlign = 'left';
    }

    // ── helpers: misc ──────────────────────────────────────────────────

    _shade(color, amount) {
        if (color.startsWith('rgba')) return color;
        const m = color.match(/^#([0-9a-f]{6})$/i);
        if (!m) return color;
        const r = parseInt(m[1].slice(0, 2), 16);
        const g = parseInt(m[1].slice(2, 4), 16);
        const b = parseInt(m[1].slice(4, 6), 16);
        const adj = (v) => Math.max(0, Math.min(255, Math.round(v + amount * 255)));
        return `rgb(${adj(r)}, ${adj(g)}, ${adj(b)})`;
    }

    _wrap(ctx, text, maxW) {
        const words = String(text).split(/\s+/);
        const lines = [];
        let line = '';
        for (const w of words) {
            const test = line ? line + ' ' + w : w;
            if (ctx.measureText(test).width > maxW && line) {
                lines.push(line);
                line = w;
            } else {
                line = test;
            }
        }
        if (line) lines.push(line);
        return lines;
    }

    _roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + w, y, x + w, y + h, r);
        ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r);
        ctx.arcTo(x, y, x + w, y, r);
        ctx.closePath();
    }
}

window.LxMRenderers = window.LxMRenderers || {};
window.LxMRenderers['blockworld'] = BlockworldRenderer;
