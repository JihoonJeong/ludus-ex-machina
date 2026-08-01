"""PhysGym IMPORT smoke — LxM side (external agent through OUR harness).

Mirrors Ludex's creature import smoke but with an EXTERNAL agent (haiku via
our ClaudeCodeAdapter), proving LxM can import a PhysGym env into its own
harness and run an external agent against it with OUR carriage + masking +
result control (the diagnostic-axis path). Not the full walk — a smoke.
"""
import json
import re
import sys
import tempfile

sys.path.insert(0, "/Users/jihoon/Projects/ludus-ex-machina")
import physgym
from lxm.adapters.claude_code import ClaudeCodeAdapter

ENV_ID = 285
adapter = ClaudeCodeAdapter({"agent_id": "physgym", "model": "claude-haiku-4-5-20251001"})


def ask(prompt):
    r = adapter._invoke_once(tempfile.mkdtemp(prefix="pg_"), prompt)
    return (r.get("stdout") or "").strip()


def extract_json(text, kind):
    m = re.search(r"\[.*\]" if kind == "arr" else r"\{.*\}", text, re.S)
    return json.loads(m.group()) if m else None


def run(mode):
    print(f"\n{'='*66}\nMODE: {mode}")
    ri = physgym.ResearchInterface(env=ENV_ID, sample_quota=50, test_quota=2, mode=mode)
    report = ri.generate_report()
    params = ri.input_params
    print(f"params (masking axis): {params}")
    print(f"report[:150]: {report[:150].replace(chr(10),' ')}")
    if mode != "default":
        return  # masking-only demo for the anonymous level

    # --- carriage §point-of-use: the report (law-relevant context) is put in
    #     the decision-turn prompt by OUR driver, every turn. ---
    p1 = (report + f"\n\nYou may run experiments. Propose 5 experiments as a "
          f"JSON array of objects, each with numeric keys {params}. "
          f"Reply ONLY the JSON array.")
    samples = extract_json(ask(p1), "arr")
    samples = [{k: float(s[k]) for k in params} for s in samples][:5]
    results = ri.run_experiment(samples)
    obs = "\n".join(f"  {s} -> {r}" for s, r in zip(samples, results))
    print(f"agent ran {len(results)} experiments (observations harvested):")
    print(obs)

    p2 = (report + f"\n\nExperiments you ran:\n{obs}\n\nPropose a formula for "
          f"the output as a function of {params}. Reply ONLY a JSON object "
          f'{{"expr": "<sympy expression in {params}>", '
          f'"func": "def hypothesis_function({", ".join(params)}): return <expr>"}}.')
    hyp = extract_json(ask(p2), "obj")
    print(f"agent hypothesis: expr = {hyp.get('expr')}")
    ev = ri.test_hypothesis(candidate_function=hyp["func"], candidate_expr=hyp["expr"])
    mse = ev.get("mse") if isinstance(ev, dict) else None
    r2 = ev.get("r2") if isinstance(ev, dict) else None
    print(f"RESULT harvested: MSE={mse} R2={r2}  (raw keys: {list(ev.keys()) if isinstance(ev,dict) else ev})")


run("default")
run("anonymous_no_context_no_description")
print(f"\n{'='*66}\nCARRIAGE: report embedded in every decision-turn prompt by "
      "OUR driver (point-of-use OK). MASKING: default named vs anonymous "
      "var_N = acquirability axis under OUR control. External agent (haiku) "
      "drove the imported wall through the LxM harness.")
