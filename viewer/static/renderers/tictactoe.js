/**
 * Tic-Tac-Toe renderer for LxM Match Viewer.
 * Polished version with animations, coordinate labels, and cell highlights.
 */
class TicTacToeRenderer {
    constructor(containerElement) {
        this.container = containerElement;
        this.canvas = document.createElement('canvas');
        // Use higher resolution for crisp rendering
        this.canvas.width = 480 * 2;
        this.canvas.height = 480 * 2;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.ctx.scale(2, 2);  // HiDPI scaling
        this._animationId = null;
        this._prevState = null;
    }

    initialState(matchConfig) {
        const agents = matchConfig.agents || [];
        const marks = {};
        if (agents[0]) marks[agents[0].agent_id] = 'X';
        if (agents[1]) marks[agents[1].agent_id] = 'O';
        return {
            board: [[null, null, null], [null, null, null], [null, null, null]],
            marks
        };
    }

    applyMove(state, logEntry) {
        const newBoard = state.board.map(row => [...row]);
        const move = logEntry.envelope.move;
        if (move.type === 'pass') return { ...state, board: newBoard };
        const [row, col] = move.position;
        const mark = state.marks[logEntry.agent_id];
        newBoard[row][col] = mark;
        return { ...state, board: newBoard };
    }

    render(state, turnNumber, lastMove, animate = false) {
        if (this._animationId) {
            cancelAnimationFrame(this._animationId);
            this._animationId = null;
        }

        const lastPos = lastMove?.envelope?.move?.type === 'place'
            ? lastMove.envelope.move.position : null;

        if (animate && lastPos) {
            this._animateTransition(state, lastPos, lastMove);
        } else {
            this._drawBoard(state, lastPos, 1.0);
        }
    }

    _drawBoard(state, highlightPos, newMarkOpacity) {
        const ctx = this.ctx;
        const W = 480;
        const pad = 40;
        const innerSize = W - pad * 2;
        const cell = innerSize / 3;

        // Clear
        ctx.clearRect(0, 0, W, W);

        // Coordinate labels
        ctx.fillStyle = '#444466';
        ctx.font = '11px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        for (let i = 0; i < 3; i++) {
            const x = pad + i * cell + cell / 2;
            ctx.fillText(i.toString(), x, pad - 16);  // column labels
            const y = pad + i * cell + cell / 2;
            ctx.fillText(i.toString(), pad - 16, y);   // row labels
        }

        // Highlight cell background for last move
        if (highlightPos) {
            const [hr, hc] = highlightPos;
            const hx = pad + hc * cell;
            const hy = pad + hr * cell;
            ctx.fillStyle = 'rgba(255, 215, 0, 0.04)';
            ctx.fillRect(hx, hy, cell, cell);
        }

        // Grid lines
        ctx.strokeStyle = '#2a2a4a';
        ctx.lineWidth = 2;
        for (let i = 1; i < 3; i++) {
            const pos = pad + i * cell;
            ctx.beginPath();
            ctx.moveTo(pos, pad);
            ctx.lineTo(pos, W - pad);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(pad, pos);
            ctx.lineTo(W - pad, pos);
            ctx.stroke();
        }

