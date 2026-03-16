/**
 * Codenames renderer for LxM Match Viewer.
 * Canvas-based 5x5 word grid with team colors, clue history, and spymaster view toggle.
 */

(function () {
    const COLORS = {
        bg: '#1a1a2e',
        cardBg: '#16213e',
        cardBorder: '#2a2a4a',
        text: '#e0e0e0',
        muted: '#555577',
        secondary: '#8888aa',

        // Card colors (unrevealed)
        unrevealed: '#2a2a4a',
        unrevealedText: '#e0e0e0',

        // Revealed colors
        red: '#c0392b',
        redLight: 'rgba(192, 57, 43, 0.25)',
        blue: '#2980b9',
        blueLight: 'rgba(41, 128, 185, 0.25)',
        neutral: '#555577',
        neutralLight: 'rgba(85, 85, 119, 0.2)',
        assassin: '#111111',
        assassinText: '#ff4444',

        // Team indicators
        redTeam: '#e74c3c',
        blueTeam: '#3498db',
        gold: '#ffd700',
    };

    const CARD_COLORS = {
        red: { bg: COLORS.red, text: '#ffffff' },
        blue: { bg: COLORS.blue, text: '#ffffff' },
        neutral: { bg: COLORS.neutral, text: '#cccccc' },
        assassin: { bg: COLORS.assassin, text: COLORS.assassinText },
    };

    // Spymaster overlay colors (faded, for unrevealed)
    const SPY_OVERLAY = {
        red: 'rgba(192, 57, 43, 0.15)',
        blue: 'rgba(41, 128, 185, 0.15)',
        neutral: 'rgba(85, 85, 119, 0.10)',
        assassin: 'rgba(255, 68, 68, 0.12)',
    };

    class CodenamesRenderer {
        constructor(container) {
            this.canvas = document.createElement('canvas');
            this.canvas.width = 900;
            this.canvas.height = 780;
            container.appendChild(this.canvas);
            this.ctx = this.canvas.getContext('2d');
            this.showSpymasterView = false;

            // Toggle button
            this._addToggle(container);
        }

        _addToggle(container) {
            const btn = document.createElement('button');
            btn.textContent = 'Spymaster View';
            btn.style.cssText = 'position:absolute;bottom:8px;right:8px;padding:4px 10px;font-size:11px;' +
                'background:#2a2a4a;color:#8888aa;border:1px solid #444;border-radius:4px;cursor:pointer;z-index:10;';
            btn.addEventListener('click', () => {
                this.showSpymasterView = !this.showSpymasterView;
                btn.style.background = this.showSpymasterView ? '#3a3a5a' : '#2a2a4a';
                btn.style.color = this.showSpymasterView ? '#e0e0e0' : '#8888aa';
                // Re-render with current state
                if (this._lastRenderArgs) {
                    this.render(...this._lastRenderArgs);
                }
            });
            container.style.position = 'relative';
            container.appendChild(btn);
        }

        initialState(matchConfig) {
            const agents = matchConfig.agents || [];
            const teams = {};
            for (const a of agents) {
                if (a.team && a.role) {
                    if (!teams[a.team]) teams[a.team] = {};
                    teams[a.team][a.role] = a.agent_id;
                }
            }
            return {
                board: null,
                answerKey: null,
                teams,
                activeTeam: 'red',
                activeRole: 'spymaster',
                currentClue: null,
                guessesRemaining: 0,
                remaining: { red: 9, blue: 8 },
                clueHistory: [],
                guessHistory: [],
                agents: agents.map(a => a.agent_id),
                agentNames: Object.fromEntries(agents.map(a => [a.agent_id, a.display_name || a.agent_id])),
            };
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            const ctx = logEntry.post_move_context;
            if (!post) return state;

            return {
                ...state,
                board: post.board || state.board,
                answerKey: post.answer_key || state.answerKey,
                activeTeam: post.active_team || state.activeTeam,
                activeRole: post.active_role || state.activeRole,
                currentClue: post.current_clue,
                guessesRemaining: post.guesses_remaining ?? 0,
                remaining: post.remaining || state.remaining,
                clueHistory: ctx?.clue_history || state.clueHistory,
                guessHistory: ctx?.guess_history || state.guessHistory,
            };
        }

        render(state, turnNumber, lastMove, animate = false) {
            this._lastRenderArgs = [state, turnNumber, lastMove, animate];
            const ctx = this.ctx;
            const W = this.canvas.width;
            const H = this.canvas.height;

            // Background
            ctx.fillStyle = COLORS.bg;
            ctx.fillRect(0, 0, W, H);

            if (!state.board) {
                ctx.fillStyle = COLORS.muted;
                ctx.font = '16px -apple-system, sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('Waiting for game state...', W / 2, H / 2);
                return;
            }

            // Header: team scores
            this._drawHeader(ctx, W, state);

            // Board (5x5 grid)
            const boardY = 70;
            const boardW = W - 60;
            const boardH = 440;
            this._drawBoard(ctx, 30, boardY, boardW, boardH, state, lastMove);

            // Team panels
            this._drawTeamPanels(ctx, 30, boardY + boardH + 20, boardW, state);

            // Current action
            this._drawCurrentAction(ctx, W / 2, boardY + boardH + 110, state);

            // Clue history
            this._drawClueHistory(ctx, 30, boardY + boardH + 145, boardW, state);
        }

        _drawHeader(ctx, W, state) {
            const redRemaining = state.remaining?.red ?? '?';
            const blueRemaining = state.remaining?.blue ?? '?';

            ctx.font = 'bold 18px -apple-system, sans-serif';
            ctx.textAlign = 'center';

            // Red side
            ctx.fillStyle = COLORS.redTeam;
            ctx.fillText(`Red: ${redRemaining} remaining`, W * 0.25, 35);

            // Title
            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 20px -apple-system, sans-serif';
            ctx.fillText('CODENAMES', W / 2, 35);

            // Blue side
            ctx.fillStyle = COLORS.blueTeam;
            ctx.font = 'bold 18px -apple-system, sans-serif';
            ctx.fillText(`Blue: ${blueRemaining} remaining`, W * 0.75, 35);

            // Spymaster view indicator
            if (this.showSpymasterView) {
                ctx.fillStyle = COLORS.gold;
                ctx.font = '11px -apple-system, sans-serif';
                ctx.fillText('SPYMASTER VIEW', W / 2, 55);
            }
        }

        _drawBoard(ctx, x, y, w, h, state, lastMove) {
            const board = state.board;
            const key = state.answerKey;
            const gap = 6;
            const cellW = (w - gap * 4) / 5;
            const cellH = (h - gap * 4) / 5;

            const lastGuessWord = lastMove?.envelope?.move?.type === 'guess'
                ? lastMove.envelope.move.word?.toUpperCase() : null;

            for (let r = 0; r < 5; r++) {
                for (let c = 0; c < 5; c++) {
                    const cell = board[r][c];
                    const category = key ? key[r][c] : 'unknown';
                    const cx = x + c * (cellW + gap);
                    const cy = y + r * (cellH + gap);

                    // Draw card
                    if (cell.revealed) {
                        const colors = CARD_COLORS[cell.revealed_as] || CARD_COLORS.neutral;
                        ctx.fillStyle = colors.bg;
                        ctx.beginPath();
                        ctx.roundRect(cx, cy, cellW, cellH, 6);
                        ctx.fill();

                        // Word
                        ctx.fillStyle = colors.text;
                        ctx.font = `bold ${this._fontSize(cell.word, cellW)}px "SF Mono", monospace`;
                        ctx.textAlign = 'center';
                        ctx.fillText(cell.word, cx + cellW / 2, cy + cellH / 2 + 2);

                        // Category icon
                        ctx.font = '12px -apple-system, sans-serif';
                        ctx.fillText(
                            cell.revealed_as === 'assassin' ? '\u2620' : cell.revealed_as?.toUpperCase() || '',
                            cx + cellW / 2, cy + cellH - 10
                        );
                    } else {
                        // Unrevealed card
                        ctx.fillStyle = COLORS.unrevealed;
                        ctx.beginPath();
                        ctx.roundRect(cx, cy, cellW, cellH, 6);
                        ctx.fill();

                        // Spymaster view overlay
                        if (this.showSpymasterView && category !== 'unknown') {
                            ctx.fillStyle = SPY_OVERLAY[category] || SPY_OVERLAY.neutral;
                            ctx.beginPath();
                            ctx.roundRect(cx, cy, cellW, cellH, 6);
                            ctx.fill();

                            // Border hint
                            const hintColor = category === 'red' ? COLORS.redTeam :
                                category === 'blue' ? COLORS.blueTeam :
                                category === 'assassin' ? COLORS.assassinText : COLORS.muted;
                            ctx.strokeStyle = hintColor;
                            ctx.lineWidth = 2;
                            ctx.beginPath();
                            ctx.roundRect(cx + 1, cy + 1, cellW - 2, cellH - 2, 5);
                            ctx.stroke();
                        }

                        // Word
                        ctx.fillStyle = COLORS.unrevealedText;
                        ctx.font = `bold ${this._fontSize(cell.word, cellW)}px "SF Mono", monospace`;
                        ctx.textAlign = 'center';
                        ctx.fillText(cell.word, cx + cellW / 2, cy + cellH / 2 + 2);
                    }

                    // Highlight last guess
                    if (lastGuessWord && cell.word?.toUpperCase() === lastGuessWord) {
                        ctx.strokeStyle = COLORS.gold;
                        ctx.lineWidth = 3;
                        ctx.beginPath();
                        ctx.roundRect(cx - 1, cy - 1, cellW + 2, cellH + 2, 7);
                        ctx.stroke();
                    }
                }
            }
        }

        _fontSize(word, cellW) {
            if (!word) return 12;
            const maxW = cellW - 12;
            // Approximate: 8px per char at size 14
            const charW = word.length * 8;
            if (charW <= maxW) return 14;
            return Math.max(9, Math.floor(14 * maxW / charW));
        }

        _drawTeamPanels(ctx, x, y, w, state) {
            const panelW = w / 2 - 10;

            // Red team
            this._drawTeamPanel(ctx, x, y, panelW, 'red', state);
            // Blue team
            this._drawTeamPanel(ctx, x + panelW + 20, y, panelW, 'blue', state);
        }

        _drawTeamPanel(ctx, x, y, w, team, state) {
            const isActive = state.activeTeam === team;
            const teamColor = team === 'red' ? COLORS.redTeam : COLORS.blueTeam;
            const teams = state.teams || {};
            const teamData = teams[team] || {};

            // Panel bg
            ctx.fillStyle = isActive ? (team === 'red' ? COLORS.redLight : COLORS.blueLight) : COLORS.cardBg;
            ctx.beginPath();
            ctx.roundRect(x, y, w, 65, 6);
            ctx.fill();

            if (isActive) {
                ctx.strokeStyle = teamColor;
                ctx.lineWidth = 2;
                ctx.stroke();
            }

            // Team name
            ctx.fillStyle = teamColor;
            ctx.font = 'bold 14px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(`${team.toUpperCase()} TEAM`, x + 12, y + 20);

            // Agent names
            ctx.fillStyle = COLORS.secondary;
            ctx.font = '11px "SF Mono", monospace';
            const spyName = state.agentNames?.[teamData.spymaster] || teamData.spymaster || '?';
            const guessName = state.agentNames?.[teamData.guesser] || teamData.guesser || '?';
            ctx.fillText(`Spy: ${spyName}`, x + 12, y + 38);
            ctx.fillText(`Guess: ${guessName}`, x + 12, y + 54);
        }

        _drawCurrentAction(ctx, cx, y, state) {
            const teamColor = state.activeTeam === 'red' ? COLORS.redTeam : COLORS.blueTeam;
            const roleLabel = state.activeRole === 'spymaster' ? "Spymaster's turn" : "Guesser's turn";

            ctx.fillStyle = teamColor;
            ctx.font = 'bold 13px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`${state.activeTeam?.toUpperCase()} ${roleLabel}`, cx, y);

            if (state.currentClue) {
                ctx.fillStyle = COLORS.text;
                ctx.font = 'bold 13px "SF Mono", monospace';
                ctx.fillText(
                    `Clue: "${state.currentClue.word}" for ${state.currentClue.number} (${state.guessesRemaining} guesses left)`,
                    cx, y + 18
                );
            }
        }

        _drawClueHistory(ctx, x, y, w, state) {
            const history = state.clueHistory || [];
            const guesses = state.guessHistory || [];
            if (history.length === 0) return;

            ctx.fillStyle = COLORS.muted;
            ctx.font = '11px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText('CLUE HISTORY', x, y);

            const lineH = 16;
            const maxLines = 8;
            const startIdx = Math.max(0, history.length - maxLines);

            for (let i = startIdx; i < history.length; i++) {
                const clue = history[i];
                const ly = y + 16 + (i - startIdx) * lineH;
                const teamColor = clue.team === 'red' ? COLORS.redTeam : COLORS.blueTeam;

                // Team dot
                ctx.fillStyle = teamColor;
                ctx.beginPath();
                ctx.arc(x + 6, ly - 3, 4, 0, Math.PI * 2);
                ctx.fill();

                // Clue text
                ctx.fillStyle = COLORS.text;
                ctx.font = '12px "SF Mono", monospace';
                ctx.textAlign = 'left';
                let text = `T${clue.turn}: "${clue.word}" ${clue.number}`;

                // Append guess results for this clue
                const clueGuesses = guesses.filter(g => g.team === clue.team);
                // Group by turn range (approximate)
                const guessStr = clueGuesses
                    .slice(-clue.number - 1)
                    .map(g => `${g.word}${g.correct ? '\u2713' : '\u2717'}`)
                    .join(' ');
                if (guessStr) text += ` \u2192 ${guessStr}`;

                ctx.fillText(text, x + 16, ly);
            }
        }

        renderResult(result, state) {
            // Result overlay handled by app.js
        }

        formatMoveSummary(logEntry) {
            const move = logEntry.envelope?.move;
            if (!move) return '?';
            if (move.type === 'clue') return `Clue: "${move.word}" ${move.number}`;
            if (move.type === 'guess') return `Guess: ${move.word}`;
            if (move.type === 'pass') return 'Pass';
            return '?';
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['codenames'] = CodenamesRenderer;
})();
