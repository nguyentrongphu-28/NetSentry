# scripts/collect_snapshot.py -- thu thập snapshot từ inventory (cần .env + netmiko + thiết bị thật)
#   python scripts/collect_snapshot.py [--device NAME] [--from-file cfg.txt]
import sys

import _bootstrap  # noqa: F401
from app.devices.snapshot_collector import main

if __name__ == "__main__":
    sys.exit(main())
