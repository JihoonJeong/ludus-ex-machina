/**
 * LxM Data Source — abstracts server vs static mode.
 *
 * Static mode: fetches pre-exported JSON from docs/data/
 * Server mode: fetches from localhost viewer server (existing behavior)
 */

const dataSource = {
    isStatic: false,
    basePath: '',
    // Hosted cross-machine matches (RFP A6) live only in Redis on the API
    // server; a `live_*` match id (or ?hosted=1) is fetched from here.
    hostedApi: 'https://lxm-api.onrender.com',
    // published replays (durable store) — GCS public bucket; the viewer falls
    // back here once a live match has expired from Redis (24h TTL).
    gcsReplays: 'https://storage.googleapis.com/lxm-replays/replays',
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
                const res = await fetch('/api/matches', { signal: AbortSignal.timeout(15000) });
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
        if (this._isHosted(matchId)) {
            const live = await this._fetch(`${this._hostedBase()}/api/matches/${matchId}/config`);
            if (live) return live;
            return (await this._durableReplay(matchId))?.config || null;  // GCS/Pages (TTL expired)
        }
        if (this.isStatic) {
            const replay = await this._getReplay(matchId);
            return replay?.config || null;
        }
        return this._fetch(`/api/match/${matchId}/config`);
    },

    async getMatchLog(matchId) {
        if (this._isHosted(matchId)) {
            const live = await this._fetch(`${this._hostedBase()}/api/matches/${matchId}/log`);
            if (live) return live;
            return (await this._durableReplay(matchId))?.log || null;  // GCS/Pages (TTL expired)
        }
        if (this.isStatic) {
            const replay = await this._getReplay(matchId);
            return replay?.log || null;
        }
        return this._fetch(`/api/match/${matchId}/log`);
    },

    async getMatchResult(matchId) {
        if (this._isHosted(matchId)) {
            const live = await this._fetch(`${this._hostedBase()}/api/matches/${matchId}/result`);
            if (live) return live;
            return (await this._durableReplay(matchId))?.result || null;  // GCS/Pages (TTL expired)
        }
        if (this.isStatic) {
            const replay = await this._getReplay(matchId);
            return replay?.result || null;
        }
        return this._fetch(`/api/match/${matchId}/result`);
    },

    async getMatchBundle(matchId) {
        if (this._isHosted(matchId)) {
            const base = this._hostedBase();
            const [config, log, result] = await Promise.all([
                this._fetch(`${base}/api/matches/${matchId}/config`),
                this._fetch(`${base}/api/matches/${matchId}/log`),
                this._fetch(`${base}/api/matches/${matchId}/result`),
            ]);
            if (config) return { config, log, result };   // live in the API
            return this._durableReplay(matchId);           // GCS/Pages (TTL expired)
        }
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

    // ── Reach sessions (D-062 Phase 2b) ──
    // Sessions live only in static mode for now; server support is a
    // future addition to viewer/server.py.

    async getSessions() {
        if (this.isStatic) {
            return (await this._fetch(`${this.basePath}/sessions.json`)) || [];
        }
        // Server mode: fall back to the static file.
        return (await this._fetch('/data/sessions.json')) || [];
    },

    async getSessionBundle(sessionId) {
        if (this.isStatic) {
            return this._fetch(`${this.basePath}/sessions/${sessionId}.json`);
        }
        return this._fetch(`/data/sessions/${sessionId}.json`);
    },

    // Internal helpers

    _isHosted(matchId) {
        const params = new URLSearchParams(window.location.search);
        if (params.get('hosted') === '1') return true;
        return typeof matchId === 'string' && matchId.startsWith('live_');
    },

    _hostedBase() {
        // ?api=http://localhost:8000 overrides for local testing.
        const params = new URLSearchParams(window.location.search);
        return params.get('api') || this.hostedApi;
    },

    async _durableReplay(matchId) {
        // A published match's replay bundle: GCS public bucket (long-term store)
        // then the Pages static file. Cached.
        const key = 'durable:' + matchId;
        if (this._replayCache[key] !== undefined) return this._replayCache[key];
        let bundle = await this._fetch(`${this.gcsReplays}/${matchId}.json`);
        if (!bundle) bundle = await this._getReplay(matchId);
        this._replayCache[key] = bundle || null;
        return bundle;
    },

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
