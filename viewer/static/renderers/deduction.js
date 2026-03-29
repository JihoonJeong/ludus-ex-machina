/**
 * Deduction Game renderer for LxM Match Viewer.
 * Shows case info, evidence exploration timeline, notes, and final answer.
 */

(function () {
    const COLORS = {
        bg: '#1a1a2e',
        cardBg: '#16213e',
        text: '#e0e0e0',
        muted: '#555577',
        secondary: '#8888aa',
        border: '#2a2a4a',
        read: '#4ade80',
        unread: '#334455',
        note: '#fbbf24',
        submit: '#60a5fa',
        correct: '#4ade80',
        wrong: '#f87171',
        partial: '#fbbf24',
    };

    class DeductionRenderer {
        constructor(container) {
            this.canvas = document.createElement('canvas');
            this.canvas.width = 960;
            this.canvas.height = 700;
            container.appendChild(this.canvas);
            this.ctx = this.canvas.getContext('2d');
        }

        initialState(matchConfig) {
            const agents = matchConfig.agents.map(a => a.agent_id);
            return {
                agents,
                filesRead: [],
                filesAvailable: [],
                notes: '',
                timeline: [],
                submitted: false,
                answer: null,
                result: null,
                title: '',
                difficulty: '',
                suspects: {},
            };
        }

        applyMove(state, move, agentId, postMoveState) {
            const s = { ...state, timeline: [...state.timeline] };

            // Extract from post_move_state if available
            if (postMoveState) {
                const agent = postMoveState.agents?.[agentId];
                if (agent) {
                    s.filesRead = agent.files_read || [];
                    s.filesAvailable = agent.files_available || [];
                    s.notes = agent.notes || '';
                    s.submitted = agent.submitted || false;
                    s.answer = agent.answer;
                }
                s.title = postMoveState.scenario_id || state.title;
            }

            // Build timeline entry
            const entry = { agent: agentId, action: move.action };
            if (move.action === 'read') {
                entry.file = move.file;
            } else if (move.action === 'note') {
                entry.content = (move.content || '').substring(0, 100);
            } else if (move.action === 'submit') {
                entry.answer = move.answer;
            }
            s.timeline.push(entry);

            return s;
        }

        render(state, context) {
            const ctx = this.ctx;
            const W = this.canvas.width;
            const H = this.canvas.height;

            // Background
            ctx.fillStyle = COLORS.bg;
            ctx.fillRect(0, 0, W, H);

            // Title
            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 18px Inter, sans-serif';
            const title = context?.title || state.title || 'Deduction';
            const diff = context?.difficulty || state.difficulty || '';
            ctx.fillText(`${title} (${diff})`, 20, 30);

            // Left panel: Evidence files
            this._renderEvidencePanel(ctx, state, context, 20, 50, 280, H - 70);

            // Center panel: Timeline
            this._renderTimeline(ctx, state, 320, 50, 340, H - 70);

            // Right panel: Answer & Score
            this._renderAnswerPanel(ctx, state, context, 680, 50, 260, H - 70);
        }

        _renderEvidencePanel(ctx, state, context, x, y, w, h) {
            // Header
            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 13px Inter, sans-serif';
            ctx.fillText('EVIDENCE FILES', x, y + 15);

            const allFiles = [...new Set([...(state.filesRead || []), ...(state.filesAvailable || [])])].sort();
            const readSet = new Set(state.filesRead || []);

            const lineH = 22;
            const startY = y + 35;

            allFiles.forEach((file, i) => {
                const fy = startY + i * lineH;
                if (fy > y + h) return;

                const isRead = readSet.has(file);

                // Indicator
                ctx.fillStyle = isRead ? COLORS.read : COLORS.unread;
                ctx.fillRect(x, fy - 10, 8, 14);

                // Filename
                ctx.fillStyle = isRead ? COLORS.text : COLORS.muted;
                ctx.font = '12px monospace';
                ctx.fillText(file, x + 14, fy);
            });

            // Count
            ctx.fillStyle = COLORS.secondary;
            ctx.font = '11px Inter, sans-serif';
            const total = allFiles.length || context?.total_evidence || 0;
            ctx.fillText(`${readSet.size}/${total} read`, x, y + h - 5);
        }

        _renderTimeline(ctx, state, x, y, w, h) {
            // Header
            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 13px Inter, sans-serif';
            ctx.fillText('INVESTIGATION TIMELINE', x, y + 15);

            const timeline = state.timeline || [];
            const lineH = 28;
            const startY = y + 35;

            timeline.forEach((entry, i) => {
                const ty = startY + i * lineH;
                if (ty > y + h - 20) return;

                // Turn number
                ctx.fillStyle = COLORS.muted;
                ctx.font = '11px monospace';
                ctx.fillText(`T${i + 1}`, x, ty);

                // Action icon + text
                if (entry.action === 'read') {
                    ctx.fillStyle = COLORS.read;
                    ctx.font = '12px Inter, sans-serif';
                    ctx.fillText(`📄 Read: ${entry.file}`, x + 30, ty);
                } else if (entry.action === 'note') {
                    ctx.fillStyle = COLORS.note;
                    ctx.font = '12px Inter, sans-serif';
                    const preview = (entry.content || '').substring(0, 40);
                    ctx.fillText(`📝 Note: ${preview}...`, x + 30, ty);
                } else if (entry.action === 'submit') {
                    ctx.fillStyle = COLORS.submit;
                    ctx.font = 'bold 12px Inter, sans-serif';
                    const ans = entry.answer || {};
                    ctx.fillText(`🎯 SUBMIT: ${ans.culprit || '?'}`, x + 30, ty);
                }
            });

            if (timeline.length === 0) {
                ctx.fillStyle = COLORS.muted;
                ctx.font = '12px Inter, sans-serif';
                ctx.fillText('No moves yet...', x + 30, startY);
            }
        }

        _renderAnswerPanel(ctx, state, context, x, y, w, h) {
            // Header
            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 13px Inter, sans-serif';
            ctx.fillText('VERDICT', x, y + 15);

            if (!state.submitted || !state.answer) {
                ctx.fillStyle = COLORS.muted;
                ctx.font = '12px Inter, sans-serif';
                ctx.fillText('Investigating...', x, y + 40);
                return;
            }

            const answer = state.answer;
            let ly = y + 40;

            // Suspects list
            const suspects = context?.suspect_names || state.suspects || {};
            if (Object.keys(suspects).length > 0) {
                ctx.fillStyle = COLORS.secondary;
                ctx.font = '11px Inter, sans-serif';
                ctx.fillText('Suspects:', x, ly);
                ly += 18;
                for (const [id, name] of Object.entries(suspects)) {
                    const isAccused = answer.culprit?.toUpperCase() === id.toUpperCase();
                    ctx.fillStyle = isAccused ? COLORS.submit : COLORS.muted;
                    ctx.font = isAccused ? 'bold 12px Inter, sans-serif' : '11px Inter, sans-serif';
                    ctx.fillText(`${isAccused ? '▶ ' : '  '}${id}: ${name}`, x, ly);
                    ly += 16;
                }
                ly += 10;
            }

            // Answer
            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 13px Inter, sans-serif';
            ctx.fillText('Answer:', x, ly);
            ly += 20;

            const fields = [
                ['Culprit', answer.culprit],
                ['Motive', answer.motive],
                ['Method', answer.method],
            ];

            fields.forEach(([label, value]) => {
                ctx.fillStyle = COLORS.secondary;
                ctx.font = '11px Inter, sans-serif';
                ctx.fillText(label + ':', x, ly);
                ly += 15;
                ctx.fillStyle = COLORS.text;
                ctx.font = '12px Inter, sans-serif';
                // Wrap long text
                const maxW = w - 10;
                const words = (value || '?').split(' ');
                let line = '';
                words.forEach(word => {
                    const test = line + (line ? ' ' : '') + word;
                    if (ctx.measureText(test).width > maxW && line) {
                        ctx.fillText(line, x, ly);
                        ly += 14;
                        line = word;
                    } else {
                        line = test;
                    }
                });
                if (line) {
                    ctx.fillText(line, x, ly);
                    ly += 20;
                }
            });

            // Notes
            if (state.notes) {
                ly += 10;
                ctx.fillStyle = COLORS.note;
                ctx.font = 'bold 11px Inter, sans-serif';
                ctx.fillText('Notes:', x, ly);
                ly += 15;
                ctx.fillStyle = COLORS.muted;
                ctx.font = '11px Inter, sans-serif';
                const preview = state.notes.substring(0, 150);
                ctx.fillText(preview, x, ly);
            }
        }

        destroy() {
            if (this.canvas.parentNode) {
                this.canvas.parentNode.removeChild(this.canvas);
            }
        }
    }

    // Register
    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['deduction'] = DeductionRenderer;
})();
