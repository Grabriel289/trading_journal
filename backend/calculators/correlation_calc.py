"""Pairwise Pearson correlation matrix across labeled return series."""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class CorrelationMatrix:
    labels: List[str]
    matrix: List[List[Optional[float]]]
    high_correlations: List[Tuple[str, str, float]]  # |corr| > 0.7


def calc_correlation_matrix(
    return_series: Dict[str, List[float]],
    min_overlapping: int = 20,
) -> CorrelationMatrix:
    """All series assumed aligned to the same date index (caller's responsibility).
    Caller may pad with 0.0 for days where a label has no return.
    """
    labels = sorted(return_series.keys())
    n = len(labels)
    matrix: List[List[Optional[float]]] = [[None] * n for _ in range(n)]
    high_corrs: List[Tuple[str, str, float]] = []

    for i in range(n):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            x = return_series[labels[i]]
            y = return_series[labels[j]]
            length = min(len(x), len(y))
            if length < min_overlapping:
                continue
            corr = _pearson(x[:length], y[:length])
            matrix[i][j] = corr
            matrix[j][i] = corr
            if corr is not None and abs(corr) > 0.7:
                high_corrs.append((labels[i], labels[j], corr))

    high_corrs.sort(key=lambda x: abs(x[2]), reverse=True)
    return CorrelationMatrix(labels=labels, matrix=matrix, high_correlations=high_corrs)


def _pearson(x: List[float], y: List[float]) -> Optional[float]:
    n = len(x)
    if n < 2:
        return None
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    sx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    sy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if sx < 1e-14 or sy < 1e-14:
        return None
    return cov / (sx * sy)
