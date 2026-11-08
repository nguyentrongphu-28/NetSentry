# scripts/testing_utils.py
"""Bộ chạy test đơn giản (không cần pytest). File test vẫn tương thích pytest."""
import traceback


def run_tests(namespace, title):
    tests = [(n, f) for n, f in namespace.items() if n.startswith("test_") and callable(f)]
    print("=" * 64)
    print(f"[*] {title}: {len(tests)} test")
    print("=" * 64)
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  [PASS] {name}")
        except Exception:  # noqa: BLE001 - muốn bắt cả AssertionError lẫn lỗi bất ngờ
            failed += 1
            print(f"  [FAIL] {name}")
            traceback.print_exc()
    print("-" * 64)
    if failed:
        print(f"[!] {failed}/{len(tests)} test THẤT BẠI")
    else:
        print(f"[OK] {len(tests)}/{len(tests)} test đạt")
    return failed == 0
