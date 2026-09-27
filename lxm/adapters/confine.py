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
  v3.4 (09-27, Organum 107 §7): the read wall held — no lineage could list
     ~/.organum or open its keys — but writes were still the adapters' job
     (their hands flags) for every lineage but codex and seats with hands. A
     handless claude/grok/cursor/agy seat could therefore WRITE anywhere
     under $HOME: overwrite or delete another lab's keys and tokens without
     reading them. Now every lineage runs under the write guard.

`file-read-data` is denied, not `file-read*`: contents and listings are
blocked, `stat` is not. A brain can learn that a path exists; it cannot read
it. Writes are denied under $HOME, /tmp and the per-user temp dir for every
lineage, except the CLI's own store, ~/Library (the keychain), this call's
private TMPDIR, claude's own session scratch dir, and a seat's desk when it
has hands. The workspace of a seat without hands stays read-only.

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
    "gemini": (".local/bin", ".gemini", "Library/Keychains"),
}
# Read by every CLI process that touches the login keychain — and a closed
# keychain is not a quiet failure. On 09-27 agy (gemini) ran under v3.1 with
# ~/Library/Keychains and the keychain search-list preferences closed: a token
# refresh ran `security add`, got -25294 (no such keychain), and macOS asked the
# founder to RESET THE DEFAULT KEYCHAIN (Naru saw the dialog and warned us;
# same fix as Naru's 4c10777e). Search succeeds and only add/update fails, so
# the canary cannot catch it. These files are opened for every lineage.
KEYCHAIN_READ_LITERALS = (".CFUserTextEncoding", "Library/Preferences/com.apple.security.plist",
                          "Library/Preferences/.GlobalPreferences.plist")
# ...and under a write guard, the keychain folder and preferences stay writable
# (a refreshed token is written back): Naru opens all of ~/Library for writes.
WRITE_LIBRARY = ("Library",)
# Inside what is allowed back: other sessions' records, closed again.
DENY_WITHIN = {
    "claude": (".claude/projects", ".claude/history.jsonl", ".claude/file-history", ".claude/todos",
               ".claude/paste-cache", ".claude/shell-snapshots", ".claude/debug", ".claude/backups",
               ".claude/sessions", ".claude/jobs"),
    # codex keeps other threads' items in its sqlite databases (state, thread
    # history, memories, ...) and has a shell to read them: closed too (every
    # *.sqlite* found at profile time, see DENY_WITHIN_GLOBS). It then cannot
    # record its own rollout; the runner keeps codex's --json events instead.
    "codex": (".codex/sessions", ".codex/archived_sessions", ".codex/history.jsonl", ".codex/attachments",
              ".codex/memories", ".codex/dictation-history", ".codex/generated_images", ".codex/log",
              ".codex/ambient-suggestions", ".codex/browser", ".codex/computer-use", ".codex/sqlite"),
    "grok": (".grok/sessions", ".grok/logs", ".grok/memtrace"),
    "cursor": (".cursor/chats", ".cursor/projects", ".cursor/ai-tracking"),
    "gemini": (".gemini/antigravity-cli/brain", ".gemini/antigravity-cli/knowledge",
               ".gemini/antigravity-cli/annotations", ".gemini/antigravity-cli/implicit",
               ".gemini/antigravity-cli/history.jsonl", ".gemini/antigravity-cli/conversation_summaries.db"),
}
DENY_WITHIN_GLOBS = {"codex": (".codex/*.sqlite*",)}
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
# Lineages whose write-less mode is a sandbox of their own that cannot nest
# inside ours: the adapter drops its inner sandbox and ours guards alone.
# (Until v3.4 this was also the only lineage with a write guard.)
WRITE_GUARD = {"codex"}
# Where a lineage's CLI must be able to WRITE its own state under the write
# guard (on for every lineage since v3.4).
WRITE_STORE = {"codex": (".codex",), "gemini": (".gemini",), "grok": (".grok",),
               "claude": (".claude", ".claude.json"), "cursor": (".cursor", ".config/cursor")}


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
            private_tmp: str | None = None, write_root: str | None = None,
            write_guard: bool | None = None) -> str:
    """workspace: what the call may READ (a task's whole repository mirror).
    write_root: where a seat with hands may WRITE (its desk); None = nowhere
    in the workspace. write_guard: deny writes outside the CLI store, ~/Library,
    the private TMPDIR, claude's own session scratch and write_root — on by
    default for every lineage (v3.4); False only for tests that need the
    read wall alone."""
    if write_guard is None:
        write_guard = True
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
    out.append("(allow file-read-data "
               + " ".join(f'(literal "{_q(os.path.join(home, p))}")' for p in KEYCHAIN_READ_LITERALS) + ")")
    again = [os.path.join(home, p) for p in DENY_WITHIN.get(lineage, ())]
    for pattern in DENY_WITHIN_GLOBS.get(lineage, ()):
        import glob as _glob
        again += sorted(_glob.glob(os.path.join(home, pattern)))
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
    if write_guard:
        mine = [os.path.join(home, n) for n in WRITE_STORE.get(lineage, ()) + WRITE_LIBRARY]
        out.append(f'(deny file-write* {sub([home, "/private/tmp", "/tmp"])} '
                   f'(regex #"^{re.escape(TMP_ROOT)}/"))')
        opened = mine + (sorted(_both(private_tmp)) if private_tmp else [])
        if lineage == "claude" and workspace:
            opened += claude_scratch_dirs(workspace)     # its own /tmp/claude-<uid>/<cwd> only
        if write_root:
            opened += sorted(_both(write_root))
        if opened:
            out.append(f"(allow file-write* {sub(opened)})")
        if workspace and not write_root:
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
        cwd = kwargs.get("cwd") or (cmd[cmd.index("-C") + 1] if "-C" in cmd else None)
        # A task whose seat works in one folder of a repository mirror (a desk)
        # reads the whole mirror: the runner says so for the call.
        workspace = getattr(adapter, "_confine_read_root", None) or cwd
        hands = getattr(adapter, "_hands", None)
        with_hands = hands in ("full", "field")
        private_tmp = tempfile.mkdtemp(prefix="lxm_tmp_")
        env = dict(kwargs.get("env") or os.environ)
        env["TMPDIR"] = private_tmp + "/"
        kwargs["env"] = env
        # An adapter that passes no cwd (codex sets its root with -C) would
        # start inside the caller's repo, which is closed: start in the
        # private temp dir instead.
        if kwargs.get("cwd") is None:
            kwargs["cwd"] = private_tmp
        prof = profile(lineage, home, workspace, private_tmp,
                       write_root=cwd if with_hands else None, write_guard=True)
        try:
            return inner(["sandbox-exec", "-p", prof, *cmd], *args, **kwargs)
        finally:
            shutil.rmtree(private_tmp, ignore_errors=True)

    adapter._run_cli = confined
    adapter._confinement = {
        "mechanism": "sandbox-exec allow-list v3.4 (file-read-data: $HOME, /tmp, per-user temp closed; "
                     "CLI needs + this call's workspace/session/private TMPDIR reopened; "
                     "file-write*: the same places closed for every lineage, CLI store + ~/Library + "
                     "private TMPDIR [+ desk with hands] reopened)"
                     + ("; inner sandbox dropped (cannot nest)" if lineage in WRITE_GUARD else ""),
        "profile_sha256": hashlib.sha256(base.encode()).hexdigest(),
        "version": "3.4",
        "own_store_residual": OWN_STORE_RESIDUAL.get(lineage)}
    return adapter._confinement["profile_sha256"]
