/**
 * Avalon renderer for LxM Match Viewer.
 * Canvas-based round table with quest track, vote history, and god view toggle.
 */

(function () {
    const COLORS = {
        bg: '#1a1a2e',
        tableBg: '#16213e',
        tableBorder: '#2a2a4a',
        text: '#e0e0e0',
        muted: '#555577',
        secondary: '#8888aa',
        gold: '#ffd700',

        good: '#4ade80',
        goodBg: 'rgba(74, 222, 128, 0.15)',
        evil: '#f87171',
        evilBg: 'rgba(248, 113, 113, 0.15)',
        unknown: '#8888aa',

        questPass: '#4ade80',
        questFail: '#f87171',
        questPending: '#2a2a4a',
        questCurrent: '#ffd700',

        approve: '#4ade80',
        reject: '#f87171',
        submitted: '#555577',

        leader: '#ffd700',
        onTeam: '#3b82f6',
        active: 'rgba(255, 215, 0, 0.25)',
    };

    class AvalonRenderer {
        constructor(container) {
            this.canvas = document.createElement('canvas');
            this.W = 960;
            this.H = 720;
            this.canvas.width = this.W * 2;
            this.canvas.height = this.H * 2;
            this.canvas.style.width = '100%';
            this.canvas.style.height = '100%';
            container.appendChild(this.canvas);
            this.ctx = this.canvas.getContext('2d');
            this.ctx.scale(2, 2);
            this._godView = false;
            this._lastRenderArgs = null;

            // God view toggle click
            this.canvas.addEventListener('click', (e) => {
                const rect = this.canvas.getBoundingClientRect();
                const sx = this.W / rect.width;
                const x = (e.clientX - rect.left) * sx;
                const y = (e.clientY - rect.top) * (this.H / rect.height);
                if (x >= this.W - 150 && x <= this.W - 10 && y >= this.H - 40 && y <= this.H - 10) {
                    this._godView = !this._godView;
                    if (this._lastRenderArgs) this.render(...this._lastRenderArgs);
                }
            });
        }

        initialState(matchConfig) {
            const agents = matchConfig.agents || [];
            const players = {};
            agents.forEach(a => {
                players[a.agent_id] = { role: 'unknown', status: 'active' };
            });
            return {
                quest_number: 1,
                phase: 'propose',
                leader: agents[0]?.agent_id || '',
                proposed_team: null,
                votes_cast: {},
                quest_actions: {},
                quest_results: [],
                consecutive_rejections: 0,
                players,
                evil_players: [],
                seat_order: agents.map(a => a.agent_id),
                quest_sizes: [2, 3, 2, 3, 3],
                _all_proposals: [],
                _all_quests: [],
                _good_wins: 0,
                _evil_wins: 0,
            };
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            const ctx = logEntry.post_move_context;
            if (!post) return state;

            return {
                ...state,
                quest_number: post.quest_number ?? state.quest_number,
                phase: post.phase ?? state.phase,
                leader: post.leader ?? state.leader,
                proposed_team: post.proposed_team,
                votes_cast: post.votes_cast ?? {},
                votes_pending: post.votes_pending ?? [],
                quest_actions: post.quest_actions ?? {},
                quest_actions_pending: post.quest_actions_pending ?? [],
                quest_results: post.quest_results ?? state.quest_results,
                consecutive_rejections: post.consecutive_rejections ?? 0,
                players: post.players ?? state.players,
                evil_players: post.evil_players ?? state.evil_players,
                seat_order: post.seat_order ?? state.seat_order,
                quest_sizes: post.quest_sizes ?? state.quest_sizes,
                _all_proposals: ctx?.all_proposals ?? state._all_proposals,
                _all_quests: ctx?.all_quests ?? state._all_quests,
                _good_wins: ctx?.good_wins ?? state._good_wins,
                _evil_wins: ctx?.evil_wins ?? state._evil_wins,
            };
        }

        render(state, turnNumber, lastMove, animate = false) {
            this._lastRenderArgs = [state, turnNumber, lastMove, animate];
            const ctx = this.ctx;
            const W = this.W, H = this.H;

            // Background
            ctx.fillStyle = COLORS.bg;
            ctx.fillRect(0, 0, W, H);

            // Header
            this._drawHeader(ctx, state, W);

            // Quest track
            this._drawQuestTrack(ctx, state, W);

            // Rejection counter
            this._drawRejectionCounter(ctx, state, W);

            // Players in circle
            this._drawPlayers(ctx, state, W, H);

            // Phase info
            this._drawPhaseInfo(ctx, state, W, H);

            // Vote/Quest history
            this._drawHistory(ctx, state, W, H);

            // God view toggle
            this._drawToggle(ctx, W, H);

            // Last action
            if (lastMove) {
                this._drawLastAction(ctx, lastMove, W, H);
            }
        }

        _drawHeader(ctx, state, W) {
            ctx.fillStyle = 'rgba(26, 26, 46, 0.9)';
            ctx.fillRect(0, 0, W, 44);

            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 16px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(`AVALON`, 16, 28);

            ctx.fillStyle = COLORS.secondary;
            ctx.font = '14px -apple-system, sans-serif';
            ctx.fillText(`Quest ${state.quest_number} of 5`, 110, 28);

            const phase = (state.phase || '').replace(/_/g, ' ').toUpperCase();
            ctx.fillStyle = COLORS.gold;
            ctx.font = 'bold 13px -apple-system, sans-serif';
            ctx.fillText(phase, 240, 28);

            // Score
            ctx.fillStyle = COLORS.good;
            ctx.font = 'bold 14px "SF Mono", monospace';
            ctx.textAlign = 'right';
            ctx.fillText(`Good ${state._good_wins}`, W - 100, 28);
            ctx.fillStyle = COLORS.muted;
            ctx.fillText(' - ', W - 70, 28);
            ctx.fillStyle = COLORS.evil;
            ctx.fillText(`${state._evil_wins} Evil`, W - 16, 28);
        }

        _drawQuestTrack(ctx, state, W) {
            const y = 60;
            const results = state.quest_results || [];
            const sizes = state.quest_sizes || [2, 3, 2, 3, 3];
            const totalW = 5 * 80 + 4 * 16;
            const startX = (W - totalW) / 2;

            for (let i = 0; i < 5; i++) {
                const x = startX + i * 96;
                const isCurrent = i === results.length;
                const isDone = i < results.length;

                // Quest box
                ctx.fillStyle = isDone
                    ? (results[i] ? COLORS.questPass : COLORS.questFail)
                    : (isCurrent ? 'rgba(255, 215, 0, 0.2)' : COLORS.questPending);
                ctx.beginPath();
                ctx.roundRect(x, y, 80, 44, 6);
                ctx.fill();

                ctx.strokeStyle = isCurrent ? COLORS.questCurrent : COLORS.tableBorder;
                ctx.lineWidth = isCurrent ? 2 : 1;
                ctx.stroke();

                // Quest number
                ctx.fillStyle = isDone ? '#fff' : (isCurrent ? COLORS.gold : COLORS.muted);
                ctx.font = 'bold 14px -apple-system, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(`Q${i + 1}`, x + 40, y + 20);

                // Team size
                ctx.font = '11px -apple-system, sans-serif';
                ctx.fillStyle = isDone ? 'rgba(255,255,255,0.7)' : COLORS.muted;
                ctx.fillText(`${sizes[i]} players`, x + 40, y + 36);

                // Result icon
                if (isDone) {
                    ctx.font = 'bold 11px sans-serif';
                    ctx.fillStyle = results[i] ? '#fff' : '#fff';
                    ctx.fillText(results[i] ? 'PASS' : 'FAIL', x + 40, y + 36);
                }
            }
        }

        _drawRejectionCounter(ctx, state, W) {
            const y = 114;
            const rejections = state.consecutive_rejections || 0;

            ctx.fillStyle = COLORS.secondary;
            ctx.font = '12px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Rejections:', W / 2 - 60, y);

            for (let i = 0; i < 5; i++) {
                const x = W / 2 - 10 + i * 22;
                ctx.beginPath();
                ctx.arc(x, y - 4, 7, 0, Math.PI * 2);
                ctx.fillStyle = i < rejections ? COLORS.evil : COLORS.tableBorder;
                ctx.fill();
                if (i < rejections) {
                    ctx.strokeStyle = 'rgba(248, 113, 113, 0.5)';
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }
        }

        _drawPlayers(ctx, state, W, H) {
            const seats = state.seat_order || [];
            const n = seats.length;
            const cx = W / 2;
            const cy = H / 2 + 40;
            const rx = 200, ry = 180;

            // Draw table circle
            ctx.beginPath();
            ctx.ellipse(cx, cy, rx - 30, ry - 30, 0, 0, Math.PI * 2);
            ctx.fillStyle = COLORS.tableBg;
            ctx.fill();
            ctx.strokeStyle = COLORS.tableBorder;
            ctx.lineWidth = 2;
            ctx.stroke();

            const startAngle = -Math.PI / 2; // Top
            seats.forEach((pid, i) => {
                const angle = startAngle + (i / n) * Math.PI * 2;
                const px = cx + rx * Math.cos(angle);
                const py = cy + ry * Math.sin(angle);

                const player = state.players[pid] || {};
                const isLeader = pid === state.leader;
                const onTeam = state.proposed_team && state.proposed_team.includes(pid);
                const isEvil = state.evil_players?.includes(pid);
                const role = player.role || 'unknown';

                // Player circle
                const radius = 32;
                ctx.save();

                // Glow for leader
                if (isLeader) {
                    ctx.shadowColor = COLORS.leader;
                    ctx.shadowBlur = 12;
                }

                ctx.beginPath();
                ctx.arc(px, py, radius, 0, Math.PI * 2);

                if (onTeam) {
                    ctx.fillStyle = 'rgba(59, 130, 246, 0.3)';
                } else {
                    ctx.fillStyle = COLORS.tableBg;
                }
                ctx.fill();

                // Border
                if (isLeader) {
                    ctx.strokeStyle = COLORS.leader;
                    ctx.lineWidth = 3;
                } else if (onTeam) {
                    ctx.strokeStyle = COLORS.onTeam;
                    ctx.lineWidth = 2;
                } else {
                    ctx.strokeStyle = COLORS.tableBorder;
                    ctx.lineWidth = 1;
                }
                ctx.stroke();
                ctx.restore();

                // Name
                const displayName = pid.length > 10 ? pid.slice(0, 9) + '…' : pid;
                ctx.fillStyle = COLORS.text;
                ctx.font = 'bold 12px -apple-system, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(displayName, px, py + 4);

                // Role badge (god view or game over)
                if (this._godView || state.phase === 'game_over') {
                    const showRole = this._godView ? (isEvil ? 'evil' : role) : role;
                    if (showRole === 'evil' || (this._godView && isEvil)) {
                        ctx.fillStyle = COLORS.evil;
                        ctx.font = 'bold 10px -apple-system, sans-serif';
                        ctx.fillText('EVIL', px, py + 18);
                    } else if (showRole === 'good') {
                        ctx.fillStyle = COLORS.good;
                        ctx.font = 'bold 10px -apple-system, sans-serif';
                        ctx.fillText('GOOD', px, py + 18);
                    }
                } else if (role !== 'unknown') {
                    ctx.fillStyle = role === 'evil' ? COLORS.evil : COLORS.good;
                    ctx.font = '10px -apple-system, sans-serif';
                    ctx.fillText(role.toUpperCase(), px, py + 18);
                }

                // Leader crown
                if (isLeader) {
                    ctx.fillStyle = COLORS.leader;
                    ctx.font = '16px sans-serif';
                    ctx.fillText('👑', px, py - radius - 6);
                }

                // Team marker
                if (onTeam) {
                    ctx.fillStyle = COLORS.onTeam;
                    ctx.font = 'bold 9px -apple-system, sans-serif';
                    ctx.fillText('TEAM', px, py - 14);
                }

                // Vote indicator (after voting resolves)
                const vote = state.votes_cast?.[pid];
                if (vote && vote !== 'submitted' && state.phase !== 'vote') {
                    ctx.fillStyle = vote === 'approve' ? COLORS.approve : COLORS.reject;
                    ctx.font = '10px sans-serif';
                    ctx.fillText(vote === 'approve' ? '✓' : '✗', px + radius + 8, py);
                }
            });
        }

        _drawPhaseInfo(ctx, state, W, H) {
            const x = W / 2;
            const y = H / 2 + 40;

            // Center text in table
            ctx.textAlign = 'center';
            ctx.fillStyle = COLORS.secondary;
            ctx.font = '13px -apple-system, sans-serif';

            if (state.phase === 'propose') {
                ctx.fillText(`${state.leader}'s turn`, x, y - 10);
                ctx.fillText('to propose a team', x, y + 8);
            } else if (state.phase === 'vote') {
                const team = state.proposed_team || [];
                ctx.fillText(`Voting on team:`, x, y - 10);
                ctx.fillStyle = COLORS.onTeam;
                ctx.font = 'bold 13px -apple-system, sans-serif';
                ctx.fillText(team.join(', '), x, y + 8);
            } else if (state.phase === 'quest') {
                ctx.fillText('Quest in progress...', x, y);
            } else if (state.phase === 'game_over') {
                ctx.fillStyle = state._good_wins >= 3 ? COLORS.good : COLORS.evil;
                ctx.font = 'bold 16px -apple-system, sans-serif';
                ctx.fillText(state._good_wins >= 3 ? 'GOOD WINS!' : 'EVIL WINS!', x, y);
            }
        }

        _drawHistory(ctx, state, W, H) {
            const proposals = state._all_proposals || [];
            const quests = state._all_quests || [];

            // Right side: recent proposals
            const panelX = W - 260;
            const panelY = 130;

            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 11px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText('PROPOSAL HISTORY', panelX, panelY);

            const recentProps = proposals.slice(-6);
            recentProps.forEach((p, i) => {
                const y = panelY + 18 + i * 18;
                ctx.font = '11px "SF Mono", monospace';
                ctx.fillStyle = p.approved ? COLORS.approve : COLORS.reject;
                const icon = p.approved ? '✓' : '✗';
                ctx.fillText(`${icon} Q${p.quest}: ${p.leader}→[${p.team.join(',')}] ${p.approvals}-${p.rejections}`, panelX, y);
            });

            if (proposals.length === 0) {
                ctx.font = '11px -apple-system, sans-serif';
                ctx.fillStyle = COLORS.muted;
                ctx.fillText('No proposals yet', panelX, panelY + 18);
            }

            // Quest history below
            const qPanelY = panelY + 140;
            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 11px -apple-system, sans-serif';
            ctx.fillText('QUEST RESULTS', panelX, qPanelY);

            quests.forEach((q, i) => {
                const y = qPanelY + 18 + i * 18;
                ctx.font = '11px "SF Mono", monospace';
                ctx.fillStyle = q.success ? COLORS.questPass : COLORS.questFail;
                const status = q.success ? 'PASS' : `FAIL (${q.sabotage_count} sab)`;
                ctx.fillText(`Q${q.quest}: [${q.team.join(',')}] ${status}`, panelX, y);

                // God view: show who sabotaged
                if (this._godView && !q.success && q.actions) {
                    const saboteurs = Object.entries(q.actions)
                        .filter(([_, a]) => a === 'sabotage')
                        .map(([pid]) => pid);
                    if (saboteurs.length > 0) {
                        ctx.fillStyle = COLORS.evil;
                        ctx.fillText(`  ↳ ${saboteurs.join(', ')}`, panelX, y + 14);
                    }
                }
            });
        }

        _drawToggle(ctx, W, H) {
            const x = W - 150, y = H - 40, w = 140, h = 28;
            ctx.fillStyle = this._godView ? 'rgba(248, 113, 113, 0.2)' : 'rgba(42, 42, 74, 0.8)';
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 5);
            ctx.fill();
            ctx.strokeStyle = this._godView ? COLORS.evil : '#3a3a5a';
            ctx.lineWidth = 1;
            ctx.stroke();

            ctx.fillStyle = this._godView ? COLORS.evil : COLORS.muted;
            ctx.font = '11px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(this._godView ? '🔓 Roles Revealed' : '🔒 God View', x + w / 2, y + 18);
        }

        _drawLastAction(ctx, lastMove, W, H) {
            const move = lastMove.envelope?.move;
            const agent = lastMove.agent_id || '';
            if (!move) return;

            let text = `${agent}: `;
            switch (move.type) {
                case 'proposal':
                    text += `proposes [${(move.team || []).join(', ')}]`;
                    break;
                case 'vote':
                    text += `votes ${move.choice}`;
                    break;
                case 'quest_action':
                    text += `plays ${move.choice}`;
                    break;
                default:
                    text += move.type || '?';
            }

            ctx.fillStyle = 'rgba(26, 26, 46, 0.85)';
            ctx.fillRect(0, H - 36, W - 160, 36);

            ctx.fillStyle = COLORS.text;
            ctx.font = '12px "SF Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(text, 16, H - 14);
        }

        formatMoveSummary(logEntry) {
            const move = logEntry.envelope?.move;
            const agent = logEntry.agent_id || '';
            if (!move) {
                if (logEntry.result === 'timeout') return `${agent}: timed out`;
                return '?';
            }
            switch (move.type) {
                case 'proposal': return `${agent}: proposes [${(move.team || []).join(', ')}]`;
                case 'vote': return `${agent}: ${move.choice}`;
                case 'quest_action': return `${agent}: ${move.choice}`;
                default: return `${agent}: ${move.type}`;
            }
        }

        renderResult(result, state) {
            // Result overlay handled by app.js
        }

        destroy() {
            if (this.canvas && this.canvas.parentNode) {
                this.canvas.parentNode.removeChild(this.canvas);
            }
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['avalon'] = AvalonRenderer;
})();
