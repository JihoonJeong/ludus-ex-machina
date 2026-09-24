"""One trial: fresh sandbox, one call, then read the disk and the report.

Containment, in the order it matters:
  - The canary gate runs before any trial (the script does this, fail-closed).
  - Every trial gets its own empty tempdir; fixtures are written into it.
  - One `_invoke_once` per trial, never the retrying `invoke`: a retry after a
    partial write would score two attempts as one. A failed call is a route
    failure, recorded and excluded — not retried into a success.
  - The repo's `git status` is taken before and after. Codex runs with the
    repo as its process cwd (its workspace comes from `-C`), so a misdirected
    write would land here; any new change is flagged, loudly.
  - The whole sandbox is archived next to the record, so every category can be
    re-derived by hand from the files the brain actually left.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from lxm.fidelity.report import extract_report
from lxm.fidelity.score import score_trial, snapshot
from lxm.fidelity.tasks import build_prompt


def git_status(repo: Path) -> set[str]:
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                             cwd=repo, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return set(out.stdout.splitlines()) if out.returncode == 0 else set()


def git_head(repo: Path) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def usage_from_raw(lineage: str, raw_stdout: str) -> dict | None:
    """CLI self-reported tokens, where the CLI emits them. Claude's JSON and
    Codex's JSONL do; agy and grok print plain text and do not — those stay
    None rather than being estimated, so a missing number reads as missing."""
    if not raw_stdout:
        return None
    if lineage == "claude":
        try:
            d = json.loads(raw_stdout)
        except (json.JSONDecodeError, ValueError):
            return None
        u = d.get("usage") or {}
        if not u:
            return None
        tin = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                          "cache_read_input_tokens"))
        return {"in": tin, "out": u.get("output_tokens"),
                "cost_usd": d.get("total_cost_usd")}
    if lineage == "codex":
        tin = tout = 0
        seen = False
        for line in raw_stdout.splitlines():
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            u = obj.get("usage") if isinstance(obj, dict) else None
            if isinstance(u, dict):
                seen = True
                tin += u.get("input_tokens") or 0
                tout += u.get("output_tokens") or 0
        return {"in": tin, "out": tout} if seen else None
    return None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def file_hashes(tree: dict) -> dict[str, str]:
    """relpath -> sha256 of the bytes, or "dir"."""
    return {rel: ("dir" if data is None else hashlib.sha256(data).hexdigest())
            for rel, data in sorted(tree.items())}


_TOOL_ITEMS = {"command_execution", "file_change", "mcp_tool_call", "web_search"}


def tool_events_from_raw(lineage: str, raw_stdout: str) -> list[dict] | None:
    """Tool success/failure evidence where the CLI exposes it — codex's JSONL
    does. Reasoning and message items are dropped on purpose: the judge gets
    what the tools did, never the model's intermediate reasoning. CLIs that do
    not expose tool events return None, which the packet writes as unknown."""
    if lineage != "codex" or not raw_stdout:
        return None
    events = []
    for line in raw_stdout.splitlines():
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        item = obj.get("item") if isinstance(obj, dict) else None
        if obj.get("type") != "item.completed" or not isinstance(item, dict):
            continue
        if item.get("type") not in _TOOL_ITEMS:
            continue
        ev = {"type": item.get("type"), "status": item.get("status"),
              "exit_code": item.get("exit_code")}
        if item.get("command"):
            ev["command"] = str(item["command"])[:400]
        if item.get("changes"):
            ev["changes"] = [{"path": c.get("path"), "kind": c.get("kind")}
                             for c in item["changes"] if isinstance(c, dict)][:20]
        events.append(ev)
    return events


def run_trial(adapter, lineage: str, task, trial_id: str, archive: Path,
              repo: Path, model: str | None = None) -> dict:
    sandbox = Path(tempfile.mkdtemp(prefix="lxm_fid_"))
    try:
        for rel, data in task.fixtures.items():
            p = sandbox / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        before = snapshot(sandbox)
        git_before = git_status(repo)
        head_before = git_head(repo)
        prompt = build_prompt(task)
        t_start = _now()

        raw: dict = {}
        original = adapter._run_cli

        def spy(*args, **kwargs):
            r = original(*args, **kwargs)
            raw["stdout"], raw["stderr"] = r.get("stdout", ""), r.get("stderr", "")
            return r

        adapter._run_cli = spy
        t0 = time.monotonic()
        try:
            res = adapter._invoke_once(str(sandbox), prompt)
        except Exception as e:  # a crashed adapter is a route failure, not a verdict
            res = {"stdout": "", "stderr": f"adapter exception: {e}",
                   "exit_code": -1, "timed_out": False}
        finally:
            adapter._run_cli = original
        latency = round(time.monotonic() - t0, 1)
        t_end = _now()

        after = snapshot(sandbox)
        stray_outside = sorted(git_status(repo) - git_before)
        head_after = git_head(repo)
        text = res.get("stdout") or ""
        route_fail = bool(res.get("exit_code", 0) != 0 or res.get("timed_out")
                          or not text.strip())
        report = extract_report(text, sandbox)
        record = {
            "trial_id": trial_id, "lineage": lineage, "model": model,
            "task_id": task.task_id, "latency_s": latency,
            "route_fail": route_fail,
            "route_detail": None if not route_fail else {
                "exit_code": res.get("exit_code"), "timed_out": res.get("timed_out"),
                "stderr_tail": (res.get("stderr") or "")[-400:]},
            "usage": usage_from_raw(lineage, raw.get("stdout", "")),
            "t_start": t_start, "t_end": t_end,
            "code_commit": head_before,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "reply_text": text,
            "files_before": file_hashes(before),
            "files_after": file_hashes(after),
            "tool_events": tool_events_from_raw(lineage, raw.get("stdout", "")),
            "stray_outside_sandbox": stray_outside,
            # The repo check cannot tell whose hand changed the tree. On the
            # 2026-09-24 pilot it fired on the operator's own concurrent edit
            # (committed as badf3f9 mid-trial). A moved HEAD during the trial,
            # or a stray that names committed files, is operator activity to
            # rule out before anyone reads it as a brain write.
            "repo_head_moved": head_before != head_after,
            "score": score_trial(task, before, after, report),
        }
        dest = archive / trial_id
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(sandbox, dest / "tree", dirs_exist_ok=True)
        (dest / "reply.txt").write_text(text, encoding="utf-8")
        (dest / "prompt.txt").write_text(prompt, encoding="utf-8")
        # Raw CLI output stays in the local archive for audit; it can hold the
        # model's reasoning, so it never goes into a judge packet.
        (dest / "raw_stdout.txt").write_text(raw.get("stdout", ""), encoding="utf-8")
        (dest / "raw_stderr.txt").write_text(raw.get("stderr", ""), encoding="utf-8")
        (dest / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
        return record
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
