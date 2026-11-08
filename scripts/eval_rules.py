#!/usr/bin/env python3
"""Measure rule precision/recall on labeled configs (plan week 8).

Cases file (default sample-data/eval/cases.json), list of:
  {"name": "telnet-on", "config_file": "sample-data/eval/telnet_on.txt", "expected_rule_ids": ["NS-001"]}
  (or "config": "<inline text>"). Configs MUST have secrets removed.

The runner is any importable function `module:function(config_text) -> iterable[str] of rule_ids`.
A's rule engine should expose one; example:
  PYTHONPATH=backend python scripts/eval_rules.py --runner app.audit.engine:run_rules_on_text
"""
import argparse
import importlib
import json
from collections import defaultdict
from pathlib import Path


def compute_metrics(results: list[tuple[set[str], set[str]]]) -> dict:
    """results: list of (expected_rule_ids, detected_rule_ids) per case."""
    tp, fp, fn = defaultdict(int), defaultdict(int), defaultdict(int)
    for exp, det in results:
        for r in exp & det: tp[r] += 1
        for r in det - exp: fp[r] += 1
        for r in exp - det: fn[r] += 1

    def prf(t: int, f_p: int, f_n: int) -> dict:
        p = t / (t + f_p) if t + f_p else None
        r = t / (t + f_n) if t + f_n else None
        return {"tp": t, "fp": f_p, "fn": f_n, "precision": p, "recall": r}

    per_rule = {r: prf(tp[r], fp[r], fn[r]) for r in sorted(set(tp) | set(fp) | set(fn))}
    overall = prf(sum(tp.values()), sum(fp.values()), sum(fn.values()))
    return {"overall": overall, "per_rule": per_rule}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", required=True)
    ap.add_argument("--cases", default="sample-data/eval/cases.json")
    a = ap.parse_args()
    mod, fn = a.runner.split(":")
    runner = getattr(importlib.import_module(mod), fn)
    base = Path(a.cases).parent
    results = []
    for c in json.loads(Path(a.cases).read_text()):
        text = c.get("config") or (base.parent.parent / c["config_file"]).read_text()
        results.append((set(c["expected_rule_ids"]), set(runner(text))))
    print(json.dumps(compute_metrics(results), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
