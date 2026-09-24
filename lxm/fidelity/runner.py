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

import json
import shutil
import subprocess
import tempfile
import time
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

        raw: dict = {}
        original = adapter._run_cli

        def spy(*args, **kwargs):
            r = original(*args, **kwargs)
            raw["stdout"], raw["stderr"] = r.get("stdout", ""), r.get("stderr", "")
            return r

        adapter._run_cli = spy
        t0 = time.monotonic()
        try:
            res = adapter._invoke_once(str(sandbox), build_prompt(task))
        except Exception as e:  # a crashed adapter is a route failure, not a verdict
            res = {"stdout": "", "stderr": f"adapter exception: {e}",
                   "exit_code": -1, "timed_out": False}
        finally:
            adapter._run_cli = original
        latency = round(time.monotonic() - t0, 1)

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
        (dest / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
        return record
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
