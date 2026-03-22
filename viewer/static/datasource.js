/**
 * LxM Data Source — abstracts server vs static mode.
 *
 * Static mode: fetches pre-exported JSON from docs/data/
 * Server mode: fetches from localhost viewer server (existing behavior)
 */

const dataSource = {
    isStatic: false,
    basePath: '',
    _replayCache: {},

    /**
     * Auto-detect mode.
     * Static if: hosted on github.io, or ?static=1 param, or no /api/matches response.
     */
    async init() {
        const params = new URLSearchParams(window.location.search);
        const hostname = window.location.hostname;

        if (params.get('static') === '1' || hostname.includes('github.io')) {
            this.isStatic = true;
            // Determine base path for data files
            // On GitHub Pages: /ludus-ex-machina/viewer/ → data is at /ludus-ex-machina/data/
            // Locally: /viewer/ → data is at /data/
            const pathParts = window.location.pathname.split('/');
            // Find 'viewer' in path and go up one level
            const viewerIdx = pathParts.indexOf('viewer');
            if (viewerIdx > 0) {
                this.basePath = pathParts.slice(0, viewerIdx).join('/') + '/data';
            } else {
                this.basePath = '/data';
            }
        } else {
            // Try server mode — fall back to static if server unreachable
            try {
                const res = await fetch('/api/matches', { signal: AbortSignal.timeout(2000) });
                if (!res.ok) throw new Error();
                this.isStatic = false;
            } catch {
                this.isStatic = true;
                this.basePath = '/data';
            }
        }

        console.log(`[LxM] Data source: ${this.isStatic ? 'static' : 'server'} ${this.isStatic ? '(' + this.basePath + ')' : ''}`);
    },

    async getMatches() {
        if (this.isStatic) {
            return this._fetch(`${this.basePath}/matches.json`);
        }
        return this._fetch('/api/matches');
    },

    async getLeaderboard() {
        if (this.isStatic) {
            return this._fetch(`${this.basePath}/leaderboard.json`);
        }
        return this._fetch('/api/leaderboard');
    },

    async getCrossCompany() {
        if (this.isStatic) {
            return this._fetch(`${this.basePath}/cross_company.json`);
        }
        return null; // Not available in server mode
    },

    async getMatchConfig(matchId) {
        if (this.isStatic) {
            const replay = await this._getReplay(matchId);
            return replay?.config || null;
        }
        return this._fetch(`/api/match/${matchId}/config`);
    },

    async getMatchLog(matchId) {
        if (this.isStatic) {
            const replay = await this._getReplay(matchId);
            return replay?.log || null;
        }
        return this._fetch(`/api/match/${matchId}/log`);
    },

    async getMatchResult(matchId) {
        if (this.isStatic) {
            const replay = await this._getReplay(matchId);
            return replay?.result || null;
        }
        return this._fetch(`/api/match/${matchId}/result`);
    },

    async getMatchBundle(matchId) {
        if (this.isStatic) {
            return this._getReplay(matchId);
        }
        const [config, log, result] = await Promise.all([
            this._fetch(`/api/match/${matchId}/config`),
            this._fetch(`/api/match/${matchId}/log`),
            this._fetch(`/api/match/${matchId}/result`),
        ]);
        return { config, log, result };
    },

    // Internal helpers

    async _getReplay(matchId) {
        if (this._replayCache[matchId]) {
            return this._replayCache[matchId];
        }
        const data = await this._fetch(`${this.basePath}/replays/${matchId}.json`);
        if (data) {
            this._replayCache[matchId] = data;
        }
        return data;
    },

    async _fetch(url) {
        try {
            const res = await fetch(url);
            if (!res.ok) return null;
            return res.json();
        } catch {
            return null;
        }
    },
};
