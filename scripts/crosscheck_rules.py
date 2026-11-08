"""Đối chiếu độc lập: viết lại logic rule từ rules.json (KHÔNG dùng code của A) rồi so với expected_results.json.

    python scripts/crosscheck_rules.py                      # kiểm tra ground truth có nhất quán với rules.json không

Dùng ở Tuần 8: có thể import parse()/run() từ file này để so với evaluate_config của A trên cấu hình THẬT; nếu lệch, xem lại cả hai phía.
Giới hạn: đây là cách đọc rule của MỘT người viết khác, không phải 'độ chính xác trên thiết bị thật'."""
import json, re

def parse(text):
    """Trả về (top_lines, blocks[(header, [children])]). Bỏ banner, comment."""
    top, blocks, cur, in_banner, delim = [], [], None, False, None
    for raw in text.splitlines():
        line = raw.rstrip()
        if in_banner:
            if delim and delim in line: in_banner = False
            continue
        s = line.strip()
        if not s or s.startswith("!") or s.startswith("Building configuration") or s.startswith("Current configuration"):
            continue
        m = re.match(r"^banner\s+\S+\s+(\^C|\S)", s)
        if m and not line.startswith(" "):
            top.append(s)
            d = m.group(1)
            rest = s[m.end():]
            if d not in rest:      # banner kéo dài nhiều dòng
                in_banner, delim = True, d
            continue
        if line.startswith(" "):
            if cur is not None: cur[1].append(s)
        else:
            if s == "end": continue
            cur = (s, []); blocks.append(cur); top.append(s)
    return top, blocks

def run(rule, top, blocks):
    ok = True
    for c in rule["checks"]:
        t, pat = c["type"], c["pattern"]
        if t == "required_line":
            ok &= any(re.search(pat, l) for l in top)
        elif t == "forbidden_line":
            ok &= not any(re.search(pat, l) for l in top)
        elif t == "block_required":
            bs = [b for b in blocks if re.search(c["block_pattern"], b[0])]
            if c.get("exclude_header"): bs = [b for b in bs if not re.search(c["exclude_header"], b[0])]
            if c.get("only_if"): bs = [b for b in bs if any(re.search(c["only_if"], x) for x in b[1])]
            if not bs and "only_if" not in c: ok = False   # không có khối → không đạt
            for b in bs: ok &= any(re.search(pat, x) for x in b[1])
    return "PASS" if ok else "FAIL"

if __name__ == "__main__":
    import os, sys
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    samples = os.path.join(base, "sample_configs")
    rules = json.load(open(os.path.join(base, "rules", "rules.json"), encoding="utf-8"))
    exp = json.load(open(os.path.join(samples, "expected_results.json"), encoding="utf-8"))
    tp=fp=fn=tn=0; diffs=[]
    for f, e in exp.items():
        if f.startswith("_"): continue
        top, blocks = parse(open(os.path.join(samples, f), encoding="utf-8").read())
        for r in rules:
            got = run(r, top, blocks); want = e[r["rule_id"]]
            if want=="FAIL" and got=="FAIL": tp+=1
            elif want=="PASS" and got=="FAIL": fp+=1; diffs.append((f,r["rule_id"],want,got))
            elif want=="FAIL" and got=="PASS": fn+=1; diffs.append((f,r["rule_id"],want,got))
            else: tn+=1
    print("TP",tp,"FP",fp,"FN",fn,"TN",tn, "cặp:",tp+fp+fn+tn)
    for d in diffs: print("LỆCH:",d)
