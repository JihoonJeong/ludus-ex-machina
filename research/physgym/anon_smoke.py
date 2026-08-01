"""Decisive R2/R1 test: anonymous masking, HONEST carriage (observations in the
prompt), NO organ. If haiku still solves in ONE round, then (a) anonymous is
not a ceiling-escape by itself and (b) cross-turn memory is irrelevant — the
no-reload arm would measure an artifact, not 'does memory help induction'."""
import json
import re
import sys
import tempfile

sys.path.insert(0, "/Users/jihoon/Projects/ludus-ex-machina")
import physgym
from lxm.adapters.claude_code import ClaudeCodeAdapter

adapter = ClaudeCodeAdapter({"agent_id": "pg", "model": "claude-haiku-4-5-20251001"})


def ask(p):
    return (adapter._invoke_once(tempfile.mkdtemp(prefix="pg_"), p).get("stdout") or "").strip()


def ejson(t, k):
    m = re.search(r"\[.*\]" if k == "arr" else r"\{.*\}", t, re.S)
    return json.loads(m.group()) if m else None


def trial(env_id):
    ri = physgym.ResearchInterface(env=env_id, sample_quota=50, test_quota=2,
                                   mode="anonymous_no_context_no_description")
    rep, params = ri.generate_report(), ri.input_params
    p1 = (rep + f"\n\nPropose 8 experiments as a JSON array of objects with "
          f"numeric keys {params}. Reply ONLY the JSON array.")
    try:
        samples = [{k: float(s[k]) for k in params} for s in ejson(ask(p1), "arr")][:8]
    except Exception as e:
        return f"env {env_id}: propose-fail {e}"
    results = ri.run_experiment(samples)
    obs = "\n".join(f"  {s} -> {r.get('output')}" for s, r in zip(samples, results))
    # HONEST carriage: all observations in the prompt (no organ, no reload trick)
    p2 = (rep + f"\n\nObservations:\n{obs}\n\nInfer a formula for the output as "
          f"a function of {params}. Reply ONLY {{\"expr\":\"...\",\"func\":"
          f"\"def hypothesis_function({', '.join(params)}): return <expr>\"}}.")
    hyp = ejson(ask(p2), "obj")
    ev = ri.test_hypothesis(candidate_function=hyp["func"], candidate_expr=hyp["expr"])
    fm = ev.get("fit_metrics", {}) if isinstance(ev, dict) else {}
    return (f"env {env_id} ANON: expr={hyp.get('expr')} | is_correct="
            f"{ev.get('is_correct')} R2={fm.get('r2')} MSE={fm.get('mse')}")


for eid in (285, 42, 100):
    try:
        print(trial(eid))
    except Exception as e:
        print(f"env {eid}: ERROR {e}")
