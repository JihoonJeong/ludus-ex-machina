/**
 * Reach Session renderer for LxM Viewer — D-062 Phase 2b skeleton.
 *
 * Unlike game renderers (which step through log entries), reach sessions
 * are rendered as a full transcript: session meta + prompt/response turn
 * timeline + close markers. The renderer consumes a session bundle (the
 * JSON produced by `scripts/export_static.py::bundle_session`).
 *
 * Bundle shape:
 *   { session_id, meta, turn_state, turns: [{turn, prompt, responses}], closes }
 *
 * This is a skeleton — enough to validate the data flow end-to-end.
 * Styling and interaction (collapsible turns, consent badges, voice
 * drift indicators, etc.) are joint-session follow-ups.
 */

(function () {
    const COLORS = {
        bg: '#0f1115',
        panel: '#1a1a2e',
        border: '#2a2a4a',
        text: '#e0e0e0',
        muted: '#888888',
        accent: '#d4c27a',
        prompt: '#60a5fa',     // field-host prompts — blue
        response: '#4ade80',   // creature responses — green
        close: '#f87171',      // close markers — red
    };

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // Minimal markdown: paragraphs, fenced code, simple emphasis.
    // Full markdown is deferred — this is enough for the skeleton.
    function renderBody(body) {
        if (!body) return '';
        const out = [];
        const paragraphs = body.trim().split(/\n\n+/);
        for (const p of paragraphs) {
            const trimmed = p.trim();
            if (!trimmed) continue;
            if (trimmed.startsWith('```') && trimmed.endsWith('```')) {
                const inner = trimmed.slice(3, -3).trim();
                out.push(`<pre class="reach-code">${escapeHtml(inner)}</pre>`);
            } else {
                out.push(`<p>${escapeHtml(trimmed).replace(/\n/g, '<br>')}</p>`);
            }
        }
        return out.join('');
    }

    function renderMeta(meta) {
        const parts = meta.participants || [];
        const participantsHtml = parts.map(p => {
            const alias = p.machine_alias ? `@${escapeHtml(p.machine_alias)}` : '';
            const role = p.role ? ` · ${escapeHtml(p.role)}` : '';
            return `<span class="reach-participant">${escapeHtml(p.creature || '?')}<span class="reach-muted">${alias}${role}</span></span>`;
        }).join('<span class="reach-sep">↔</span>');
        const status = meta.status || 'unknown';
        const field = escapeHtml(meta.field || '(no field)');
        const created = escapeHtml(meta.created_at || '');
        return `
            <div class="reach-meta">
                <div class="reach-meta-row">
                    <span class="reach-label">Field:</span>
                    <span>${field}</span>
                    <span class="reach-status reach-status-${escapeHtml(status)}">${escapeHtml(status)}</span>
                </div>
                <div class="reach-meta-row">${participantsHtml}</div>
                ${created ? `<div class="reach-meta-row reach-muted">Opened ${created}</div>` : ''}
            </div>`;
    }

    function renderMetaFooter(meta) {
        // meta.yaml free-form annotations (schema §2.1): render a
        // footer when `note` or `smoke` fields are present.
        if (!meta || (meta.note == null && meta.smoke == null)) return '';
        const noteHtml = meta.note ? `<div class="reach-note-body">${renderBody(String(meta.note))}</div>` : '';
        const smokeBadge = meta.smoke ? `<span class="reach-smoke-badge">smoke</span>` : '';
        return `
            <div class="reach-footer">
                <div class="reach-footer-header">Session note ${smokeBadge}</div>
                ${noteHtml}
            </div>`;
    }

    function renderTurn(turn) {
        const n = turn.turn;
        const p = turn.prompt;
        const responses = turn.responses || [];

        const promptBlock = p
            ? `<div class="reach-prompt">
                 <div class="reach-prompt-header">Prompt · turn ${n}</div>
                 <div class="reach-body">${renderBody(p.body)}</div>
               </div>`
            : '';

        const responseBlocks = responses.map(r => {
            const fm = r.frontmatter || {};
            const creature = escapeHtml(fm.creature || '?');
            const alias = fm.machine_alias ? `@${escapeHtml(fm.machine_alias)}` : '';
            const ts = fm.timestamp ? `<span class="reach-muted reach-ts">${escapeHtml(fm.timestamp)}</span>` : '';
            return `<div class="reach-response">
                      <div class="reach-response-header">${creature}<span class="reach-muted">${alias}</span>${ts}</div>
                      <div class="reach-body">${renderBody(r.body)}</div>
                    </div>`;
        }).join('');

        return `<div class="reach-turn" data-turn="${n}">
                  ${promptBlock}
                  ${responseBlocks}
                </div>`;
    }

    function renderCloses(closes) {
        if (!closes || closes.length === 0) return '';
        const items = closes.map(c => {
            const fm = c.frontmatter || {};
            const reason = escapeHtml(fm.reason || 'close');
            const by = escapeHtml(fm.by_creature || '?');
            const ts = escapeHtml(fm.timestamp || '');
            return `<div class="reach-close">
                      <div class="reach-close-header">close · ${reason} · by ${by}<span class="reach-muted reach-ts">${ts}</span></div>
                      ${c.body ? `<div class="reach-body">${renderBody(c.body)}</div>` : ''}
                    </div>`;
        }).join('');
        return `<div class="reach-closes">${items}</div>`;
    }

    // Styles injected once per page.
    let stylesInjected = false;
    function injectStyles() {
        if (stylesInjected) return;
        stylesInjected = true;
        const css = `
            .reach-container { color: ${COLORS.text}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 16px; background: ${COLORS.bg}; border-radius: 6px; }
            .reach-meta { padding: 12px; background: ${COLORS.panel}; border: 1px solid ${COLORS.border}; border-radius: 6px; margin-bottom: 16px; }
            .reach-meta-row { margin: 4px 0; }
            .reach-label { color: ${COLORS.accent}; margin-right: 8px; }
            .reach-participant { padding: 3px 8px; background: rgba(212, 194, 122, 0.12); border-radius: 4px; margin-right: 4px; }
            .reach-sep { margin: 0 8px; color: ${COLORS.muted}; }
            .reach-muted { color: ${COLORS.muted}; font-size: 0.9em; margin-left: 6px; }
            .reach-status { padding: 2px 8px; border-radius: 10px; font-size: 0.85em; margin-left: 10px; }
            .reach-status-active { background: rgba(74, 222, 128, 0.2); color: ${COLORS.response}; }
            .reach-status-closed { background: rgba(136, 136, 136, 0.2); }
            .reach-status-interrupted { background: rgba(248, 113, 113, 0.2); color: ${COLORS.close}; }
            .reach-turn { margin-bottom: 14px; border-left: 3px solid ${COLORS.border}; padding-left: 12px; }
            .reach-prompt { background: rgba(96, 165, 250, 0.08); border: 1px solid rgba(96, 165, 250, 0.3); border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; }
            .reach-prompt-header { color: ${COLORS.prompt}; font-size: 0.85em; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
            .reach-response { background: rgba(74, 222, 128, 0.08); border: 1px solid rgba(74, 222, 128, 0.3); border-radius: 6px; padding: 10px 12px; margin-bottom: 6px; }
            .reach-response-header { color: ${COLORS.response}; font-size: 0.9em; margin-bottom: 6px; }
            .reach-body { line-height: 1.5; }
            .reach-body p { margin: 6px 0; }
            .reach-code { background: #0b0d12; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 0.9em; }
            .reach-closes { margin-top: 20px; }
            .reach-close { background: rgba(248, 113, 113, 0.08); border: 1px solid rgba(248, 113, 113, 0.3); border-radius: 6px; padding: 10px 12px; margin-bottom: 6px; }
            .reach-close-header { color: ${COLORS.close}; font-size: 0.9em; margin-bottom: 6px; }
            .reach-ts { font-size: 0.8em; }
            .reach-footer { margin-top: 24px; padding: 12px; background: ${COLORS.panel}; border: 1px dashed ${COLORS.border}; border-radius: 6px; }
            .reach-footer-header { color: ${COLORS.accent}; font-size: 0.85em; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
            .reach-note-body { color: ${COLORS.muted}; font-size: 0.95em; }
            .reach-smoke-badge { background: rgba(248, 113, 113, 0.2); color: ${COLORS.close}; padding: 2px 8px; border-radius: 10px; font-size: 0.75em; margin-left: 8px; text-transform: none; }
        `;
        const style = document.createElement('style');
        style.textContent = css;
        document.head.appendChild(style);
    }

    class ReachRenderer {
        constructor(container) {
            injectStyles();
            this.container = container;
            this.root = document.createElement('div');
            this.root.className = 'reach-container';
            container.appendChild(this.root);
        }

        /** Render an entire session bundle (not a per-move diff). */
        renderBundle(bundle) {
            if (!bundle || !bundle.meta) {
                this.root.innerHTML = '<div class="reach-muted">No session data.</div>';
                return;
            }
            const metaHtml = renderMeta(bundle.meta);
            const turnsHtml = (bundle.turns || []).map(renderTurn).join('');
            const closesHtml = renderCloses(bundle.closes);
            const footerHtml = renderMetaFooter(bundle.meta);
            this.root.innerHTML = metaHtml + turnsHtml + closesHtml + footerHtml;
        }
    }

    window.LxMRenderers = window.LxMRenderers || {};
    window.LxMRenderers['reach'] = ReachRenderer;
})();
