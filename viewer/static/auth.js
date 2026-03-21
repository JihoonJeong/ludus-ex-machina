/**
 * LxM Auth — GitHub OAuth + API server integration.
 */

const LXM_API = 'http://localhost:8000';

const lxmAuth = {
    token: null,
    user: null,

    init() {
        // Check URL for auth callback params
        const hash = window.location.hash;
        if (hash.includes('/auth?')) {
            const params = new URLSearchParams(hash.split('?')[1]);
            const token = params.get('token');
            const user = params.get('user');
            const name = params.get('name');
            if (token && user) {
                localStorage.setItem('lxm_token', token);
                localStorage.setItem('lxm_user', user);
                localStorage.setItem('lxm_name', name || user);
                // Clean URL
                window.location.hash = '#/';
            }
        }

        // Load from localStorage
        this.token = localStorage.getItem('lxm_token');
        this.user = localStorage.getItem('lxm_user');
        this.updateUI();
    },

    login() {
        window.location.href = `${LXM_API}/api/auth/login`;
    },

    logout() {
        localStorage.removeItem('lxm_token');
        localStorage.removeItem('lxm_user');
        localStorage.removeItem('lxm_name');
        this.token = null;
        this.user = null;
        this.updateUI();
    },

    updateUI() {
        const loginBtn = document.getElementById('btn-login');
        const profile = document.getElementById('user-profile');

        if (this.token && this.user) {
            loginBtn.style.display = 'none';
            profile.style.display = 'flex';
            document.getElementById('user-name').textContent = localStorage.getItem('lxm_name') || this.user;

            // Try to load avatar from API
            this.fetchProfile();
        } else {
            loginBtn.style.display = '';
            profile.style.display = 'none';
        }
    },

    async fetchProfile() {
        try {
            const res = await fetch(`${LXM_API}/api/auth/me`, {
                headers: { 'Authorization': `Bearer ${this.token}` },
            });
            if (res.ok) {
                const data = await res.json();
                if (data.avatar_url) {
                    document.getElementById('user-avatar').src = data.avatar_url;
                }
                if (data.display_name) {
                    document.getElementById('user-name').textContent = data.display_name;
                }
            }
        } catch (e) {
            // API server not available — that's OK for local dev
        }
    },

    isLoggedIn() {
        return !!(this.token && this.user);
    },

    getHeaders() {
        if (!this.token) return {};
        return { 'Authorization': `Bearer ${this.token}` };
    },
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => lxmAuth.init());
