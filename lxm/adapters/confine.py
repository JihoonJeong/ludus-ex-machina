"""Per-call READ confinement for measurement fields (macOS `sandbox-exec`).

Why (2026-09-25, from-lxm/083): the report-fidelity harness blocked writes
("hands none") and left reads open to the whole disk. From an empty tempdir,
grok grepped the home directory and read another village's ledgers, the hub
envelope holding the case originals, and LxM's own scorer. The canary's bait
sat INSIDE the workspace, so reach outside it was never measured.

This wraps one CLI call so that it cannot read the places that hold other
people's text or the answer key:
  - ~/Projects (every repo on this machine: villages, the relay, LxM state/)
  - ~/Documents, ~/Desktop, ~/Downloads, the Claude desktop app's data
  - OTHER lineages' CLI stores entirely (they hold other sessions' prompts)
  - within the lineage's OWN store, the sessions of other working
    directories, where the CLI lets us name them apart (claude, grok)
The CLI keeps its own config, auth and the new session's files.

`file-read-data` is denied, not `file-read*`: contents and directory listings
are blocked, `stat` is not (CLIs `mkdir -p` through these trees). A brain can
still learn that a path exists; it cannot read it.

Games do not use this. It is installed only by a measurement script, and the
canary's REACH probe verifies it before any trial runs (fail-closed).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile

HOME = os.path.expanduser("~")

# The CLI store of each lineage (adapter type name → dir under $HOME).
STORES = {"claude": (".claude", ".claude.json"), "codex": (".codex",), "grok": (".grok",),
          "cursor": (".cursor",), "gemini": (".gemini",)}

# Inside a lineage's OWN store: other sessions' records. These hold other
# seats' prompts — on this machine, the village seats whose cases we measure
# (Tide is a cursor seat, Spark an agy seat), i.e. the answer key. Denied
# per CLI; the CLI keeps its config, auth and the new session's files.
#   subpaths: relative to $HOME, denied outright
#   regex:    denied by pattern ({home} filled in)
# claude keys project dirs by cwd ('/' → '-'), grok URL-encodes the cwd:
# trials run under /private/var/folders, so anything keyed to /Users is
# another session. cursor keys chats by md5(realpath(workspace)) and projects
# by the encoded path: the whole tree is denied and this call's own dirs are
# allowed back per call (see profile()).
OWN_STORE_DENY = {
    "claude": {"subpaths": (".claude/history.jsonl", ".claude/file-history", ".claude/todos",
                            ".claude/paste-cache", ".claude/shell-snapshots", ".claude/debug",
                            ".claude/backups", ".claude/sessions", ".claude/jobs"),
               "regex": (r"^{home}/\.claude/projects/-Users-",)},
    "grok": {"subpaths": (".grok/logs", ".grok/memtrace"),
             "regex": (r"^{home}/\.grok/sessions/%2FUsers",)},
    "codex": {"subpaths": (".codex/sessions", ".codex/archived_sessions", ".codex/history.jsonl",
                           ".codex/attachments"), "regex": ()},
    "cursor": {"subpaths": (".cursor/chats", ".cursor/projects", ".cursor/ai-tracking"), "regex": ()},
    "gemini": {"subpaths": (".gemini/antigravity-cli/brain", ".gemini/antigravity-cli/knowledge",
                            ".gemini/antigravity-cli/annotations", ".gemini/antigravity-cli/implicit",
                            ".gemini/antigravity-cli/history.jsonl",
                            ".gemini/antigravity-cli/conversation_summaries.db"), "regex": ()},
}
# What stays readable inside the own store, recorded with every run.
OWN_STORE_RESIDUAL = {
    "gemini": "~/.gemini/antigravity-cli/conversations/*.db (keyed by conversation id; "
              "the current one must stay readable, so all do)",
}


def _cursor_own_dirs(home: str, workspace: str) -> list[str]:
    real = os.path.realpath(workspace)
    enc = {p.lstrip("/").replace("/", "-").replace("_", "-") for p in (real, os.path.abspath(workspace))}
    return ([os.path.join(home, ".cursor/chats", hashlib.md5(real.encode()).hexdigest())]
            + [os.path.join(home, ".cursor/projects", e) for e in sorted(enc)])


DENY_TREES = ("Projects", "Documents", "Desktop", "Downloads",
              "Library/Application Support/Claude", "Library/Mail", "Library/Messages")


def _q(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


# Lineages whose own write-less mode is a sandbox of their own: macOS
# sandboxes do not nest (codex's seatbelt fails inside ours with
# "sandbox_apply: Operation not permitted", so its command tool dies). For
# these the adapter drops its inner sandbox and the outer profile takes the
# write denial over: nothing under $HOME but the CLI's own store, and never
# the workspace.
WRITE_GUARD = {"codex"}


def profile(lineage: str, home: str = HOME, workspace: str | None = None) -> str:
    rules = [f'(subpath "{_q(os.path.join(home, t))}")' for t in DENY_TREES]
    for other, names in STORES.items():
        if other != lineage:
            rules += [f'(subpath "{_q(os.path.join(home, n))}")' for n in names]
    own = OWN_STORE_DENY.get(lineage, {})
    rules += [f'(subpath "{_q(os.path.join(home, sp))}")' for sp in own.get("subpaths", ())]
    for rx in own.get("regex", ()):
        rules.append(f'(regex #"{rx.format(home=home.replace(".", r"\.") )}")')
    out = "(version 1)\n(allow default)\n(deny file-read-data\n  " + "\n  ".join(rules) + ")\n"
    if lineage == "cursor" and workspace:
        out += ("(allow file-read-data "
                + " ".join(f'(subpath "{_q(d)}")' for d in _cursor_own_dirs(home, workspace)) + ")\n")
    if lineage in WRITE_GUARD:
        own = " ".join(f'(subpath "{_q(os.path.join(home, n))}")' for n in STORES[lineage])
        out += f'(deny file-write* (subpath "{_q(home)}"))\n(allow file-write* {own})\n'
        if workspace:
            ws = {os.path.abspath(workspace), os.path.realpath(workspace)}
            out += "(deny file-write* " + " ".join(f'(subpath "{_q(w)}")' for w in sorted(ws)) + ")\n"
    return out


def profile_sha(lineage: str, home: str = HOME) -> str:
    return hashlib.sha256(profile(lineage, home).encode()).hexdigest()


def available() -> bool:
    return shutil.which("sandbox-exec") is not None


def install(adapter, lineage: str, home: str = HOME) -> str:
    """Route every CLI call of this adapter through sandbox-exec with the
    lineage's profile. Returns the profile sha (record it with the run)."""
    if not available():
        raise RuntimeError("sandbox-exec not found — read confinement unavailable on this host")
    base = profile(lineage, home)
    inner = adapter._run_cli
    if lineage in WRITE_GUARD:
        adapter._outer_sandbox = True      # the adapter drops its inner sandbox

    def confined(cmd, *args, **kwargs):
        workspace = kwargs.get("cwd") or (cmd[cmd.index("-C") + 1] if "-C" in cmd else None)
        # An adapter that passes no cwd (codex sets its root with -C) would
        # start the process inside the caller's repo — under ~/Projects, which
        # the profile denies, so the CLI dies on its own cwd ("Operation not
        # permitted"). Start it somewhere neutral instead.
        if kwargs.get("cwd") is None:
            kwargs["cwd"] = tempfile.gettempdir()
        prof = profile(lineage, home, workspace)
        return inner(["sandbox-exec", "-p", prof, *cmd], *args, **kwargs)

    adapter._run_cli = confined
    adapter._confinement = {
        "mechanism": "sandbox-exec file-read-data deny"
                     + (" + outer write guard (inner sandbox cannot nest)" if lineage in WRITE_GUARD else ""),
        "profile_sha256": hashlib.sha256(base.encode()).hexdigest(),
        "own_store_residual": OWN_STORE_RESIDUAL.get(lineage)}
    return adapter._confinement["profile_sha256"]
