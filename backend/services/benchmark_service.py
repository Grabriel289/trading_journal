"""Benchmark service — aligns portfolio equity snapshots with BenchmarkPrice and
delegates to benchmark_calc for the math."""

from datetime import date as date_cls
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from backend.calculators.benchmark_calc import BenchmarkMetrics, calc_benchmark_metrics
from backend.calculators.portfolio_calc import calc_daily_returns
from backend.models import BenchmarkPrice, EquitySnapshot, Portfolio


class BenchmarkService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_metrics(
        self,
        portfolio_id: str,
        date_from: Optional[date_cls] = None,
        date_to: Optional[date_cls] = None,
    ) -> BenchmarkMetrics:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError("Portfolio not found")
        if not portfolio.benchmark:
            raise ValueError(
                "No benchmark set. Edit the portfolio and set a benchmark symbol "
                "(e.g. 'BTC') to enable benchmark-relative metrics."
            )

        q = (
            self._db.query(EquitySnapshot)
            .filter(EquitySnapshot.portfolio_id == portfolio_id)
        )
        if date_from:
            q = q.filter(EquitySnapshot.date >= date_from)
        if date_to:
            q = q.filter(EquitySnapshot.date <= date_to)
        snaps = q.order_by(EquitySnapshot.date).all()

        if len(snaps) < 30:
            raise ValueError(
                f"Need at least 30 equity snapshots for benchmark analysis "
                f"(have {len(snaps)}). Take daily snapshots for ≥ 1 month."
            )

        snap_dates = {s.date: Decimal(s.total_equity) for s in snaps}

        bench_q = (
            self._db.query(BenchmarkPrice)
            .filter(
                BenchmarkPrice.symbol == portfolio.benchmark,
                BenchmarkPrice.date.in_(list(snap_dates.keys())),
            )
            .order_by(BenchmarkPrice.date)
        )
        bench_prices = {bp.date: Decimal(bp.close_price) for bp in bench_q.all()}

        aligned_dates = sorted(set(snap_dates.keys()) & set(bench_prices.keys()))
        if len(aligned_dates) < 30:
            raise ValueError(
                f"Only {len(aligned_dates)} overlapping dates between portfolio "
                f"snapshots and benchmark prices. Need ≥ 30. Run the benchmark "
                f"sync job to backfill BenchmarkPrice data."
            )

        port_series = [snap_dates[d] for d in aligned_dates]
        bench_series = [bench_prices[d] for d in aligned_dates]

        port_rets = calc_daily_returns(port_series)
        bench_rets = calc_daily_returns(bench_series)

        return calc_benchmark_metrics(port_rets, bench_rets)
