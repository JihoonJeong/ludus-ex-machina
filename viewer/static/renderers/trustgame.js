/**
 * Trust Game (Prisoner's Dilemma) renderer for LxM Match Viewer.
 * Canvas-based visualization with history strip, scores, and cooperation stats.
 */

(function () {
    const COLORS = {
        cooperate: '#4ade80',
        defect: '#f87171',
        cooperateBg: 'rgba(74, 222, 128, 0.15)',
        defectBg: 'rgba(248, 113, 113, 0.15)',
        bg: '#1a1a2e',
        cardBg: '#16213e',
        text: '#e0e0e0',
        muted: '#555577',
        secondary: '#8888aa',
        border: '#2a2a4a',
        gold: '#ffd700',
    };

    class TrustGameRenderer {
        constructor(container) {
            this.canvas = document.createElement('canvas');
            this.canvas.width = 960;
            this.canvas.height = 640;
            container.appendChild(this.canvas);
            this.ctx = this.canvas.getContext('2d');
        }

        initialState(matchConfig) {
            const agents = matchConfig.agents.map(a => a.agent_id);
            const names = matchConfig.agents.map(a => a.display_name || a.agent_id);
            return {
                round: 1,
                scores: { [agents[0]]: 0, [agents[1]]: 0 },
                history: [],
                pendingMove: null,
                agents,
                names,
                cooperationRate: { [agents[0]]: 0, [agents[1]]: 0 },
                patterns: { mutual_cooperate: 0, mutual_defect: 0, betrayals: 0 },
                lastAction: null,
                lastPayoffs: null,
            };
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            const ctx = logEntry.post_move_context;
            if (!post) return state;

            return {
                ...state,
                round: post.round,
                scores: post.scores,
                pendingMove: post.pending_move,
                history: ctx?.history || state.history,
                cooperationRate: ctx?.cooperation_rate || state.cooperationRate,
                patterns: ctx?.patterns || state.patterns,
                lastAction: logEntry.envelope?.move?.action || null,
                lastAgent: logEntry.agent_id,
                lastPayoffs: null,  // Will be set from history
            };
        }

        render(state, turnNumber, lastMove, animate = false) {
            const ctx = this.ctx;
            const W = this.canvas.width;
            const H = this.canvas.height;

            // Background
            ctx.fillStyle = COLORS.bg;
            ctx.fillRect(0, 0, W, H);

            const agents = state.agents || [];
            if (agents.length < 2) return;

            // Title
            const roundNum = state.history.length;
            ctx.fillStyle = COLORS.secondary;
            ctx.font = '17px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`Round ${roundNum} / ??`, W / 2, 30);

            // Agent cards
            this._drawAgentCard(ctx, 60, 60, 360, 180, state, 0);
            this._drawAgentCard(ctx, 540, 60, 360, 180, state, 1);

            // VS separator
            ctx.fillStyle = COLORS.muted;
            ctx.font = 'bold 20px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('vs', W / 2, 155);

            // Last round result
            if (state.history.length > 0) {
                const lastRound = state.history[state.history.length - 1];
                this._drawRoundResult(ctx, W / 2, 270, lastRound, agents);
            }

            // History strip
            this._drawHistoryStrip(ctx, 60, 320, W - 120, 140, state);

            // Stats bar
            this._drawStats(ctx, 60, 490, W - 120, state);
        }

        _drawAgentCard(ctx, x, y, w, h, state, idx) {
            const agents = state.agents;
            const aid = agents[idx];
            const name = state.names[idx];
            const score = state.scores[aid] || 0;

            // Card bg
            ctx.fillStyle = COLORS.cardBg;
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 8);
            ctx.fill();
            ctx.strokeStyle = COLORS.border;
            ctx.lineWidth = 1;
            ctx.stroke();

            // Name
            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 20px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(name, x + w / 2, y + 35);

            // Score
            ctx.fillStyle = COLORS.gold;
            ctx.font = 'bold 48px "SF Mono", monospace';
            ctx.fillText(String(score), x + w / 2, y + 98);

            ctx.fillStyle = COLORS.muted;
            ctx.font = '14px -apple-system, sans-serif';
            ctx.fillText('SCORE', x + w / 2, y + 118);

            // Cooperation rate
            const rate = state.cooperationRate[aid] || 0;
            const rateText = state.history.length > 0 ? `${Math.round(rate * 100)}% coop` : '—';
            ctx.fillStyle = rate >= 0.5 ? COLORS.cooperate : COLORS.defect;
            ctx.font = '16px "SF Mono", monospace';
            ctx.fillText(rateText, x + w / 2, y + 150);

            // Last action indicator
            if (state.history.length > 0) {
                const lastRound = state.history[state.history.length - 1];
                const action = lastRound[aid];
                if (action) {
                    const color = action === 'cooperate' ? COLORS.cooperate : COLORS.defect;
                    const label = action === 'cooperate' ? 'COOPERATE' : 'DEFECT';
                    ctx.fillStyle = color;
                    ctx.font = 'bold 14px -apple-system, sans-serif';
                    ctx.fillText(label, x + w / 2, y + 170);
                }
            }
        }

        _drawRoundResult(ctx, cx, cy, round, agents) {
            const a0 = agents[0];
            const a1 = agents[1];
            const act0 = round[a0];
            const act1 = round[a1];
            const pay0 = round.payoffs[a0];
            const pay1 = round.payoffs[a1];

            // Payoff display
            ctx.font = 'bold 24px "SF Mono", monospace';
            ctx.textAlign = 'center';

            ctx.fillStyle = pay0 > 0 ? COLORS.cooperate : COLORS.defect;
            ctx.fillText(`+${pay0}`, cx - 120, cy);

            ctx.fillStyle = COLORS.muted;
            ctx.fillText('/', cx, cy);

            ctx.fillStyle = pay1 > 0 ? COLORS.cooperate : COLORS.defect;
            ctx.fillText(`+${pay1}`, cx + 120, cy);

            // Label
            let label = '';
            if (act0 === 'cooperate' && act1 === 'cooperate') label = 'Mutual Cooperation';
            else if (act0 === 'defect' && act1 === 'defect') label = 'Mutual Defection';
            else label = 'Betrayal';

            ctx.fillStyle = COLORS.secondary;
            ctx.font = '15px -apple-system, sans-serif';
            ctx.fillText(label, cx, cy + 26);
        }

        _drawHistoryStrip(ctx, x, y, w, h, state) {
            const agents = state.agents;
            const history = state.history;
            if (history.length === 0) {
                ctx.fillStyle = COLORS.muted;
                ctx.font = '15px -apple-system, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('No rounds played yet', x + w / 2, y + h / 2);
                return;
            }

            // Header
            ctx.fillStyle = COLORS.muted;
            ctx.font = '14px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText('HISTORY', x, y);

            const dotSize = Math.min(16, (w - 100) / Math.max(history.length, 1));
            const startX = x + 90;
            const rowHeight = 32;

            for (let agentIdx = 0; agentIdx < 2; agentIdx++) {
                const aid = agents[agentIdx];
                const rowY = y + 20 + agentIdx * rowHeight;

                // Agent label
                ctx.fillStyle = COLORS.secondary;
                ctx.font = '13px "SF Mono", monospace';
                ctx.textAlign = 'right';
                ctx.fillText(state.names[agentIdx].slice(0, 10), startX - 8, rowY + 12);

                // Dots
                for (let i = 0; i < history.length; i++) {
                    const action = history[i][aid];
                    const dotX = startX + i * dotSize;
                    const color = action === 'cooperate' ? COLORS.cooperate : COLORS.defect;

                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(dotX + dotSize / 2, rowY + 8, dotSize * 0.35, 0, Math.PI * 2);
                    ctx.fill();
                }
            }

            // Outcome row (mutual coop / defect / betrayal)
            const outcomeY = y + 20 + 2 * rowHeight;
            ctx.fillStyle = COLORS.muted;
            ctx.font = '13px "SF Mono", monospace';
            ctx.textAlign = 'right';
            ctx.fillText('outcome', startX - 8, outcomeY + 12);

            for (let i = 0; i < history.length; i++) {
                const a0 = history[i][agents[0]];
                const a1 = history[i][agents[1]];
                const dotX = startX + i * dotSize;
                let symbol, color;

                if (a0 === 'cooperate' && a1 === 'cooperate') {
                    color = COLORS.cooperate;
                    symbol = '\u2714'; // checkmark
                } else if (a0 === 'defect' && a1 === 'defect') {
                    color = COLORS.defect;
                    symbol = '\u2716'; // x
                } else {
                    color = COLORS.gold;
                    symbol = '!';
                }

                ctx.fillStyle = color;
                ctx.font = `${Math.max(10, dotSize * 0.7)}px "SF Mono", monospace`;
                ctx.textAlign = 'center';
                ctx.fillText(symbol, dotX + dotSize / 2, outcomeY + 12);
            }
        }

        _drawStats(ctx, x, y, w, state) {
            const p = state.patterns;
            const total = p.mutual_cooperate + p.mutual_defect + p.betrayals;
            if (total === 0) return;

            ctx.fillStyle = COLORS.border;
            ctx.fillRect(x, y, w, 1);

            const stats = [
                { label: 'Mutual Cooperation', value: p.mutual_cooperate, color: COLORS.cooperate },
                { label: 'Mutual Defection', value: p.mutual_defect, color: COLORS.defect },
                { label: 'Betrayals', value: p.betrayals, color: COLORS.gold },
            ];

            const barY = y + 30;
            const barH = 24;

            // Bar chart
            let bx = x;
            for (const s of stats) {
                const bw = (s.value / total) * w;
                if (bw > 0) {
                    ctx.fillStyle = s.color;
                    ctx.globalAlpha = 0.3;
                    ctx.fillRect(bx, barY, bw, barH);
                    ctx.globalAlpha = 1.0;
                    if (bw > 30) {
                        ctx.fillStyle = s.color;
                        ctx.font = 'bold 14px "SF Mono", monospace';
                        ctx.textAlign = 'center';
                        ctx.fillText(String(s.value), bx + bw / 2, barY + 16);
                    }
                    bx += bw;
                }
            }

            // Labels
            ctx.font = '14px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            let lx = x;
            for (const s of stats) {
                ctx.fillStyle = s.color;
                ctx.fillText(`${s.label}: ${s.value}`, lx, barY + barH + 24);
                lx += w / 3;
            }
        }

        renderResult(result, state) {
            // Result overlay handled by app.js
        }

        formatMoveSummary(logEntry) {
            const action = logEntry.envelope?.move?.action;
            if (!action) return '?';
            return action === 'cooperate' ? 'Cooperate' : 'Defect';
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['trustgame'] = TrustGameRenderer;
})();
