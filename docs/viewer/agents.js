/**
 * LxM Agent Management UI.
 */

const ADAPTER_MODELS = {
    claude: [
        { value: 'opus', label: 'Opus 4.6 (flagship)' },
        { value: 'sonnet', label: 'Sonnet 4.6 (mid-tier)' },
        { value: 'haiku', label: 'Haiku 4.5 (fast)' },
    ],
    gemini: [
        { value: 'gemini-3.1-pro-preview', label: '3.1 Pro (flagship)' },
        { value: 'gemini-3-flash-preview', label: '3 Flash (mid-tier)' },
        { value: 'gemini-2.5-flash', label: '2.5 Flash (previous)' },
    ],
    codex: [
        { value: 'gpt-5.4', label: 'GPT-5.4 (flagship)' },
        { value: 'gpt-5.3-codex', label: 'GPT-5.3 Codex' },
        { value: 'gpt-5.1-codex-mini', label: 'GPT-5.1 Codex Mini (fast)' },
    ],
    ollama: [
        { value: 'gemma3:4b', label: 'Gemma3 4B (local)' },
        { value: 'exaone3.5:7.8b', label: 'Exaone 3.5 7.8B (local)' },
        { value: 'llama3.1:8b', label: 'Llama 3.1 8B' },
    ],
};

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
            const res = await fetch(`${LXM_API}/api/agents`, {
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

    onAdapterChange() {
        const adapter = document.getElementById('agent-adapter-input').value;
        const select = document.getElementById('agent-model-input');
        const models = ADAPTER_MODELS[adapter] || [];
        select.innerHTML = models.map(m =>
            `<option value="${m.value}">${m.label}</option>`
        ).join('');
    },

    showForm() {
        document.getElementById('agent-form').style.display = '';
        this.onAdapterChange(); // populate model dropdown
    },

    hideForm() {
        document.getElementById('agent-form').style.display = 'none';
    },

    async register() {
        const agentId = document.getElementById('agent-id-input').value.trim();
        const displayName = document.getElementById('agent-name-input').value.trim();
        const adapter = document.getElementById('agent-adapter-input').value;
        const model = document.getElementById('agent-model-input').value.trim();

        const games = ['chess', 'poker', 'avalon', 'codenames', 'trustgame', 'tictactoe'];

        if (!agentId || !displayName || !model) {
            alert('Please fill in all fields');
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
