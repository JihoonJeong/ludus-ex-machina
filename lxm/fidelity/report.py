"""Pull the brain's own completion report out of its reply.

The report is the thing being measured, so extraction must never quietly
"fix" it. An unparseable report is recorded as missing — never skipped, never
guessed at — for the same reason door_audit treats an unreadable envelope as a
finding: a silent extraction break looks identical to a well-behaved brain.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

DONE = {"done", "completed", "complete", "success", "succeeded", "ok",
        "written", "created"}
FAILED = {"failed", "fail", "error", "blocked", "skipped", "not done",
          "not_done", "unable", "impossible", "missing"}

_FENCED = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def _balanced_objects(text: str) -> list[str]:
    """Every top-level {...} that mentions "artifacts", brace-matched with
    string awareness — the fallback for CLIs that drop code fences."""
    out, i = [], 0
    while True:
        i = text.find("{", i)
        if i < 0:
            return out
        depth, j, in_str, esc = 0, i, False, False
        while j < len(text):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[i:j + 1]
                    if '"artifacts"' in chunk:
                        out.append(chunk)
                    break
            j += 1
        i = j + 1 if j > i else i + 1


def _status(raw) -> str:
    s = str(raw).strip().lower()
    if s in DONE:
        return "done"
    if s in FAILED:
        return "failed"
    return "unknown"


def normalize_path(raw: str, sandbox: Path | None = None) -> str:
    """Relative POSIX form. Absolute paths inside the sandbox are made relative
    (macOS /var → /private/var is resolved on both sides); anything else is
    kept as written, so a path that points outside stays visibly wrong."""
    p = str(raw).strip().strip("`").strip()
    if sandbox is not None and p.startswith("/"):
        try:
            return Path(p).resolve().relative_to(sandbox.resolve()).as_posix()
        except ValueError:
            return p
    while p.startswith("./"):
        p = p[2:]
    return PurePosixPath(p).as_posix() if p else p


def extract_report(text: str, sandbox: Path | None = None) -> list[dict] | None:
    """The LAST parseable report block wins — a brain that drafts a report,
    keeps working, and reports again means the final one."""
    candidates = [m.group(1) for m in _FENCED.finditer(text or "")]
    candidates += _balanced_objects(text or "")
    for raw in reversed(candidates):
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        arts = obj.get("artifacts") if isinstance(obj, dict) else None
        if not isinstance(arts, list):
            continue
        entries = []
        for a in arts:
            if not isinstance(a, dict) or "path" not in a:
                continue
            entries.append({
                "path": normalize_path(a.get("path", ""), sandbox),
                "status": _status(a.get("status", "")),
                "raw_status": str(a.get("status", "")),
                "note": str(a.get("note", ""))[:300],
            })
        return entries
    return None
