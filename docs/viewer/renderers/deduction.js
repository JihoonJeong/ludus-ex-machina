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
        contentBg: 'rgba(22, 33, 62, 0.8)',
    };

    class DeductionRenderer {
        constructor(container) {
            this.canvas = document.createElement('canvas');
            this.canvas.width = 1100;
            this.canvas.height = 700;
            container.appendChild(this.canvas);
            this.ctx = this.canvas.getContext('2d');
            // Store evidence content from log entries for viewer display
            this._evidenceContent = {};
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
                title: '',
                difficulty: '',
                suspects: {},
                lastReadFile: null,
                lastReadContent: null,
            };
        }

        applyMove(state, logEntry) {
            const s = { ...state, timeline: [...state.timeline] };
            const postMoveState = logEntry.post_move_state;
            const postMoveContext = logEntry.post_move_context;
            const agentId = logEntry.agent_id;
            const move = logEntry.envelope?.move || {};

            if (postMoveState) {
                const agent = postMoveState.agents?.[agentId];
                if (agent) {
                    s.filesRead = agent.files_read || [];
                    s.filesAvailable = agent.files_available || [];
                    s.notes = agent.notes || '';
                    s.submitted = agent.submitted || false;
                    s.answer = agent.answer;
                    // Capture last read content for viewer
                    if (agent.last_read_content) {
                        s.lastReadFile = move.file || null;
                        s.lastReadContent = agent.last_read_content;
                        if (move.file) {
                            this._evidenceContent[move.file] = agent.last_read_content;
                        }
                    }
                }
                s.title = postMoveState.scenario_id || state.title;
            }
            if (postMoveContext) {
                s.difficulty = postMoveContext.difficulty || state.difficulty;
                s.suspects = postMoveContext.suspect_names || state.suspects;
            }

            const entry = { agent: agentId, action: move.action };
            if (move.action === 'read') {
                entry.file = move.file;
            } else if (move.action === 'note') {
                entry.content = (move.content || '').substring(0, 200);
            } else if (move.action === 'submit') {
                entry.answer = move.answer;
            }
            s.timeline.push(entry);

            return s;
        }

        render(state, turn, lastMove, animate) {
            const ctx = this.ctx;
            const W = this.canvas.width;
            const H = this.canvas.height;

            ctx.fillStyle = COLORS.bg;
            ctx.fillRect(0, 0, W, H);

            // Title
            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 18px Inter, sans-serif';
            const title = state.title || 'Deduction';
            const diff = state.difficulty || '';
            ctx.fillText(`${title} (${diff})`, 20, 30);

            // Layout: evidence(220) | timeline+content(540) | verdict(300)
            this._renderEvidencePanel(ctx, state, 20, 50, 200, H - 70);
            this._renderCenterPanel(ctx, state, 240, 50, 540, H - 70);
            this._renderVerdictPanel(ctx, state, 800, 50, 280, H - 70);
        }

        _renderEvidencePanel(ctx, state, x, y, w, h) {
            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 12px Inter, sans-serif';
            ctx.fillText('EVIDENCE FILES', x, y + 15);

            const allFiles = [...new Set([...(state.filesRead || []), ...(state.filesAvailable || [])])].sort();
            const readSet = new Set(state.filesRead || []);

            const lineH = 20;
            const startY = y + 35;

            allFiles.forEach((file, i) => {
                const fy = startY + i * lineH;
                if (fy > y + h - 20) return;

                const isRead = readSet.has(file);
                const isLast = file === state.lastReadFile;

                ctx.fillStyle = isRead ? COLORS.read : COLORS.unread;
                ctx.fillRect(x, fy - 8, 6, 12);

                ctx.fillStyle = isLast ? COLORS.submit : (isRead ? COLORS.text : COLORS.muted);
                ctx.font = isLast ? 'bold 11px monospace' : '11px monospace';
                const displayName = this._truncate(ctx, file.replace('.md', ''), w - 16);
                ctx.fillText(displayName, x + 12, fy);
            });

            ctx.fillStyle = COLORS.secondary;
            ctx.font = '11px Inter, sans-serif';
            const total = allFiles.length;
            ctx.fillText(`${readSet.size}/${total} read`, x, y + h - 5);
        }

        _renderCenterPanel(ctx, state, x, y, w, h) {
            // Split: top = timeline, bottom = file content preview
            const timelineH = Math.min(200, 35 + (state.timeline || []).length * 24);
            const contentY = y + timelineH + 20;
            const contentH = h - timelineH - 20;

            // Timeline
            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 12px Inter, sans-serif';
            ctx.fillText('INVESTIGATION TIMELINE', x, y + 15);

            const timeline = state.timeline || [];
            const startY = y + 35;

            timeline.forEach((entry, i) => {
                const ty = startY + i * 24;
                if (ty > y + timelineH - 10) return;

                ctx.fillStyle = COLORS.muted;
                ctx.font = '11px monospace';
                ctx.fillText(`T${i + 1}`, x, ty);

                if (entry.action === 'read') {
                    ctx.fillStyle = COLORS.read;
                    ctx.font = '12px Inter, sans-serif';
                    ctx.fillText(`📄 Read: ${entry.file}`, x + 30, ty);
                } else if (entry.action === 'note') {
                    ctx.fillStyle = COLORS.note;
                    ctx.font = '12px Inter, sans-serif';
                    const preview = this._truncate(ctx, `📝 ${entry.content || ''}`, w - 40);
                    ctx.fillText(preview, x + 30, ty);
                } else if (entry.action === 'submit') {
                    ctx.fillStyle = COLORS.submit;
                    ctx.font = 'bold 12px Inter, sans-serif';
                    const ans = entry.answer || {};
                    ctx.fillText(`🎯 SUBMIT: Culprit=${ans.culprit || '?'}`, x + 30, ty);
                }
            });

            // File content preview
            if (state.lastReadContent && contentH > 40) {
                ctx.fillStyle = COLORS.contentBg;
                ctx.fillRect(x, contentY, w, contentH);
                ctx.strokeStyle = COLORS.border;
                ctx.strokeRect(x, contentY, w, contentH);

                ctx.fillStyle = COLORS.submit;
                ctx.font = 'bold 11px Inter, sans-serif';
                ctx.fillText(`📄 ${state.lastReadFile || 'Evidence'}`, x + 8, contentY + 16);

                ctx.fillStyle = COLORS.text;
                ctx.font = '11px Inter, sans-serif';
                const lines = this._wrapText(ctx, state.lastReadContent, w - 20);
                const maxLines = Math.floor((contentH - 30) / 15);
                lines.slice(0, maxLines).forEach((line, i) => {
                    ctx.fillText(line, x + 8, contentY + 34 + i * 15);
                });
                if (lines.length > maxLines) {
                    ctx.fillStyle = COLORS.muted;
                    ctx.fillText(`... (${lines.length - maxLines} more lines)`, x + 8, contentY + 34 + maxLines * 15);
                }
            }
        }

        _renderVerdictPanel(ctx, state, x, y, w, h) {
            ctx.fillStyle = COLORS.secondary;
            ctx.font = 'bold 12px Inter, sans-serif';
            ctx.fillText('VERDICT', x, y + 15);

            if (!state.submitted || !state.answer) {
                ctx.fillStyle = COLORS.muted;
                ctx.font = '12px Inter, sans-serif';
                ctx.fillText('Investigating...', x, y + 40);
                return;
            }

            const answer = state.answer;
            let ly = y + 40;

            // Suspects
            const suspects = state.suspects || {};
            if (Object.keys(suspects).length > 0) {
                ctx.fillStyle = COLORS.secondary;
                ctx.font = '11px Inter, sans-serif';
                ctx.fillText('Suspects:', x, ly);
                ly += 16;
                for (const [id, name] of Object.entries(suspects)) {
                    const isAccused = answer.culprit?.toUpperCase() === id.toUpperCase();
                    ctx.fillStyle = isAccused ? COLORS.submit : COLORS.muted;
                    ctx.font = isAccused ? 'bold 11px Inter, sans-serif' : '11px Inter, sans-serif';
                    const prefix = isAccused ? '▶ ' : '  ';
                    const displayName = this._truncate(ctx, `${prefix}${id}: ${name}`, w - 5);
                    ctx.fillText(displayName, x, ly);
                    ly += 15;
                }
                ly += 8;
            }

            // Answer
            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 13px Inter, sans-serif';
            ctx.fillText('Answer:', x, ly);
            ly += 18;

            const fields = [
                ['Culprit', answer.culprit],
                ['Motive', answer.motive],
                ['Method', answer.method],
            ];

            fields.forEach(([label, value]) => {
                ctx.fillStyle = COLORS.secondary;
                ctx.font = '11px Inter, sans-serif';
                ctx.fillText(label + ':', x, ly);
                ly += 14;
                ctx.fillStyle = COLORS.text;
                ctx.font = '12px Inter, sans-serif';
                const lines = this._wrapText(ctx, (value || '?').replace(/_/g, ' '), w - 5);
                lines.slice(0, 3).forEach(line => {
                    ctx.fillText(line, x, ly);
                    ly += 14;
                });
                ly += 4;
            });

            // Notes
            if (state.notes) {
                ly += 8;
                ctx.fillStyle = COLORS.note;
                ctx.font = 'bold 11px Inter, sans-serif';
                ctx.fillText('Notes:', x, ly);
                ly += 14;
                ctx.fillStyle = COLORS.muted;
                ctx.font = '11px Inter, sans-serif';
                const noteLines = this._wrapText(ctx, state.notes, w - 5);
                noteLines.slice(0, 5).forEach(line => {
                    ctx.fillText(line, x, ly);
                    ly += 13;
                });
            }
        }

        // Helpers

        _truncate(ctx, text, maxWidth) {
            if (ctx.measureText(text).width <= maxWidth) return text;
            let t = text;
            while (t.length > 3 && ctx.measureText(t + '...').width > maxWidth) {
                t = t.slice(0, -1);
            }
            return t + '...';
        }

        _wrapText(ctx, text, maxWidth) {
            const lines = [];
            const paragraphs = text.split('\n');
            for (const para of paragraphs) {
                if (!para.trim()) { lines.push(''); continue; }
                const words = para.split(' ');
                let line = '';
                for (const word of words) {
                    const test = line + (line ? ' ' : '') + word;
                    if (ctx.measureText(test).width > maxWidth && line) {
                        lines.push(line);
                        line = word;
                    } else {
                        line = test;
                    }
                }
                if (line) lines.push(line);
            }
            return lines;
        }

        destroy() {
            if (this.canvas.parentNode) {
                this.canvas.parentNode.removeChild(this.canvas);
            }
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['deduction'] = DeductionRenderer;
})();
