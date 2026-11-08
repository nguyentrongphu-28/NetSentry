# scripts/run_all_tests.py -- chạy toàn bộ test Tuần 3-7 (không cần mạng/thiết bị/API key)
#   python scripts/run_all_tests.py
import sys
import unittest

import _bootstrap  # noqa: F401
from tests.testing_utils import run_tests
from tests.unit import test_integration_a_week7, test_week3, test_week4, test_week5, test_week6, test_week7

if __name__ == "__main__":
    ok = True
    for mod, title in [(test_week3, "TUẦN 3"), (test_week4, "TUẦN 4"), (test_week5, "TUẦN 5"), (test_week6, "TUẦN 6")]:
        ok &= run_tests(vars(mod), title)
        print()
    print("=" * 64)
    print("[*] TUẦN 7: unittest (AI assistant + kiểm thử an toàn)")
    print("=" * 64)
    res = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(test_week7))
    res2 = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(test_integration_a_week7))
    ok &= res.wasSuccessful() and res2.wasSuccessful()
    print("\nTẤT CẢ ĐẠT" if ok else "\nCÓ TEST THẤT BẠI - xem chi tiết phía trên")
    sys.exit(0 if ok else 1)