        // Cell hover dots for empty cells (subtle guide)
        for (let r = 0; r < 3; r++) {
            for (let c = 0; c < 3; c++) {
                if (state.board[r][c]) continue;
                const cx = pad + c * cell + cell / 2;
                const cy = pad + r * cell + cell / 2;
                ctx.fillStyle = 'rgba(42, 42, 74, 0.5)';
                ctx.beginPath();
                ctx.arc(cx, cy, 3, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Draw marks
        for (let r = 0; r < 3; r++) {
            for (let c = 0; c < 3; c++) {
                const mark = state.board[r][c];
                if (!mark) continue;
                const cx = pad + c * cell + cell / 2;
                const cy = pad + r * cell + cell / 2;
                const isLast = highlightPos && highlightPos[0] === r && highlightPos[1] === c;
                const opacity = isLast ? newMarkOpacity : (isLast ? 1.0 : 0.65);
                this._drawMark(mark, cx, cy, cell, opacity, isLast);
            }
        }
    }

    _drawMark(mark, cx, cy, cellSize, opacity, highlight = false) {
        const ctx = this.ctx;
        const size = cellSize * 0.3;

        ctx.save();
        ctx.globalAlpha = opacity;

        if (mark === 'X') {
            ctx.strokeStyle = '#00d4ff';
            ctx.lineWidth = highlight ? 5 : 3.5;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(cx - size, cy - size);
            ctx.lineTo(cx + size, cy + size);
            ctx.stroke();
            ctx.beginPath();
            ctx.moveTo(cx + size, cy - size);
            ctx.lineTo(cx - size, cy + size);
            ctx.stroke();
            // Glow for highlighted
            if (highlight && opacity >= 0.9) {
                ctx.globalAlpha = 0.15;
                ctx.shadowColor = '#00d4ff';
                ctx.shadowBlur = 16;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(cx - size, cy - size);
                ctx.lineTo(cx + size, cy + size);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(cx + size, cy - size);
                ctx.lineTo(cx - size, cy + size);
                ctx.stroke();
                ctx.shadowBlur = 0;
            }
        } else {
            ctx.strokeStyle = '#ff6b35';
            ctx.lineWidth = highlight ? 5 : 3.5;
            ctx.beginPath();
            ctx.arc(cx, cy, size, 0, Math.PI * 2);
            ctx.stroke();
            if (highlight && opacity >= 0.9) {
                ctx.globalAlpha = 0.15;
                ctx.shadowColor = '#ff6b35';
                ctx.shadowBlur = 16;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(cx, cy, size, 0, Math.PI * 2);
                ctx.stroke();
                ctx.shadowBlur = 0;
            }
        }

        ctx.restore();
    }

    _animateTransition(state, highlightPos, lastMove) {
        const duration = 250;
        let start = null;

        // Easing: ease-out cubic
        const ease = t => 1 - Math.pow(1 - t, 3);

        const frame = (ts) => {
            if (!start) start = ts;
            const progress = Math.min((ts - start) / duration, 1);
            const eased = ease(progress);

            this._drawBoard(state, highlightPos, eased);

            if (progress < 1) {
                this._animationId = requestAnimationFrame(frame);
            } else {
                this._animationId = null;
            }
        };
        this._animationId = requestAnimationFrame(frame);
    }

    renderResult(result, state) {
        if (!result) return;

        if (result.outcome === 'win') {
            const winLine = this._findWinLine(state.board);
            if (winLine) {
                this._animateWinLine(winLine);
            }
        }
    }

    _findWinLine(board) {
        const lines = [
            [[0,0],[0,1],[0,2]], [[1,0],[1,1],[1,2]], [[2,0],[2,1],[2,2]],
            [[0,0],[1,0],[2,0]], [[0,1],[1,1],[2,1]], [[0,2],[1,2],[2,2]],
            [[0,0],[1,1],[2,2]], [[0,2],[1,1],[2,0]],
        ];
        for (const line of lines) {
            const vals = line.map(([r, c]) => board[r][c]);
            if (vals[0] && vals[0] === vals[1] && vals[1] === vals[2]) {
                return line;
            }
        }
        return null;
    }

    _animateWinLine(line) {
        const ctx = this.ctx;
        const pad = 40;
        const cell = (480 - pad * 2) / 3;

        const toXY = ([r, c]) => ({
            x: pad + c * cell + cell / 2,
            y: pad + r * cell + cell / 2,
        });

        const start = toXY(line[0]);
        const end = toXY(line[2]);
        const duration = 400;
        let startTime = null;

        const ease = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

        const frame = (ts) => {
            if (!startTime) startTime = ts;
            const progress = Math.min((ts - startTime) / duration, 1);
            const eased = ease(progress);

            // Draw partial line
            const currentX = start.x + (end.x - start.x) * eased;
            const currentY = start.y + (end.y - start.y) * eased;

            ctx.save();
            // Glow
            ctx.strokeStyle = '#ffd700';
            ctx.lineWidth = 8;
            ctx.lineCap = 'round';
            ctx.globalAlpha = 0.3;
            ctx.shadowColor = '#ffd700';
            ctx.shadowBlur = 20;
            ctx.beginPath();
            ctx.moveTo(start.x, start.y);
            ctx.lineTo(currentX, currentY);
            ctx.stroke();
            // Main line
            ctx.globalAlpha = 0.85;
            ctx.lineWidth = 5;
            ctx.shadowBlur = 0;
            ctx.beginPath();
            ctx.moveTo(start.x, start.y);
            ctx.lineTo(currentX, currentY);
            ctx.stroke();
            ctx.restore();

            if (progress < 1) {
                requestAnimationFrame(frame);
            }
        };
        requestAnimationFrame(frame);
    }

    _drawWinLine(line) {
        const ctx = this.ctx;
        const pad = 40;
        const cell = (480 - pad * 2) / 3;
        const toXY = ([r, c]) => ({
            x: pad + c * cell + cell / 2,
            y: pad + r * cell + cell / 2,
        });
        const start = toXY(line[0]);
        const end = toXY(line[2]);

        ctx.save();
        ctx.strokeStyle = '#ffd700';
        ctx.lineWidth = 5;
        ctx.lineCap = 'round';
        ctx.globalAlpha = 0.85;
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
        ctx.restore();
    }

    formatMoveSummary(logEntry) {
        const move = logEntry.envelope.move;
        if (move.type === 'pass') return 'passed (timeout)';
        const [r, c] = move.position;
        return `placed at (${r}, ${c})`;
    }
}

// Register renderer
window.LxMRenderers = window.LxMRenderers || {};
window.LxMRenderers.tictactoe = TicTacToeRenderer;
