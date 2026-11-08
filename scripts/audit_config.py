# scripts/audit_config.py -- chạy rule audit lên 1 file cấu hình
#   python scripts/audit_config.py data/sample_configs/switch_bad.cfg --role switch
import sys

import _bootstrap  # noqa: F401
from app.audit.rule_engine import main

if __name__ == "__main__":
    sys.exit(main())
