/**
 * Chess renderer for LxM Match Viewer.
 * Uses post_move_state from log entries to reconstruct board positions.
 */
class ChessRenderer {
    constructor(containerElement) {
        this.container = containerElement;
        this.canvas = document.createElement('canvas');
        this.canvas.width = 480 * 2;
        this.canvas.height = 480 * 2;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.ctx.scale(2, 2);
    }

    initialState(matchConfig) {
        const agents = matchConfig.agents || [];
        const colors = {};
        if (agents[0]) colors[agents[0].agent_id] = 'white';
        if (agents[1]) colors[agents[1].agent_id] = 'black';
        return {
            board: this._startingBoard(),
            colors,
            lastMove: null,
            inCheck: false,
            sideToMove: 'white',
        };
    }

    applyMove(state, logEntry) {
        const post = logEntry.post_move_state;
        if (post) {
            return {
                ...state,
                board: this._parseBoardVisual(post.board_visual),
                lastMove: post.last_move,
                inCheck: post.in_check || false,
                sideToMove: post.side_to_move || 'white',
            };
        }
        // Fallback: try to parse from envelope
        return state;
    }

    render(state, turnNumber, lastMove, animate = false) {
        this._drawBoard(state);
    }

    renderResult(result, state) {
        // No special win-line rendering for chess (unlike tic-tac-toe)
    }

    formatMoveSummary(logEntry) {
        const last = logEntry.post_move_state?.last_move;
        if (last?.san) {
            let text = last.san;
            if (last.captured) text += ` (captured)`;
            if (last.is_castling) text = last.san + ' (castles)';
            return text;
        }
        return logEntry.envelope?.move?.notation || '?';
    }

    // ── Drawing ──

    _drawBoard(state) {
        const ctx = this.ctx;
        const W = 480;
        const pad = 28;
        const boardSize = W - pad * 2;
        const sq = boardSize / 8;

        const LIGHT = '#f0d9b5';
        const DARK = '#b58863';
        const HIGHLIGHT_FROM = 'rgba(255, 255, 0, 0.35)';
        const HIGHLIGHT_TO = 'rgba(255, 255, 0, 0.45)';
        const CHECK_COLOR = 'rgba(255, 50, 50, 0.55)';

        // Background
        ctx.fillStyle = '#1a1a2e';
        ctx.fillRect(0, 0, W, W);

        // Squares
        for (let r = 0; r < 8; r++) {
            for (let f = 0; f < 8; f++) {
                const x = pad + f * sq;
                const y = pad + r * sq;
                ctx.fillStyle = (r + f) % 2 === 0 ? LIGHT : DARK;
                ctx.fillRect(x, y, sq, sq);
            }
        }

        // Highlight last move squares
        const lm = state.lastMove;
        if (lm && lm.from && lm.to) {
            const fromCoords = this._algebraicToCoords(lm.from);
            const toCoords = this._algebraicToCoords(lm.to);
            if (fromCoords) {
                ctx.fillStyle = HIGHLIGHT_FROM;
                ctx.fillRect(pad + fromCoords.f * sq, pad + fromCoords.r * sq, sq, sq);
            }
            if (toCoords) {
                ctx.fillStyle = HIGHLIGHT_TO;
                ctx.fillRect(pad + toCoords.f * sq, pad + toCoords.r * sq, sq, sq);
            }
        }

        // Highlight check
        if (state.inCheck) {
            const kingChar = state.sideToMove === 'white' ? 'K' : 'k';
            for (let r = 0; r < 8; r++) {
                for (let f = 0; f < 8; f++) {
                    if (state.board[r][f] === kingChar) {
                        ctx.fillStyle = CHECK_COLOR;
                        ctx.fillRect(pad + f * sq, pad + r * sq, sq, sq);
                    }
                }
            }
        }

        // Pieces
        const PIECE_CHARS = {
            'K': '\u2654', 'Q': '\u2655', 'R': '\u2656', 'B': '\u2657', 'N': '\u2658', 'P': '\u2659',
            'k': '\u265A', 'q': '\u265B', 'r': '\u265C', 'b': '\u265D', 'n': '\u265E', 'p': '\u265F',
        };

        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.font = `${sq * 0.75}px serif`;

        for (let r = 0; r < 8; r++) {
            for (let f = 0; f < 8; f++) {
                const piece = state.board[r][f];
                if (!piece || piece === '.') continue;
                const ch = PIECE_CHARS[piece];
                if (!ch) continue;
                const x = pad + f * sq + sq / 2;
                const y = pad + r * sq + sq / 2;

                // Text shadow for visibility
                ctx.fillStyle = 'rgba(0,0,0,0.3)';
                ctx.fillText(ch, x + 1, y + 1);
                ctx.fillStyle = piece === piece.toUpperCase() ? '#ffffff' : '#1a1a2e';
                ctx.fillText(ch, x, y);
            }
        }

        // File labels (a-h)
        ctx.font = '11px -apple-system, sans-serif';
        ctx.fillStyle = '#666688';
        ctx.textBaseline = 'top';
        for (let f = 0; f < 8; f++) {
            ctx.fillText('abcdefgh'[f], pad + f * sq + sq / 2, pad + boardSize + 4);
        }
        // Rank labels (8-1)
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'right';
        for (let r = 0; r < 8; r++) {
            ctx.fillText((8 - r).toString(), pad - 6, pad + r * sq + sq / 2);
        }
    }

    // ── Helpers ──

    _startingBoard() {
        return [
            ['r','n','b','q','k','b','n','r'],
            ['p','p','p','p','p','p','p','p'],
            ['.','.','.','.','.','.','.','.'],
            ['.','.','.','.','.','.','.','.'],
            ['.','.','.','.','.','.','.','.'],
            ['.','.','.','.','.','.','.','.'],
            ['P','P','P','P','P','P','P','P'],
            ['R','N','B','Q','K','B','N','R'],
        ];
    }

    _parseBoardVisual(boardVisual) {
        if (!boardVisual || !Array.isArray(boardVisual)) return this._startingBoard();
        return boardVisual.map(row => row.split(' '));
    }

    _algebraicToCoords(sq) {
        if (!sq || sq.length < 2) return null;
        const f = sq.charCodeAt(0) - 97; // 'a' = 0
        const r = 8 - parseInt(sq[1]);    // '8' = 0, '1' = 7
        if (f < 0 || f > 7 || r < 0 || r > 7) return null;
        return { r, f };
    }
}

// Register renderer
window.LxMRenderers = window.LxMRenderers || {};
window.LxMRenderers.chess = ChessRenderer;
