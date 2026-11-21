# NetSentry Evaluation & Delivery Framework

Thư mục này chứa các công cụ đánh giá, giao thức kiểm thử, và tập dữ liệu mẫu (corpus) phục vụ việc nghiệm thu và đo lường định lượng các chỉ số an toàn, độ chính xác của NetSentry.

---

## 1. Cấu Trúc Thư Mục

- `metrics.py`: Module tính toán các chỉ số thống kê (P/R/F1, ma trận nhầm lẫn 3x3, khoảng tin cậy Wilson 95%, percentiles p50/p95).
- `rule_eval.py`: Công cụ đánh giá độ chính xác của Rule Engine trên tập corpus so với nhãn đúng `labels.json`.
- `perf_eval.py`: Công cụ tổng hợp thời gian audit và tỷ lệ kết nối từ cơ sở dữ liệu.
- `remediation_eval.py`: Công cụ tổng hợp tỷ lệ xác minh, rollback, và can thiệp thủ công từ bảng `remediation_executions`.
- `security_matrix.py` & `security_matrix.yaml`: Công cụ và ma trận kiểm thử bảo mật (15 yêu cầu an toàn S1–S15).
- `ai_eval.py`: Đánh giá module AI (bộ tấn công prompt injection và bộ câu hỏi mẫu).
- `corpus/`:
  - `configs/dev/*.cfg`: Tập cấu hình phát triển (dev split).
  - `configs/test/*.cfg`: Tập cấu hình kiểm tra chính thức (test split).
  - `labels.json`: Nhãn đúng (ground truth) do con người gán độc lập.
  - `MANIFEST.sha256`: Bảng băm đóng băng tập test.
  - `PROVENANCE.md`: Nhật ký nguồn gốc dữ liệu và gán nhãn.
- `ai/`:
  - `injection_cases.json`: 20 ca tấn công prompt injection.
  - `question_set.json`: Bộ câu hỏi/findings chuẩn cho 8 rule.
  - `rubric_template.csv`: Phiếu chấm chất lượng giải thích của AI.

---

## 2. Hướng Dẫn Chạy Đánh Giá

### 2.1. Đánh giá Rule Engine trên tập Test đã đóng băng
```bash
# Kiểm tra tính toàn vẹn của tập test và đo độ chính xác
python evaluation/rule_eval.py --split test

# Chạy trên tập dev
python evaluation/rule_eval.py --split dev

# Xuất báo cáo JSON và CSV
python evaluation/rule_eval.py --split test --json reports/rule_eval.json --csv reports/rule_eval.csv
```

### 2.2. Kiểm tra Ma Trận Bảo Mật
```bash
python evaluation/security_matrix.py
```

### 2.3. Đánh giá Hiệu Năng & Khắc Phục
```bash
python evaluation/perf_eval.py --db-path netsentry.db
python evaluation/remediation_eval.py --db-path netsentry.db
```

### 2.4. Đánh giá AI (Prompt Injection Validator)
```bash
python evaluation/ai_eval.py
```
