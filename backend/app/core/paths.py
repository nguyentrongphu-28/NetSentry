# backend/app/core/paths.py
"""Đường dẫn tập trung. Luôn tính theo thư mục gốc repo, không phụ thuộc cwd.

Cấu trúc repo:  <root>/{backend,data,docs,frontend,scripts}
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]      # <root>
BACKEND_DIR = PROJECT_ROOT / "backend"
DATA_DIR = PROJECT_ROOT / "data"
INVENTORY_PATH = DATA_DIR / "inventory.json"
POLICY_PATH = DATA_DIR / "lab_policy.json"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
REPORT_DIR = DATA_DIR / "reports"
RULES_DIR = DATA_DIR / "rules"
RULES_PATH = RULES_DIR / "rules.json"
SAMPLE_DIR = DATA_DIR / "sample_configs"
QUESTIONS_PATH = DATA_DIR / "standard_questions.json"
