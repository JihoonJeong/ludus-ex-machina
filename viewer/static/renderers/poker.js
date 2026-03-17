/**
 * Poker renderer for LxM Match Viewer.
 * Canvas-based poker table with player positions, cards, chips, and betting.
 */

(function () {
    const COLORS = {
        bg: '#1a1a2e',
        felt: '#0d4f2b',
        feltBorder: '#1a6b3a',
        cardBg: '#ffffff',
        cardBack: '#2a2a4a',
        cardBorder: '#888888',
        cardRed: '#c0392b',
        cardBlack: '#1a1a2e',
        text: '#e0e0e0',
        muted: '#555577',
        secondary: '#8888aa',
        gold: '#ffd700',
        pot: '#ffd700',
        chipGreen: '#2ecc71',
        chipRed: '#e74c3c',
        chipBlue: '#3498db',
        chipBlack: '#2c3e50',
        active: 'rgba(255, 215, 0, 0.3)',
        folded: 'rgba(85, 85, 119, 0.5)',
        eliminated: 'rgba(100, 30, 30, 0.5)',
        allIn: '#ff6b35',
        dealer: '#ffd700',
        blind: '#8888aa',
    };

    const SUITS = { h: '\u2665', d: '\u2666', c: '\u2663', s: '\u2660' };
    const SUIT_COLORS = { h: COLORS.cardRed, d: COLORS.cardRed, c: COLORS.cardBlack, s: COLORS.cardBlack };

    function displayRank(r) { return r === 'T' ? '10' : r; }

    class PokerRenderer {
        constructor(containerElement) {
            this.container = containerElement;
            this.canvas = document.createElement('canvas');
            this.W = 1000;
            this.H = 800;
            this.canvas.width = this.W * 2;
            this.canvas.height = this.H * 2;
            this.canvas.style.width = '100%';
            this.canvas.style.height = '100%';
            this.container.appendChild(this.canvas);
            this.ctx = this.canvas.getContext('2d');
            this.ctx.scale(2, 2);
            this._showAllCards = false;
            this._lastRenderArgs = null;

            // God view toggle
            this.canvas.addEventListener('click', (e) => {
                const rect = this.canvas.getBoundingClientRect();
                const sx = this.W / rect.width;
                const x = (e.clientX - rect.left) * sx;
                const y = (e.clientY - rect.top) * (this.H / rect.height);
                if (x >= this.W - 140 && x <= this.W - 10 && y >= this.H - 40 && y <= this.H - 10) {
                    this._showAllCards = !this._showAllCards;
                    if (this._lastRenderArgs) this.render(...this._lastRenderArgs);
                }
            });
        }

        initialState(matchConfig) {
            const agents = matchConfig.agents || [];
            const players = {};
            agents.forEach(a => {
                players[a.agent_id] = {
                    chips: 1000, hole_cards: [], status: 'active',
                    current_bet: 0, total_bet_this_hand: 0,
                };
            });
            return {
                hand_number: 0, phase: 'pre_deal', community_cards: [],
                pot: 0, current_bet: 0, players,
                seat_order: agents.map(a => a.agent_id),
                blinds: { small: 10, big: 20 }, dealer_seat: 0,
            };
        }

        render(state, turnNumber, lastMove, animate = false) {
            this._lastRenderArgs = [state, turnNumber, lastMove, animate];
            const ctx = this.ctx;
            const W = this.W, H = this.H;
            const game = state.game || {};
            const current = game.current || this.initialState({ agents: [] });
            const context = game.context || {};

            // Background
            ctx.fillStyle = COLORS.bg;
            ctx.fillRect(0, 0, W, H);

            // Table
            this._drawTable(ctx, W, H);

            // Players
            const seats = current.seat_order || [];
            const positions = this._getPlayerPositions(seats.length, W, H);

            seats.forEach((pid, i) => {
                const player = current.players[pid] || {};
                const pos = positions[i];
                const isActive = current.action_on === pid;
                const isDealer = i === current.dealer_seat;
                this._drawPlayer(ctx, pos, pid, player, isActive, isDealer, current);
            });

            // Community cards
            this._drawCommunityCards(ctx, current.community_cards || [], W, H);

            // Pot
            this._drawPot(ctx, current.pot, current.side_pots, W, H);

            // Header
            this._drawHeader(ctx, current, context, W);

            // God view toggle
            this._drawToggle(ctx, W, H);

            // Last action
            if (lastMove && lastMove.move) {
                this._drawLastAction(ctx, lastMove, W, H);
            }
        }

        _drawTable(ctx, W, H) {
            const cx = W / 2, cy = H / 2 + 20;
            const rx = 360, ry = 210;

            // Shadow
            ctx.save();
            ctx.shadowColor = 'rgba(0,0,0,0.5)';
            ctx.shadowBlur = 30;
            ctx.beginPath();
            ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
            ctx.fillStyle = COLORS.felt;
            ctx.fill();
            ctx.restore();

            // Rim (wood-like border)
            ctx.beginPath();
            ctx.ellipse(cx, cy, rx + 4, ry + 4, 0, 0, Math.PI * 2);
            ctx.strokeStyle = '#5a3a1a';
            ctx.lineWidth = 8;
            ctx.stroke();

            // Felt border
            ctx.beginPath();
            ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
            ctx.strokeStyle = COLORS.feltBorder;
            ctx.lineWidth = 2;
            ctx.stroke();

            // Inner line
            ctx.beginPath();
            ctx.ellipse(cx, cy, rx - 20, ry - 14, 0, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(26, 107, 58, 0.4)';
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        _getPlayerPositions(n, W, H) {
            const cx = W / 2, cy = H / 2 + 20;
            const rx = 410, ry = 300;
            const positions = [];
            const startAngle = Math.PI / 2;
            for (let i = 0; i < n; i++) {
                const angle = startAngle + (i / n) * Math.PI * 2;
                positions.push({
                    x: cx + rx * Math.cos(angle),
                    y: cy + ry * Math.sin(angle),
                });
            }
            return positions;
        }

        _drawPlayer(ctx, pos, pid, player, isActive, isDealer, current) {
            const x = pos.x, y = pos.y;
            const cw = 50, ch = 70, gap = 6;
            const hasCards = player.status !== 'eliminated' &&
                (player.hole_cards || []).length === 2;

            // Total panel: info + cards stacked vertically
            const infoW = 170, infoH = 54;
            const panelH = hasCards ? infoH + ch + 8 : infoH;
            const panelTop = y - panelH / 2;

            ctx.save();
            if (player.status === 'eliminated') ctx.globalAlpha = 0.3;

            // Info box
            const bx = x - infoW / 2, by = panelTop;
            ctx.fillStyle = isActive ? COLORS.active : 'rgba(30, 30, 55, 0.9)';
            if (player.status === 'folded') ctx.fillStyle = COLORS.folded;
            if (player.status === 'eliminated') ctx.fillStyle = COLORS.eliminated;

            ctx.beginPath();
            ctx.roundRect(bx, by, infoW, infoH, 8);
            ctx.fill();

            // Border glow for active
            if (isActive) {
                ctx.save();
                ctx.shadowColor = COLORS.gold;
                ctx.shadowBlur = 12;
                ctx.strokeStyle = COLORS.gold;
                ctx.lineWidth = 2;
                ctx.stroke();
                ctx.restore();
            } else {
                ctx.strokeStyle = player.status === 'all_in' ? COLORS.allIn : '#3a3a5a';
                ctx.lineWidth = 1;
                ctx.stroke();
            }

            // Name
            const displayName = pid.length > 16 ? pid.slice(0, 15) + '…' : pid;
            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 14px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(displayName, x, by + 20);

            // Chips + status
            ctx.font = '13px "SF Mono", monospace';
            if (player.status === 'all_in') {
                ctx.fillStyle = COLORS.allIn;
                ctx.fillText(`ALL IN  ·  ${player.chips || 0}`, x, by + 38);
            } else if (player.status === 'folded') {
                ctx.fillStyle = COLORS.muted;
                ctx.fillText(`FOLD  ·  ${player.chips || 0}`, x, by + 38);
            } else if (player.status === 'eliminated') {
                ctx.fillStyle = '#ff4444';
                ctx.font = 'bold 12px -apple-system, sans-serif';
                ctx.fillText('ELIMINATED', x, by + 38);
            } else {
                ctx.fillStyle = COLORS.chipGreen;
                ctx.fillText(`${player.chips || 0}`, x, by + 38);
            }

            // Current bet
            if (player.current_bet > 0 && player.status !== 'eliminated') {
                ctx.fillStyle = COLORS.gold;
                ctx.font = 'bold 12px "SF Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText(`Bet: ${player.current_bet}`, x, by + infoH + ch + 20);
            }

            ctx.restore();

            // Hole cards — centered below info box
            if (hasCards) {
                const cards = player.hole_cards;
                const showFace = this._showAllCards ||
                    (cards[0] !== '??' && cards[1] !== '??') ||
                    current.phase === 'hand_complete';
                const totalCW = cw * 2 + gap;
                const cardX = x - totalCW / 2;
                const cardY = by + infoH + 4;
                this._drawHoleCard(ctx, cardX, cardY, cw, ch, cards[0], showFace);
                this._drawHoleCard(ctx, cardX + cw + gap, cardY, cw, ch, cards[1], showFace);
            }

            // Dealer button
            if (isDealer) {
                ctx.fillStyle = COLORS.dealer;
                ctx.beginPath();
                ctx.arc(bx + infoW + 10, by + 10, 12, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = '#000';
                ctx.font = 'bold 12px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('D', bx + infoW + 10, by + 10);
                ctx.textBaseline = 'alphabetic';
            }
        }

        _drawHoleCard(ctx, x, y, w, h, card, showFace) {
            if (!showFace || card === '??') {
                // Card back
                ctx.save();
                ctx.shadowColor = 'rgba(0,0,0,0.4)';
                ctx.shadowBlur = 6;
                ctx.shadowOffsetY = 2;
                ctx.fillStyle = '#1a3a6a';
                ctx.beginPath();
                ctx.roundRect(x, y, w, h, 5);
                ctx.fill();
                ctx.restore();
                ctx.strokeStyle = '#3a5a8a';
                ctx.lineWidth = 0.5;
                ctx.beginPath();
                ctx.roundRect(x, y, w, h, 5);
                ctx.stroke();
                // Inner pattern
                ctx.strokeStyle = '#2a4a7a';
                ctx.lineWidth = 0.5;
                const m = 5;
                ctx.beginPath();
                ctx.roundRect(x + m, y + m, w - m * 2, h - m * 2, 3);
                ctx.stroke();
                return;
            }

            // Card face
            ctx.save();
            ctx.shadowColor = 'rgba(0,0,0,0.4)';
            ctx.shadowBlur = 6;
            ctx.shadowOffsetY = 2;
            ctx.fillStyle = COLORS.cardBg;
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 5);
            ctx.fill();
            ctx.restore();

            ctx.strokeStyle = '#bbb';
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 5);
            ctx.stroke();

            const rank = displayRank(card[0]);
            const suit = card[1];
            const color = SUIT_COLORS[suit] || COLORS.cardBlack;

            // Top-left corner
            ctx.fillStyle = color;
            ctx.font = 'bold 15px "SF Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(rank, x + 4, y + 17);
            ctx.font = '14px sans-serif';
            ctx.fillText(SUITS[suit] || suit, x + 4, y + 31);

            // Center suit large
            ctx.font = '24px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(SUITS[suit] || suit, x + w / 2, y + h / 2 + 8);
        }

        _drawCommunityCards(ctx, cards, W, H) {
            if (!cards || cards.length === 0) return;

            const centerX = W / 2;
            const centerY = H / 2 + 10;
            const cardW = 54, cardH = 76, gap = 10;
            const totalW = cards.length * cardW + (cards.length - 1) * gap;
            const startX = centerX - totalW / 2;

            cards.forEach((card, i) => {
                const x = startX + i * (cardW + gap);
                const y = centerY - cardH / 2;
                this._drawCommunityCard(ctx, x, y, cardW, cardH, card);
            });
        }

        _drawCommunityCard(ctx, x, y, w, h, card) {
            // Shadow
            ctx.save();
            ctx.shadowColor = 'rgba(0,0,0,0.4)';
            ctx.shadowBlur = 8;
            ctx.shadowOffsetY = 3;
            ctx.fillStyle = COLORS.cardBg;
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 5);
            ctx.fill();
            ctx.restore();

            ctx.strokeStyle = '#ccc';
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 5);
            ctx.stroke();

            if (!card || card === '??') return;

            const rank = displayRank(card[0]);
            const suit = card[1];
            const color = SUIT_COLORS[suit] || COLORS.cardBlack;

            // Top-left corner
            ctx.fillStyle = color;
            ctx.font = 'bold 16px "SF Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(rank, x + 5, y + 18);
            ctx.font = '14px sans-serif';
            ctx.fillText(SUITS[suit] || suit, x + 5, y + 33);

            // Center suit large
            ctx.font = '26px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(SUITS[suit] || suit, x + w / 2, y + h / 2 + 10);

            // Bottom-right corner (inverted)
            ctx.save();
            ctx.translate(x + w - 5, y + h - 5);
            ctx.rotate(Math.PI);
            ctx.font = 'bold 16px "SF Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(rank, 0, 13);
            ctx.font = '14px sans-serif';
            ctx.fillText(SUITS[suit] || suit, 0, 28);
            ctx.restore();
        }

        _drawPot(ctx, pot, sidePots, W, H) {
            if (!pot && (!sidePots || sidePots.length === 0)) return;
            const cx = W / 2, cy = H / 2 + 70;

            // Pot chip icon
            ctx.fillStyle = 'rgba(255, 215, 0, 0.15)';
            ctx.beginPath();
            ctx.arc(cx, cy - 2, 24, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = COLORS.pot;
            ctx.font = 'bold 16px "SF Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(`POT: ${pot || 0}`, cx, cy + 5);
        }

        _drawHeader(ctx, current, context, W) {
            ctx.fillStyle = 'rgba(26, 26, 46, 0.9)';
            ctx.fillRect(0, 0, W, 44);

            ctx.fillStyle = COLORS.text;
            ctx.font = 'bold 14px -apple-system, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(`Hand #${current.hand_number || 0}`, 16, 28);

            ctx.fillStyle = COLORS.secondary;
            ctx.font = '13px -apple-system, sans-serif';
            const blinds = current.blinds || {};
            ctx.fillText(`Blinds: ${blinds.small || 0}/${blinds.big || 0}`, 130, 28);

            const phase = (current.phase || '').replace(/_/g, ' ');
            ctx.fillStyle = '#aaaacc';
            ctx.font = 'bold 12px -apple-system, sans-serif';
            ctx.fillText(phase.toUpperCase(), 280, 28);

            ctx.fillStyle = COLORS.secondary;
            ctx.font = '13px -apple-system, sans-serif';
            if (context.hands_played != null) {
                ctx.fillText(`Played: ${context.hands_played}`, 410, 28);
            }

            const eliminated = (context.elimination_order || []).length;
            const total = (current.seat_order || []).length;
            if (total > 0) {
                ctx.fillText(`Players: ${total - eliminated}/${total}`, 520, 28);
            }

            if (context.biggest_pot) {
                ctx.fillText(`Max pot: ${context.biggest_pot}`, 650, 28);
            }
        }

        _drawToggle(ctx, W, H) {
            const x = W - 140, y = H - 40, w = 130, h = 28;
            ctx.fillStyle = this._showAllCards ? 'rgba(255, 215, 0, 0.2)' : 'rgba(42, 42, 74, 0.8)';
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, 5);
            ctx.fill();
            ctx.strokeStyle = this._showAllCards ? COLORS.gold : '#3a3a5a';
            ctx.lineWidth = 1;
            ctx.stroke();

            ctx.fillStyle = this._showAllCards ? COLORS.gold : COLORS.muted;
            ctx.font = '11px -apple-system, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(this._showAllCards ? '🔓 Show All Cards' : '🔒 God View', x + w / 2, y + 18);
        }

        _drawLastAction(ctx, lastMove, W, H) {
            const move = lastMove.move || {};
            const agent = lastMove.agent_id || '';
            let text = `${agent}: `;

            switch (move.action) {
                case 'fold': text += 'folded'; break;
                case 'check': text += 'checked'; break;
                case 'call': text += 'called'; break;
                case 'raise': text += `raised to ${move.amount}`; break;
                case 'all_in': text += 'ALL IN'; break;
                default: text += move.action || '?';
            }

            ctx.fillStyle = 'rgba(26, 26, 46, 0.85)';
            ctx.fillRect(0, H - 40, W - 150, 40);

            ctx.fillStyle = COLORS.text;
            ctx.font = '13px "SF Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(text, 16, H - 16);
        }

        applyMove(state, logEntry) {
            const post = logEntry.post_move_state;
            const ctx = logEntry.post_move_context;
            if (!post) return state;

            const game = { ...(state.game || {}) };
            game.current = post;
            if (ctx) game.context = ctx;
            return { ...state, game };
        }

        formatMoveSummary(logEntry) {
            const move = logEntry.envelope?.move;
            const agent = logEntry.agent_id || '';
            if (!move) {
                if (logEntry.result === 'timeout') return `${agent}: timed out (auto-fold)`;
                return '?';
            }
            switch (move.action) {
                case 'fold': return `${agent}: folded`;
                case 'check': return `${agent}: checked`;
                case 'call': return `${agent}: called`;
                case 'raise': return `${agent}: raised to ${move.amount}`;
                case 'all_in': return `${agent}: ALL IN`;
                default: return `${agent}: ${move.action || '?'}`;
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
    window.LxMRenderers['poker'] = PokerRenderer;
})();
