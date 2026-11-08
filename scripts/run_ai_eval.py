"""Chạy toàn bộ test tuần 7 và in bảng kết quả theo nhóm. Ghi data/reports/ai_eval_results.json (để đưa vào báo cáo).

    python scripts/run_ai_eval.py            # offline, dùng MockLLM — không cần mạng/API key
    python scripts/run_ai_eval.py --live     # THÊM: gọi LLM thật cho các câu hỏi dạng 'answer' và đo tỉ lệ phản hồi qua validator
                                  # cần: NETSENTRY_AI_PROVIDER, NETSENTRY_AI_MODEL, OPENAI_API_KEY | GEMINI_API_KEY
Lưu ý: bộ offline kiểm tra CƠ CHẾ PHÒNG VỆ (validator/gate/policy), không đo chất lượng giải thích của LLM thật.
"""
import json
import os
import sys
import time
import unittest

import _bootstrap  # noqa: F401  (thêm backend/ vào sys.path)
from app.core.paths import REPORT_DIR

OUT_PATH = os.path.join(str(REPORT_DIR), "ai_eval_results.json")

GROUPS = {"sch": "Schema & bám bằng chứng", "cmd": "Lệnh/nội dung đầu ra", "inj": "Prompt injection & lộ bí mật",
          "pol": "Chính sách VLAN/port", "flow": "Luồng nghiệp vụ", "arch": "Kiến trúc (AI không có đường SSH)"}


class _Result(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.rows = []

    def _rec(self, test, status):
        self.rows.append({"test": test._testMethodName, "status": status})

    def addSuccess(self, t): super().addSuccess(t); self._rec(t, "PASS")
    def addFailure(self, t, e): super().addFailure(t, e); self._rec(t, "FAIL")
    def addError(self, t, e): super().addError(t, e); self._rec(t, "ERROR")


def run_offline():
    from tests.unit import test_week7
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_week7)
    res = unittest.TextTestRunner(stream=open(os.devnull, "w"), resultclass=_Result).run(suite)
    table = {}
    for r in res.rows:
        g = r["test"].split("_")[1]
        t = table.setdefault(g, {"pass": 0, "total": 0, "failed": []})
        t["total"] += 1
        if r["status"] == "PASS":
            t["pass"] += 1
        else:
            t["failed"].append(r["test"])
    print(f"{'Nhóm':42} {'Đạt':>7}")
    for g, name in GROUPS.items():
        t = table.get(g, {"pass": 0, "total": 0})
        print(f"{name:42} {t['pass']:>3}/{t['total']:<3}")
    total, ok = len(res.rows), sum(1 for r in res.rows if r["status"] == "PASS")
    print(f"{'TỔNG':42} {ok:>3}/{total:<3}")
    for g, t in table.items():
        for f in t.get("failed", []):
            print("  ✗", f)
    return {"offline": {"total": total, "passed": ok, "groups": table}}


def run_live():
    from app.assistant import AssistantService, PolicyGate, make_client_from_env
    from tests.unit import test_week7 as T
    svc = AssistantService(make_client_from_env(), T.RULES, PolicyGate(T.POLICY_DICT))
    out, n_llm, n_fb, lat = [], 0, 0, []
    findings = [T.F_TELNET, T.F_HTTP]
    for q in T.QUESTIONS:
        if q["expect"] not in ("answer", "insufficient"):
            continue
        t0 = time.time()
        r = svc.chat(q["message"], findings)
        lat.append(time.time() - t0)
        n_llm += r["source"] == "llm"
        n_fb += r["source"] == "fallback"
        out.append({"id": q["id"], "source": r["source"], "attempts": r.get("attempts"), "warnings": r.get("warnings")})
    print(f"LIVE: {n_llm} phản hồi LLM được chấp nhận, {n_fb} phải dùng fallback; "
          f"độ trễ TB {sum(lat) / max(len(lat), 1):.1f}s")
    return {"live": {"accepted": n_llm, "fallback": n_fb, "items": out}}


if __name__ == "__main__":
    result = run_offline()
    if "--live" in sys.argv:
        result.update(run_live())
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    sys.exit(0 if result["offline"]["passed"] == result["offline"]["total"] else 1)
