import math
import pytest
from evaluation.metrics import (
    BinaryConfusionMatrix,
    ThreeClassConfusionMatrix,
    calculate_percentile,
    format_rate,
    wilson_score_interval,
)


def test_binary_confusion_matrix_calculations():
    # TP=10, FP=2, FN=1, TN=20
    cm = BinaryConfusionMatrix(tp=10, fp=2, fn=1, tn=20)
    assert cm.total == 33
    assert cm.precision == pytest.approx(10 / 12)
    assert cm.recall == pytest.approx(10 / 11)
    expected_f1 = 2 * ((10 / 12) * (10 / 11)) / ((10 / 12) + (10 / 11))
    assert cm.f1 == pytest.approx(expected_f1)
    assert cm.accuracy == pytest.approx(30 / 33)


def test_zero_denominator_handling():
    # Zero positives predicted -> precision denominator is 0
    cm_no_pred = BinaryConfusionMatrix(tp=0, fp=0, fn=5, tn=5)
    assert cm_no_pred.precision is None
    assert format_rate(cm_no_pred.precision) == "n/a"
    assert cm_no_pred.recall == 0.0
    assert cm_no_pred.f1 is None
    assert format_rate(cm_no_pred.f1) == "n/a"

    # Zero actual positives -> recall denominator is 0
    cm_no_actual = BinaryConfusionMatrix(tp=0, fp=3, fn=0, tn=7)
    assert cm_no_actual.recall is None
    assert format_rate(cm_no_actual.recall) == "n/a"
    assert cm_no_actual.precision == 0.0
    assert cm_no_actual.f1 is None

    # Completely empty matrix
    cm_empty = BinaryConfusionMatrix(tp=0, fp=0, fn=0, tn=0)
    assert cm_empty.precision is None
    assert cm_empty.recall is None
    assert cm_empty.f1 is None
    assert cm_empty.accuracy is None


def test_wilson_score_interval_known_values():
    # n=0
    assert wilson_score_interval(0, 0) == (0.0, 0.0)

    # 0 out of 10: lower is 0.0, upper ~ 0.283
    low_0, high_0 = wilson_score_interval(0, 10, confidence=0.95)
    assert low_0 == 0.0
    assert 0.25 < high_0 < 0.32

    # 10 out of 10: upper is 1.0, lower ~ 0.717
    low_10, high_10 = wilson_score_interval(10, 10, confidence=0.95)
    assert high_10 == 1.0
    assert 0.68 < low_10 < 0.75

    # 9 out of 10: center ~ 0.9, interval contains 0.9, lower ~ 0.596, upper ~ 0.982
    low_9, high_9 = wilson_score_interval(9, 10, confidence=0.95)
    assert 0.55 < low_9 < 0.65
    assert 0.95 < high_9 <= 1.0


def test_percentile_calculations():
    assert calculate_percentile([], 50) is None

    single = [42.0]
    assert calculate_percentile(single, 50) == 42.0
    assert calculate_percentile(single, 95) == 42.0

    # 1 to 100
    data = list(range(1, 101))
    p50 = calculate_percentile(data, 50)
    assert p50 == pytest.approx(50.5)

    p95 = calculate_percentile(data, 95)
    assert p95 == pytest.approx(95.05)


def test_three_class_confusion_matrix():
    m = ThreeClassConfusionMatrix.empty()
    m = m.record("PASS", "PASS")
    m = m.record("FAIL", "FAIL")
    m = m.record("FAIL", "FAIL")
    m = m.record("UNKNOWN", "UNKNOWN")
    m = m.record("FAIL", "PASS")  # 1 mistake

    assert m.total == 5
    assert m.correct == 4
    assert m.accuracy == pytest.approx(4 / 5)
