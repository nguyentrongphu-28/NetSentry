# backend/app/core/env.py
"""Nạp file .env ở thư mục gốc repo (KEY=VALUE). Biến môi trường thật luôn được ưu tiên. Không bao giờ in giá trị."""
import os

from app.core.paths import PROJECT_ROOT


def load_env(path=None):
    path = path or (PROJECT_ROOT / ".env")
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass
