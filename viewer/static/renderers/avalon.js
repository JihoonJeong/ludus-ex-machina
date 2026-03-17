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
        evil: '#f87171',

        questPass: '#4ade80',
        questFail: '#f87171',
        questPending: '#2a2a4a',
        questCurrent: '#ffd700',

        approve: '#4ade80',
        reject: '#f87171',

        leader: '#ffd700',
        onTeam: '#3b82f6',
    };

    class AvalonRenderer {
        constructor(container) {
            this.canvas = document.createElement('canvas');
            this.W = 1400;
            this.H = 1000;
            this.canvas.width = this.W * 2;
            this.canvas.height = this.H * 2;
            this.canvas.style.width = '100%';
            this.canvas.style.height = '100%';
            container.appendChild(this.canvas);
            this.ctx = this.canvas.getContext('2d');
            this.ctx.scale(2, 2);
            this._godView = false;
            this._lastRenderArgs = null;

            this.canvas.addEventListener('click', (e) => {
                const rect = this.canvas.getBoundingClientRect();
                const sx = this.W / rect.width;
                const x = (e.clientX - rect.left) * sx;
                const y = (e.clientY - rect.top) * (this.H / rect.height);
                if (x >= this.W - 200 && x <= this.W - 16 && y >= this.H - 56 && y <= this.H - 16) {
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
                quest_number: 1, phase: 'propose',
                leader: agents[0]?.agent_id || '',
                proposed_team: null, votes_cast: {}, quest_actions: {},
                quest_results: [], consecutive_rejections: 0,
                players, evil_players: [],
                seat_order: agents.map(a => a.agent_id),
                quest_sizes: [2, 3, 2, 3, 3],
                _all_proposals: [], _all_quests: [],
                _good_wins: 0, _evil_wins: 0,
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

            ctx.fillStyle = COLORS.bg;
            ctx.fillRect(0, 0, W, H);

            this._drawHeader(ctx, state, W);
            this._drawQuestTrack(ctx, state, W);
            this._drawRejectionCounter(ctx, state, W);
            this._drawTable(ctx, state, W, H);
            this._drawPlayers(ctx, state, W, H);
            this._drawPhaseInfo(ctx, state, W, H);
            this._drawHistory(ctx, state, W, H);
            this._drawToggle(ctx, W, H);
            if (lastMove) this._drawLastAction(ctx, lastMove, W, H);
        }

        _drawHeader(ctx, state, W) {
            ctx.fillStyle = 'rgba(26, 26, 46, 0.9)';
            ctx.fillRect(0, 0, W, 58);

            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 24px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText('AVALON', 24, 38);

            ctx.fillStyle = COLORS.secondary;
            ctx.font = '18px -apple-system, sans-serif';
            ctx.fillText(`Quest ${state.quest_number} of 5`, 150, 38);

            const phase = (state.phase || '').replace(/_/g, ' ').toUpperCase();
            ctx.fillStyle = COLORS.gold;
            ctx.font = 'bold 18px -apple-system, sans-serif';
            ctx.fillText(phase, 320, 38);

            ctx.font = 'bold 22px "SF Mono", monospace';
            ctx.textAlign = 'right';
            ctx.fillStyle = COLORS.good;
            ctx.fillText(`Good ${state._good_wins}`, W - 150, 38);
            ctx.fillStyle = COLORS.muted;
            ctx.fillText(' — ', W - 108, 38);
            ctx.fillStyle = COLORS.evil;
            ctx.fillText(`${state._evil_wins} Evil`, W - 24, 38);
        }

        _drawQuestTrack(ctx, state, W) {
            const y = 74;
            const results = state.quest_results || [];
            const sizes = state.quest_sizes || [2, 3, 2, 3, 3];
            const boxW = 120, boxH = 64, gap = 24;
            const totalW = 5 * boxW + 4 * gap;
            const startX = (W - totalW) / 2;

            for (let i = 0; i < 5; i++) {
                const x = startX + i * (boxW + gap);
                const isCurrent = i === results.length;
                const isDone = i < results.length;

                ctx.fillStyle = isDone
                    ? (results[i] ? COLORS.questPass : COLORS.questFail)
                    : (isCurrent ? 'rgba(255, 215, 0, 0.2)' : COLORS.questPending);
                ctx.beginPath();
                ctx.roundRect(x, y, boxW, boxH, 10);
                ctx.fill();

                ctx.strokeStyle = isCurrent ? COLORS.questCurrent : COLORS.tableBorder;
                ctx.lineWidth = isCurrent ? 3 : 1;
                ctx.stroke();

                ctx.fillStyle = isDone ? '#fff' : (isCurrent ? COLORS.gold : COLORS.muted);
                ctx.font = 'bold 22px -apple-system, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(`Q${i + 1}`, x + boxW / 2, y + 28);

                if (isDone) {
                    ctx.fillStyle = '#fff';
                    ctx.font = 'bold 16px -apple-system, sans-serif';
                    ctx.fillText(results[i] ? 'PASS' : 'FAIL', x + boxW / 2, y + 50);
                } else {
                    ctx.fillStyle = COLORS.muted;
                    ctx.font = '15px -apple-system, sans-serif';
                    ctx.fillText(`${sizes[i]} players`, x + boxW / 2, y + 50);
                }
            }
        }

        _drawRejectionCounter(ctx, state, W) {
            const y = 158;
            const rejections = state.consecutive_rejections || 0;

            ctx.fillStyle = COLORS.secondary;
            ctx.font = '16px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Rejections:', W / 2 - 80, y);

            for (let i = 0; i < 5; i++) {
                const x = W / 2 - 10 + i * 32;
                ctx.beginPath();
                ctx.arc(x, y - 5, 12, 0, Math.PI * 2);
                ctx.fillStyle = i < rejections ? COLORS.evil : COLORS.tableBorder;
                ctx.fill();
                if (i < rejections) {
                    ctx.strokeStyle = 'rgba(248, 113, 113, 0.5)';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            }
        }

        _drawTable(ctx, state, W, H) {
            // Table center — shifted up to make room for history below
            const cx = W / 2, cy = H / 2 + 30;
            const r = 260;

            ctx.save();
            ctx.shadowColor = 'rgba(0,0,0,0.4)';
            ctx.shadowBlur = 30;
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.fillStyle = COLORS.tableBg;
            ctx.fill();
            ctx.restore();

            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.strokeStyle = COLORS.tableBorder;
            ctx.lineWidth = 2.5;
            ctx.stroke();

            // Inner ring
            ctx.beginPath();
            ctx.arc(cx, cy, r - 20, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(42, 42, 74, 0.4)';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        _drawPlayers(ctx, state, W, H) {
            const seats = state.seat_order || [];
            const n = seats.length;
            const cx = W / 2, cy = H / 2 + 30;
            // Players sit ON the table edge
            const orbitR = 270;

            const startAngle = -Math.PI / 2;
            seats.forEach((pid, i) => {
                const angle = startAngle + (i / n) * Math.PI * 2;
                const px = cx + orbitR * Math.cos(angle);
                const py = cy + orbitR * Math.sin(angle);

                const player = state.players[pid] || {};
                const isLeader = pid === state.leader;
                const onTeam = state.proposed_team && state.proposed_team.includes(pid);
                const isEvil = state.evil_players?.includes(pid);
                const role = player.role || 'unknown';

                const radius = 54;
                ctx.save();

                if (isLeader) {
                    ctx.shadowColor = COLORS.leader;
                    ctx.shadowBlur = 20;
                }

                ctx.beginPath();
                ctx.arc(px, py, radius, 0, Math.PI * 2);
                ctx.fillStyle = onTeam ? 'rgba(59, 130, 246, 0.3)' : COLORS.tableBg;
                ctx.fill();

                if (isLeader) {
                    ctx.strokeStyle = COLORS.leader;
                    ctx.lineWidth = 3.5;
                } else if (onTeam) {
                    ctx.strokeStyle = COLORS.onTeam;
                    ctx.lineWidth = 3;
                } else {
                    ctx.strokeStyle = COLORS.tableBorder;
                    ctx.lineWidth = 2;
                }
                ctx.stroke();
                ctx.restore();

                // Name
                ctx.fillStyle = COLORS.text;
                ctx.font = 'bold 19px -apple-system, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(pid, px, py + 6);

                // Role badge
                if (this._godView || state.phase === 'game_over') {
                    const showEvil = this._godView ? isEvil : (role === 'evil');
                    if (showEvil) {
                        ctx.fillStyle = COLORS.evil;
                        ctx.font = 'bold 15px -apple-system, sans-serif';
                        ctx.fillText('EVIL', px, py + 26);
                    } else {
                        ctx.fillStyle = COLORS.good;
                        ctx.font = 'bold 15px -apple-system, sans-serif';
                        ctx.fillText('GOOD', px, py + 26);
                    }
                } else if (role !== 'unknown') {
                    ctx.fillStyle = role === 'evil' ? COLORS.evil : COLORS.good;
                    ctx.font = '15px -apple-system, sans-serif';
                    ctx.fillText(role.toUpperCase(), px, py + 26);
                }

                // Crown
                if (isLeader) {
                    ctx.font = '28px sans-serif';
                    ctx.fillText('👑', px, py - radius - 10);
                }

                // Team marker
                if (onTeam) {
                    ctx.fillStyle = COLORS.onTeam;
                    ctx.font = 'bold 14px -apple-system, sans-serif';
                    ctx.fillText('TEAM', px, py - 20);
                }

                // Vote indicator
                const vote = state.votes_cast?.[pid];
                if (vote && vote !== 'submitted' && state.phase !== 'vote') {
                    ctx.fillStyle = vote === 'approve' ? COLORS.approve : COLORS.reject;
                    ctx.font = 'bold 24px sans-serif';
                    ctx.fillText(vote === 'approve' ? '✓' : '✗', px + radius + 14, py + 8);
                }
            });
        }

        _drawPhaseInfo(ctx, state, W, H) {
            const cx = W / 2, cy = H / 2 + 30;
            ctx.textAlign = 'center';
            ctx.fillStyle = COLORS.secondary;

            if (state.phase === 'propose') {
                ctx.font = '20px -apple-system, sans-serif';
                ctx.fillText(`${state.leader}'s turn`, cx, cy - 14);
                ctx.fillText('to propose a team', cx, cy + 14);
            } else if (state.phase === 'vote') {
                const team = state.proposed_team || [];
                ctx.font = '20px -apple-system, sans-serif';
                ctx.fillText('Voting on team:', cx, cy - 14);
                ctx.fillStyle = COLORS.onTeam;
                ctx.font = 'bold 20px -apple-system, sans-serif';
                ctx.fillText(team.join(', '), cx, cy + 14);
            } else if (state.phase === 'quest') {
                ctx.font = '20px -apple-system, sans-serif';
                ctx.fillText('Quest in progress...', cx, cy);
            } else if (state.phase === 'game_over') {
                ctx.fillStyle = state._good_wins >= 3 ? COLORS.good : COLORS.evil;
                ctx.font = 'bold 30px -apple-system, sans-serif';
                ctx.fillText(state._good_wins >= 3 ? 'GOOD WINS!' : 'EVIL WINS!', cx, cy);
            }
        }

        _drawHistory(ctx, state, W, H) {
            const proposals = state._all_proposals || [];
            const quests = state._all_quests || [];

            // Bottom-left: proposals
            const pX = 28, pY = H - 260;

            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 15px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText('PROPOSAL HISTORY', pX, pY);

            const recentProps = proposals.slice(-6);
            recentProps.forEach((p, i) => {
                const y = pY + 24 + i * 24;
                ctx.font = '14px "SF Mono", monospace';
                ctx.fillStyle = p.approved ? COLORS.approve : COLORS.reject;
                const icon = p.approved ? '✓' : '✗';
                ctx.fillText(`${icon} Q${p.quest}: ${p.leader}→[${p.team.join(',')}] ${p.approvals}-${p.rejections}`, pX, y);
            });

            if (proposals.length === 0) {
                ctx.font = '14px -apple-system, sans-serif';
                ctx.fillStyle = COLORS.muted;
                ctx.fillText('No proposals yet', pX, pY + 24);
            }

            // Bottom-right: quest results
            const qX = W - 420, qY = H - 260;

            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 15px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText('QUEST RESULTS', qX, qY);

            quests.forEach((q, i) => {
                const y = qY + 24 + i * 28;
                ctx.font = '14px "SF Mono", monospace';
                ctx.fillStyle = q.success ? COLORS.questPass : COLORS.questFail;
                const status = q.success ? 'PASS' : `FAIL (${q.sabotage_count} sab)`;
                ctx.fillText(`Q${q.quest}: [${q.team.join(',')}] ${status}`, qX, y);

                if (this._godView && !q.success && q.actions) {
                    const saboteurs = Object.entries(q.actions)
                        .filter(([_, a]) => a === 'sabotage')
                        .map(([pid]) => pid);
                    if (saboteurs.length > 0) {
                        ctx.fillStyle = COLORS.evil;
                        ctx.fillText(`  ↳ ${saboteurs.join(', ')}`, qX, y + 18);
                    }
                }
            });
        }

        _drawToggle(ctx, W, H) {
            const x = W - 200, y = H - 56, w = 180, h = 38;
            ctx.fillStyle = this._godView ? 'rgba(248, 113, 113, 0.2)' : 'rgba(42, 42, 74, 0.8)';
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 8);
            ctx.fill();
            ctx.strokeStyle = this._godView ? COLORS.evil : '#3a3a5a';
            ctx.lineWidth = 1;
            ctx.stroke();

            ctx.fillStyle = this._godView ? COLORS.evil : COLORS.muted;
            ctx.font = '15px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(this._godView ? '🔓 Roles Revealed' : '🔒 God View', x + w / 2, y + 25);
        }

        _drawLastAction(ctx, lastMove, W, H) {
            const move = lastMove.envelope?.move;
            const agent = lastMove.agent_id || '';
            if (!move) return;

            let text = `${agent}: `;
            switch (move.type) {
                case 'proposal': text += `proposes [${(move.team || []).join(', ')}]`; break;
                case 'vote': text += `votes ${move.choice}`; break;
                case 'quest_action': text += `plays ${move.choice}`; break;
                default: text += move.type || '?';
            }

            ctx.fillStyle = 'rgba(26, 26, 46, 0.85)';
            ctx.fillRect(0, H - 50, W - 210, 50);
            ctx.fillStyle = COLORS.text;
            ctx.font = '16px "SF Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(text, 24, H - 20);
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

        renderResult(result, state) {}

        destroy() {
            if (this.canvas?.parentNode) this.canvas.parentNode.removeChild(this.canvas);
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['avalon'] = AvalonRenderer;
})();
