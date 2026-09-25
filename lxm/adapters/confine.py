"""Per-call READ confinement for measurement fields (macOS `sandbox-exec`).

History — each version was broken by a brain that looked where we had not:
  v1 (none, 09-24): 'hands none' denied writes only. From an empty tempdir
     grok grepped the home directory and read another village's ledgers, the
     hub envelope holding the case originals, and LxM's scorer (from-lxm/083).
  v2 (deny-list, 58864f0): denied ~/Projects, document trees, other CLIs'
     stores. The canary's REACH bait sat inside that list, so it passed. In
     the run, grok read everything the list did not name: other trial
     sessions in its own store, other Claude Code scratchpads in /tmp (a
     village caretaker's working files among them), a repo checkout outside
     ~/Projects, ~/.ludex, sibling temp dirs; codex listed home and a vault
     (from-lxm/090).
  v3 (this, allow-list): deny reading $HOME, /tmp and the per-user temp dir
     WHOLE, then allow back only what the lineage's CLI needs to run (its
     binary tree, config and auth) and this call's own places (workspace,
     its session record dir, a private TMPDIR made per call). A place nobody
     thought of is closed by default. The REACH probe puts bait where v2
     leaked, not where v3 is known to hold.

`file-read-data` is denied, not `file-read*`: contents and listings are
blocked, `stat` is not. A brain can learn that a path exists; it cannot read
it. Writes stay the adapter's job (its hands flags), except for lineages whose
own write-less mode is a sandbox that cannot nest inside ours (codex): there
the profile denies writes too — under $HOME but the CLI store, the
workspace, and /tmp.

Games do not use this. It is installed only by a measurement script, and the
canary's REACH probe verifies it before any trial runs (fail-closed).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
import urllib.parse

HOME = os.path.expanduser("~")
TMP_ROOT = os.path.realpath(tempfile.gettempdir())          # /private/var/folders/xx/yy/T

# What each lineage's CLI needs to READ under $HOME to run: its binary tree,
# config and auth. Everything else under $HOME stays closed. claude and cursor
# keep their tokens in the login keychain (encrypted files; the CLI asks the
# keychain for its own item).
ALLOW_HOME = {
    "claude": (".nvm", ".claude", ".claude.json", "Library/Keychains"),
    "codex": (".nvm", ".codex"),
    "grok": (".grok",),
    "cursor": (".local/bin", ".local/share/cursor-agent", ".cursor", ".config/cursor", "Library/Keychains"),
    "gemini": (".local/bin", ".gemini"),
}
# Inside what is allowed back: other sessions' records, closed again.
DENY_WITHIN = {
    "claude": (".claude/projects", ".claude/history.jsonl", ".claude/file-history", ".claude/todos",
               ".claude/paste-cache", ".claude/shell-snapshots", ".claude/debug", ".claude/backups",
               ".claude/sessions", ".claude/jobs"),
    "codex": (".codex/sessions", ".codex/archived_sessions", ".codex/history.jsonl", ".codex/attachments"),
    "grok": (".grok/sessions", ".grok/logs", ".grok/memtrace"),
    "cursor": (".cursor/chats", ".cursor/projects", ".cursor/ai-tracking"),
    "gemini": (".gemini/antigravity-cli/brain", ".gemini/antigravity-cli/knowledge",
               ".gemini/antigravity-cli/annotations", ".gemini/antigravity-cli/implicit",
               ".gemini/antigravity-cli/history.jsonl", ".gemini/antigravity-cli/conversation_summaries.db"),
}
# What stays readable inside the own store, recorded with every run.
# Files at the top of the own store the CLI must read to start a session.
# grok cannot create a session without its search index; the index holds
# short records of every grok session on this machine — content xAI already
# saw in those sessions — so it is a recorded residual, not an open door to a
# new vendor. The session DIRS themselves stay closed.
ALLOW_TOP = {
    "grok": (".grok/sessions/session_search.sqlite", ".grok/sessions/session_search.sqlite-wal",
             ".grok/sessions/session_search.sqlite-shm", ".grok/sessions/sandbox-events.jsonl"),
}
OWN_STORE_RESIDUAL = {
    "grok": "~/.grok/sessions/session_search.sqlite (search index of all grok sessions on this "
            "machine; needed to start a session)",
    "gemini": "~/.gemini/antigravity-cli/conversations/*.db (keyed by conversation id; "
              "the current one must stay readable, so all do)",
}
# Lineages whose write-less mode is a sandbox of their own (cannot nest).
WRITE_GUARD = {"codex"}


def _q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _both(path: str) -> set[str]:
    return {os.path.abspath(path), os.path.realpath(path)}


def own_session_dirs(lineage: str, workspace: str, home: str = HOME) -> list[str]:
    """This call's own session record dirs inside the CLI store (allowed back)."""
    real = os.path.realpath(workspace)
    if lineage == "claude":
        return [os.path.join(home, ".claude/projects", re.sub(r"[/_.]", "-", p))
                for p in sorted(_both(workspace))]
    if lineage == "grok":
        return [os.path.join(home, ".grok/sessions", urllib.parse.quote(p, safe=""))
                for p in sorted(_both(workspace))]
    if lineage == "cursor":
        enc = {p.lstrip("/").replace("/", "-").replace("_", "-") for p in _both(workspace)}
        return ([os.path.join(home, ".cursor/chats", hashlib.md5(real.encode()).hexdigest())]
                + [os.path.join(home, ".cursor/projects", e) for e in sorted(enc)])
    return []


