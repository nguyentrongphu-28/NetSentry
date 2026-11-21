"""Evaluation metrics module for NetSentry.

Calculates:
- Confusion Matrix (TP, FP, FN, TN)
- Precision, Recall, F1 score with division-by-zero handling
- 3-class (PASS / FAIL / UNKNOWN) confusion matrix and overall accuracy
- Wilson 95% confidence interval for proportions
- Percentiles (p50 / median, p95, min, max, mean)
"""

from dataclasses import dataclass
import math
from typing import Sequence


@dataclass(frozen=True)
class BinaryConfusionMatrix:
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.fn + self.tn

    @property
    def precision(self) -> float | None:
        denom = self.tp + self.fp
        return (self.tp / denom) if denom > 0 else None

    @property
    def recall(self) -> float | None:
        denom = self.tp + self.fn
        return (self.tp / denom) if denom > 0 else None

    @property
    def f1(self) -> float | None:
        p = self.precision
        r = self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * (p * r) / (p + r)

    @property
    def accuracy(self) -> float | None:
        return ((self.tp + self.tn) / self.total) if self.total > 0 else None


def format_rate(value: float | None, as_percentage: bool = True) -> str:
    """Format floating point rate or None as 'n/a'."""
    if value is None:
        return "n/a"
    if as_percentage:
        return f"{value * 100:.1f}%"
    return f"{value:.4f}"


def wilson_score_interval(
    k: int, n: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Calculate the Wilson score confidence interval for a proportion.

    Default confidence is 95% (z = 1.95996).
    Returns (lower_bound, upper_bound) in range [0.0, 1.0].
    """
    if n <= 0:
        return (0.0, 0.0)

    # Standard normal quantile:
    # 0.95 -> ~1.95996, 0.99 -> ~2.57583, 0.90 -> ~1.64485
    if abs(confidence - 0.95) < 1e-4:
        z = 1.959963984540054
    elif abs(confidence - 0.90) < 1e-4:
        z = 1.6448536269514722
    elif abs(confidence - 0.99) < 1e-4:
        z = 2.5758293035489004
    else:
        # Erf inverse approximation if needed
        z = 1.959963984540054

    p = k / n
    z2 = z * z
    denominator = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denominator
    spread = (z * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * (n**2))))) / denominator

    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)
    if k == 0 or lower < 1e-12:
        lower = 0.0
    if k == n or (1.0 - upper) < 1e-12:
        upper = 1.0
    return (lower, upper)


def calculate_percentile(values: Sequence[float], percentile: float) -> float | None:
    """Calculate the given percentile (0 to 100) using linear interpolation."""
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])

    k = (n - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return float(d0 + d1)


@dataclass(frozen=True)
class ThreeClassConfusionMatrix:
    """3x3 confusion matrix for PASS, FAIL, UNKNOWN."""

    # Rows: True label (PASS, FAIL, UNKNOWN)
    # Columns: Predicted label (PASS, FAIL, UNKNOWN)
    matrix: dict[str, dict[str, int]]

    @classmethod
    def empty(cls) -> "ThreeClassConfusionMatrix":
        classes = ("PASS", "FAIL", "UNKNOWN")
        return cls(matrix={t: {p: 0 for p in classes} for t in classes})

    def record(self, true_label: str, pred_label: str) -> "ThreeClassConfusionMatrix":
        t = true_label.upper()
        p = pred_label.upper()
        classes = ("PASS", "FAIL", "UNKNOWN")
        if t not in classes or p not in classes:
            return self
        new_m = {row: dict(cols) for row, cols in self.matrix.items()}
        new_m[t][p] += 1
        return ThreeClassConfusionMatrix(matrix=new_m)

    @property
    def total(self) -> int:
        return sum(sum(cols.values()) for cols in self.matrix.values())

    @property
    def correct(self) -> int:
        return sum(self.matrix[c][c] for c in ("PASS", "FAIL", "UNKNOWN") if c in self.matrix)

    @property
    def accuracy(self) -> float | None:
        return (self.correct / self.total) if self.total > 0 else None
