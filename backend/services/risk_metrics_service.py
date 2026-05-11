"""Risk metrics — static numbers + rolling 30d Sharpe & volatility series."""

import math
from dataclasses import dataclass
from datetime import date as date_cls
from decimal import Decimal
from typing import List, Optional

import numpy as np
from scipy import stats as scipy_stats
from sqlalchemy.orm import Session

from backend.calculators.portfolio_calc import (
    calc_annual_return,
    calc_calmar,
    calc_daily_returns,
    calc_drawdown,
    calc_sharpe,
    calc_sortino,
)
from backend.models import EquitySnapshot, Portfolio


TRADING_DAYS = 365
ROLLING_WINDOW = 30


@dataclass
class StaticRiskMetrics:
    sharpe: Optional[float]
    sortino: Optional[float]
    calmar: Optional[float]
    max_drawdown_pct: Optional[float]
    var_95: Optional[float]
    var_99: Optional[float]
    annualized_return: Optional[float]
    annualized_volatility: Optional[float]
    downside_deviation: Optional[float]
    skewness: Optional[float]
    kurtosis: Optional[float]
    best_day_pct: Optional[float]
    worst_day_pct: Optional[float]


@dataclass
class RollingPoint:
    date: date_cls
    value: float


@dataclass
class RiskMetrics:
    static: StaticRiskMetrics
    rolling_sharpe_30d: List[RollingPoint]
    rolling_volatility_30d: List[RollingPoint]
    sample_size: int


class RiskMetricsService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_metrics(self, portfolio_id: str) -> RiskMetrics:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        snaps = (
            self._db.query(EquitySnapshot)
            .filter(EquitySnapshot.portfolio_id == portfolio_id)
            .order_by(EquitySnapshot.date)
            .all()
        )

        if len(snaps) < 2:
            empty = StaticRiskMetrics(
                sharpe=None, sortino=None, calmar=None, max_drawdown_pct=None,
                var_95=None, var_99=None, annualized_return=None,
                annualized_volatility=None, downside_deviation=None,
                skewness=None, kurtosis=None, best_day_pct=None, worst_day_pct=None,
            )
            return RiskMetrics(static=empty, rolling_sharpe_30d=[], rolling_volatility_30d=[], sample_size=len(snaps))

        equity = [Decimal(s.total_equity) for s in snaps]
        dates = [s.date for s in snaps]
        daily_rets = calc_daily_returns(equity)
        n = len(daily_rets)

        # Static: reuse existing calculators where possible
        sharpe = calc_sharpe(daily_rets)
        sortino = calc_sortino(daily_rets)
        dd = calc_drawdown(snaps)
        ann_ret = calc_annual_return(daily_rets)
        calmar = (
            calc_calmar(ann_ret, float(dd.max_dd_pct))
            if ann_ret is not None else None
        )

        arr = np.asarray(daily_rets, dtype=float)
        ann_vol = (
            float(np.std(arr, ddof=1) * math.sqrt(TRADING_DAYS) * 100)
            if n >= 2 else None
        )
        downside = arr[arr < 0]
        down_dev = (
            float(np.std(downside, ddof=1) * math.sqrt(TRADING_DAYS) * 100)
            if len(downside) >= 2 else None
        )
        skew = float(scipy_stats.skew(arr)) if n >= 3 else None
        # Excess kurtosis (Fisher's definition: normal = 0)
        kurt = float(scipy_stats.kurtosis(arr, fisher=True)) if n >= 4 else None
        best_day = float(np.max(arr) * 100) if n > 0 else None
        worst_day = float(np.min(arr) * 100) if n > 0 else None

        var_95 = float(np.percentile(arr, 5) * 100) if n >= 30 else None
        var_99 = float(np.percentile(arr, 1) * 100) if n >= 30 else None

        static = StaticRiskMetrics(
            sharpe=sharpe,
            sortino=sortino,
            calmar=calmar,
            max_drawdown_pct=-float(dd.max_dd_pct) if dd.max_dd_pct else 0.0,
            var_95=var_95,
            var_99=var_99,
            annualized_return=ann_ret * 100 if ann_ret is not None else None,
            annualized_volatility=ann_vol,
            downside_deviation=down_dev,
            skewness=skew,
            kurtosis=kurt,
            best_day_pct=best_day,
            worst_day_pct=worst_day,
        )

        # Rolling 30d: daily_rets[i] corresponds to dates[i+1]
        # because returns start at day 2 of the snapshot series.
        rolling_sharpe: List[RollingPoint] = []
        rolling_vol: List[RollingPoint] = []
        if n >= ROLLING_WINDOW:
            for i in range(ROLLING_WINDOW - 1, n):
                window = arr[i - ROLLING_WINDOW + 1: i + 1]
                w_mean = float(np.mean(window))
                w_std = float(np.std(window, ddof=1)) if len(window) >= 2 else 0.0
                rs = (w_mean / w_std) * math.sqrt(TRADING_DAYS) if w_std > 0 else 0.0
                rv = w_std * math.sqrt(TRADING_DAYS) * 100
                d = dates[i + 1]  # +1: returns index → snapshot index
                rolling_sharpe.append(RollingPoint(date=d, value=round(rs, 4)))
                rolling_vol.append(RollingPoint(date=d, value=round(rv, 4)))

        return RiskMetrics(
            static=static,
            rolling_sharpe_30d=rolling_sharpe,
            rolling_volatility_30d=rolling_vol,
            sample_size=len(snaps),
        )