def claude_scratch_dirs(workspace: str) -> list[str]:
    """Claude Code keeps a per-session scratchpad under /tmp/claude-<uid>/<cwd>."""
    uid = os.getuid()
    return [f"/private/tmp/claude-{uid}/{re.sub(r'[/_.]', '-', p)}" for p in sorted(_both(workspace))]


def profile(lineage: str, home: str = HOME, workspace: str | None = None,
            private_tmp: str | None = None) -> str:
    def sub(paths):
        return " ".join(f'(subpath "{_q(p)}")' for p in paths)
    out = ["(version 1)", "(allow default)",
           f'(deny file-read-data {sub([home, "/private/tmp", "/tmp"])} '
           f'(regex #"^{re.escape(TMP_ROOT)}/"))']
    back = [os.path.join(home, p) for p in ALLOW_HOME.get(lineage, ())]
    if workspace:
        back += sorted(_both(workspace))
    if private_tmp:
        back += sorted(_both(private_tmp))
    if back:
        out.append(f"(allow file-read-data {sub(back)})")
    again = [os.path.join(home, p) for p in DENY_WITHIN.get(lineage, ())]
    if again:
        out.append(f"(deny file-read-data {sub(again)})")
    if workspace:
        own = own_session_dirs(lineage, workspace, home)
        if lineage == "claude":
            own += claude_scratch_dirs(workspace)
        if own:
            out.append(f"(allow file-read-data {sub(own)})")
    top = [os.path.join(home, p) for p in ALLOW_TOP.get(lineage, ())]
    if top:
        store = os.path.join(home, ".grok/sessions")
        out.append("(allow file-read-data " + " ".join(f'(literal "{_q(p)}")' for p in top + [store]) + ")")
    if lineage == "claude":
        # the CLI opens its scratch root to make this session's dir: the root's
        # listing (other sessions' dir NAMES) is readable, their contents are not
        root = f"/private/tmp/claude-{os.getuid()}"
        out.append(f'(allow file-read-data (literal "{root}") (literal "/tmp/claude-{os.getuid()}"))')
    if lineage in WRITE_GUARD:
        mine = [os.path.join(home, n) for n in ALLOW_HOME[lineage] if n.startswith(".codex")]
        out.append(f'(deny file-write* {sub([home, "/private/tmp", "/tmp"])})')
        out.append(f"(allow file-write* {sub(mine + (sorted(_both(private_tmp)) if private_tmp else []))})")
        if workspace:
            out.append(f"(deny file-write* {sub(sorted(_both(workspace)))})")
    return "\n".join(out) + "\n"


def profile_sha(lineage: str, home: str = HOME) -> str:
    return hashlib.sha256(profile(lineage, home).encode()).hexdigest()


def available() -> bool:
    return shutil.which("sandbox-exec") is not None


def install(adapter, lineage: str, home: str = HOME) -> str:
    """Route every CLI call of this adapter through sandbox-exec with the
    lineage's allow-list profile. Each call gets a private TMPDIR (the shared
    temp dir is closed). Returns the base profile sha (record it)."""
    if not available():
        raise RuntimeError("sandbox-exec not found — read confinement unavailable on this host")
    base = profile(lineage, home)
    inner = adapter._run_cli
    if lineage in WRITE_GUARD:
        adapter._outer_sandbox = True      # the adapter drops its inner sandbox

    def confined(cmd, *args, **kwargs):
        workspace = kwargs.get("cwd") or (cmd[cmd.index("-C") + 1] if "-C" in cmd else None)
        private_tmp = tempfile.mkdtemp(prefix="lxm_tmp_")
        env = dict(kwargs.get("env") or os.environ)
        env["TMPDIR"] = private_tmp + "/"
        kwargs["env"] = env
        # An adapter that passes no cwd (codex sets its root with -C) would
        # start inside the caller's repo, which is closed: start in the
        # private temp dir instead.
        if kwargs.get("cwd") is None:
            kwargs["cwd"] = private_tmp
        prof = profile(lineage, home, workspace, private_tmp)
        try:
            return inner(["sandbox-exec", "-p", prof, *cmd], *args, **kwargs)
        finally:
            shutil.rmtree(private_tmp, ignore_errors=True)

    adapter._run_cli = confined
    adapter._confinement = {
        "mechanism": "sandbox-exec allow-list v3 (file-read-data: $HOME, /tmp, per-user temp closed; "
                     "CLI needs + this call's workspace/session/private TMPDIR reopened)"
                     + ("; outer write guard incl. /tmp (inner sandbox cannot nest)"
                        if lineage in WRITE_GUARD else ""),
        "profile_sha256": hashlib.sha256(base.encode()).hexdigest(),
        "version": 3,
        "own_store_residual": OWN_STORE_RESIDUAL.get(lineage)}
    return adapter._confinement["profile_sha256"]
