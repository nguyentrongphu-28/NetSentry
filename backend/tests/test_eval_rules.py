import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from eval_rules import compute_metrics  # noqa: E402


def test_perfect():
    m = compute_metrics([({"A"}, {"A"}), (set(), set())])
    assert m["overall"]["precision"] == 1.0 and m["overall"]["recall"] == 1.0


def test_false_positive_and_negative():
    m = compute_metrics([({"A"}, {"A", "B"}), ({"C"}, set())])
    assert m["per_rule"]["B"]["fp"] == 1 and m["per_rule"]["C"]["fn"] == 1
    assert m["overall"]["precision"] == 0.5 and m["overall"]["recall"] == 0.5


def test_empty_is_none_not_division_error():
    assert compute_metrics([])["overall"]["precision"] is None
