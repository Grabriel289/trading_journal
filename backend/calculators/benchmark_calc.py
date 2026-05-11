"""Benchmark-relative metrics: alpha, beta, R², tracking error, IR, capture ratios."""

import math
from dataclasses import dataclass
from typing import Optional, Sequence


TRADING_DAYS = 365  # crypto 24/7


@dataclass(frozen=True)
class BenchmarkMetrics:
    alpha: Optional[float]
    beta: Optional[float]
    r_squared: Optional[float]
    tracking_error: Optional[float]
    information_ratio: Optional[float]
    up_capture: Optional[float]
    down_capture: Optional[float]
    capture_ratio: Optional[float]
    portfolio_cumulative: float
    benchmark_cumulative: float
    excess_return: float
    correlation: Optional[float]


def _empty() -> BenchmarkMetrics:
    return BenchmarkMetrics(
        alpha=None, beta=None, r_squared=None,
        tracking_error=None, information_ratio=None,
        up_capture=None, down_capture=None, capture_ratio=None,
        portfolio_cumulative=0.0, benchmark_cumulative=0.0,
        excess_return=0.0, correlation=None,
    )


def calc_benchmark_metrics(
    portfolio_returns: Sequence[float],
    benchmark_returns: Sequence[float],
    risk_free_rate: float = 0.0,
) -> BenchmarkMetrics:
    """Both series must be aligned (same length, same date index)."""
    n = len(portfolio_returns)
    if n != len(benchmark_returns) or n < 30:
        return _empty()

    pr = list(portfolio_returns)
    br = list(benchmark_returns)

    port_growth = 1.0
    bench_growth = 1.0
    for p, b in zip(pr, br):
        port_growth *= (1 + p)
        bench_growth *= (1 + b)
    port_cum = port_growth - 1
    bench_cum = bench_growth - 1

    mean_p = sum(pr) / n
    mean_b = sum(br) / n
    cov = sum((pr[i] - mean_p) * (br[i] - mean_b) for i in range(n)) / (n - 1)
    var_b = sum((br[i] - mean_b) ** 2 for i in range(n)) / (n - 1)

    beta = cov / var_b if var_b > 1e-14 else None
    rf_daily = risk_free_rate / TRADING_DAYS

    alpha = None
    if beta is not None:
        daily_alpha = mean_p - rf_daily - beta * (mean_b - rf_daily)
        alpha = daily_alpha * TRADING_DAYS

    var_p = sum((pr[i] - mean_p) ** 2 for i in range(n)) / (n - 1)
    if var_p > 1e-14 and var_b > 1e-14:
        corr = cov / math.sqrt(var_p * var_b)
        r_squared = corr ** 2
    else:
        corr = None
        r_squared = None

    excess = [pr[i] - br[i] for i in range(n)]
    mean_ex = sum(excess) / n
    te_daily = math.sqrt(sum((e - mean_ex) ** 2 for e in excess) / (n - 1))
    tracking_error = te_daily * math.sqrt(TRADING_DAYS)
    ir = (
        alpha / tracking_error
        if alpha is not None and tracking_error > 1e-10 else None
    )

    up_port = [pr[i] for i in range(n) if br[i] > 0]
    up_bench = [br[i] for i in range(n) if br[i] > 0]
    down_port = [pr[i] for i in range(n) if br[i] < 0]
    down_bench = [br[i] for i in range(n) if br[i] < 0]

    up_capture = (
        (sum(up_port) / sum(up_bench)) * 100
        if up_bench and sum(up_bench) > 1e-14 else None
    )
    down_capture = (
        (sum(down_port) / sum(down_bench)) * 100
        if down_bench and abs(sum(down_bench)) > 1e-14 else None
    )
    capture_ratio = (
        up_capture / down_capture
        if up_capture is not None and down_capture is not None
           and abs(down_capture) > 1e-10
        else None
    )

    return BenchmarkMetrics(
        alpha=alpha,
        beta=beta,
        r_squared=r_squared,
        tracking_error=tracking_error,
        information_ratio=ir,
        up_capture=up_capture,
        down_capture=down_capture,
        capture_ratio=capture_ratio,
        portfolio_cumulative=port_cum,
        benchmark_cumulative=bench_cum,
        excess_return=port_cum - bench_cum,
        correlation=corr,
    )
