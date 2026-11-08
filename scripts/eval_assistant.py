#!/usr/bin/env python3
"""Evaluate the AI assistant on the standard question set.

Usage (from repo root):
  PYTHONPATH=backend python scripts/eval_assistant.py            # uses ASSISTANT_PROVIDER env (default: mock)
  ASSISTANT_PROVIDER=openai_compat ASSISTANT_BASE_URL=... ASSISTANT_MODEL=... ASSISTANT_API_KEY=... \
    PYTHONPATH=backend python scripts/eval_assistant.py --json results.json

Metrics: schema-valid answer rate (for answerable questions), injection block rate, mean latency.
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from app.assistant.providers import provider_from_env
from app.assistant.schemas import ExplainRequest, FindingInput
from app.assistant.service import explain

FINDING = FindingInput(
    rule_id="NS-001", title="Telnet enabled on VTY lines", severity="high",
    evidence=["line vty 0 4", " transport input telnet ssh"],
    rationale="Telnet is clear text.", remediation="Use 'transport input ssh'.",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(Path(__file__).resolve().parents[1] / "tests/qa/assistant_questions.json"))
    ap.add_argument("--json", help="write detailed results to this file")
    a = ap.parse_args()
    provider = provider_from_env()
    cases = json.loads(Path(a.questions).read_text())
    rows, lat = [], []
    for c in cases:
        t = time.perf_counter()
        r = explain(ExplainRequest(finding=FINDING, question=c["question"]), provider)
        dt = time.perf_counter() - t
        lat.append(dt)
        ok = (r.explanation is not None) if c["expect"] == "answer" else (r.explanation is None)
        rows.append({"id": c["id"], "expect": c["expect"], "ok": ok, "latency_s": round(dt, 3), "rejected_reason": r.rejected_reason})
    ans = [r for r in rows if r["expect"] == "answer"]
    blk = [r for r in rows if r["expect"] == "blocked"]
    summary = {
        "provider": provider.name,
        "answerable": f"{sum(r['ok'] for r in ans)}/{len(ans)}",
        "injection_blocked": f"{sum(r['ok'] for r in blk)}/{len(blk)}",
        "mean_latency_s": round(statistics.mean(lat), 3),
    }
    print(json.dumps(summary, indent=2))
    for r in rows:
        if not r["ok"]:
            print("FAIL", r)
    if a.json:
        Path(a.json).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
