/**
 * LxM Agent Management UI.
 */

const agentUI = {
    async init() {
        if (!lxmAuth.isLoggedIn()) {
            document.getElementById('agents-section').style.display = 'none';
            return;
        }
        document.getElementById('agents-section').style.display = '';
        await this.loadAgents();
    },

    async loadAgents() {
        const list = document.getElementById('agents-list');
        try {
            const res = await fetch(`${LXM_API}/api/agents?user_id=${lxmAuth.user}`, {
                headers: lxmAuth.getHeaders(),
            });
            if (!res.ok) {
                list.innerHTML = '<div class="empty-state">Could not load agents</div>';
                return;
            }
            const agents = await res.json();
            if (agents.length === 0) {
                list.innerHTML = '<div class="empty-state">No agents registered. Click "+ Register Agent" to create one.</div>';
                return;
            }
            list.innerHTML = agents.map(a => this._renderCard(a)).join('');
        } catch (e) {
            list.innerHTML = '<div class="empty-state">API server not available</div>';
        }
    },

    _renderCard(agent) {
        const games = (agent.games || []).map(g =>
            `<span class="agent-game-tag">${g}</span>`
        ).join('');

        const eloEntries = Object.entries(agent.elo || {});
        const eloStr = eloEntries.length > 0
            ? eloEntries.map(([g, e]) => `${g}: ${Math.round(e)}`).join(' · ')
            : 'No games played';

        const stats = agent.stats || {};
        const totalWins = Object.values(stats).reduce((s, g) => s + (g.wins || 0), 0);
        const totalLosses = Object.values(stats).reduce((s, g) => s + (g.losses || 0), 0);

        return `
            <div class="agent-card">
                <div class="agent-card-header">
                    <span class="agent-card-name">${agent.display_name}</span>
                    <button class="agent-delete-btn" onclick="agentUI.deleteAgent('${agent.agent_id}')">&times;</button>
                </div>
                <div class="agent-card-meta">
                    <span class="agent-adapter">${agent.adapter}</span>
                    <span class="agent-model">${agent.model}</span>
                    ${agent.hard_shell_name ? `<span class="agent-shell">${agent.hard_shell_name}</span>` : ''}
                </div>
                <div class="agent-card-games">${games}</div>
                <div class="agent-card-elo">${eloStr}</div>
                <div class="agent-card-record">${totalWins}W ${totalLosses}L</div>
            </div>
        `;
    },

    showForm() {
        document.getElementById('agent-form').style.display = '';
    },

    hideForm() {
        document.getElementById('agent-form').style.display = 'none';
    },

    async register() {
        const agentId = document.getElementById('agent-id-input').value.trim();
        const displayName = document.getElementById('agent-name-input').value.trim();
        const adapter = document.getElementById('agent-adapter-input').value;
        const model = document.getElementById('agent-model-input').value.trim();

        const checkboxes = document.querySelectorAll('.game-checkboxes input:checked');
        const games = Array.from(checkboxes).map(cb => cb.value);

        if (!agentId || !displayName || !model) {
            alert('Please fill in all fields');
            return;
        }
        if (games.length === 0) {
            alert('Select at least one game');
            return;
        }

        try {
            const res = await fetch(`${LXM_API}/api/agents`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...lxmAuth.getHeaders(),
                },
                body: JSON.stringify({
                    agent_id: agentId,
                    display_name: displayName,
                    adapter,
                    model,
                    games,
                }),
            });

            if (res.ok) {
                this.hideForm();
                // Clear form
                document.getElementById('agent-id-input').value = '';
                document.getElementById('agent-name-input').value = '';
                document.getElementById('agent-model-input').value = '';
                document.querySelectorAll('.game-checkboxes input').forEach(cb => cb.checked = false);
                await this.loadAgents();
            } else {
                const err = await res.json();
                alert(err.detail || 'Failed to register agent');
            }
        } catch (e) {
            alert('API server not available');
        }
    },

    async deleteAgent(agentId) {
        if (!confirm(`Delete agent "${agentId}"?`)) return;

        try {
            const res = await fetch(`${LXM_API}/api/agents/${agentId}`, {
                method: 'DELETE',
                headers: lxmAuth.getHeaders(),
            });
            if (res.ok) {
                await this.loadAgents();
            } else {
                alert('Failed to delete agent');
            }
        } catch (e) {
            alert('API server not available');
        }
    },
};

// Initialize after auth
const _origAuthUpdate = lxmAuth.updateUI.bind(lxmAuth);
lxmAuth.updateUI = function () {
    _origAuthUpdate();
    agentUI.init();
};
