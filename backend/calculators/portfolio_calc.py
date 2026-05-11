import math
from dataclasses import dataclass
from datetime import date as date_cls
from decimal import Decimal
from typing import List, Optional, Sequence


TRADING_DAYS_PER_YEAR = 365  # crypto is 24/7


@dataclass(frozen=True)
class DrawdownResult:
    current_dd_pct: Decimal
    max_dd_pct: Decimal
    max_dd_dollar: Decimal
    peak_equity: Decimal
    max_dd_date: Optional[date_cls]
    max_dd_duration_days: int  # span from prior peak to trough


def calc_daily_returns(equity_series: Sequence[Decimal]) -> List[float]:
    """daily_return[i] = (equity[i] - equity[i-1]) / equity[i-1] for i >= 1."""
    out: List[float] = []
    for i in range(1, len(equity_series)):
        prev = equity_series[i - 1]
        if prev > 0:
            out.append(float((equity_series[i] - prev) / prev))
        else:
            out.append(0.0)
    return out


def calc_drawdown(snapshots: Sequence) -> DrawdownResult:
    """`snapshots` is a chronological iterable with .total_equity and .date attributes."""
    if not snapshots:
        return DrawdownResult(
            current_dd_pct=Decimal("0"),
            max_dd_pct=Decimal("0"),
            max_dd_dollar=Decimal("0"),
            peak_equity=Decimal("0"),
            max_dd_date=None,
            max_dd_duration_days=0,
        )

    peak = Decimal("0")
    peak_date: Optional[date_cls] = None
    max_dd_pct = Decimal("0")
    max_dd_dollar = Decimal("0")
    max_dd_date: Optional[date_cls] = None
    max_dd_peak_date: Optional[date_cls] = None

    for s in snapshots:
        eq = Decimal(s.total_equity)
        if eq > peak:
            peak = eq
            peak_date = s.date
        if peak > 0:
            dd_pct = (peak - eq) / peak * Decimal("100")
            dd_dollar = peak - eq
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd_dollar = dd_dollar
                max_dd_date = s.date
                max_dd_peak_date = peak_date

    last = snapshots[-1]
    last_eq = Decimal(last.total_equity)
    current_dd = (
        ((peak - last_eq) / peak * Decimal("100")) if peak > 0 else Decimal("0")
    )
    duration = 0
    if max_dd_peak_date and max_dd_date:
        duration = (max_dd_date - max_dd_peak_date).days
    return DrawdownResult(
        current_dd_pct=current_dd,
        max_dd_pct=max_dd_pct,
        max_dd_dollar=max_dd_dollar,
        peak_equity=peak,
        max_dd_date=max_dd_date,
        max_dd_duration_days=duration,
    )


def _stdev(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(var)


def calc_sharpe(
    daily_returns: Sequence[float], risk_free_rate: float = 0.0
) -> Optional[float]:
    """Annualized Sharpe ratio. risk_free_rate is annual; converted to daily."""
    if len(daily_returns) < 2:
        return None
    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = [r - rf_daily for r in daily_returns]
    sd = _stdev(excess)
    if sd == 0:
        return None
    mean_excess = sum(excess) / len(excess)
    return (mean_excess / sd) * math.sqrt(TRADING_DAYS_PER_YEAR)


def calc_sortino(
    daily_returns: Sequence[float], target_rate: float = 0.0
) -> Optional[float]:
    """Annualized Sortino ratio. Target is annual rate (default 0)."""
    if len(daily_returns) < 2:
        return None
    target_daily = target_rate / TRADING_DAYS_PER_YEAR
    downside = [min(r - target_daily, 0.0) for r in daily_returns]
    n = len(downside)
    downside_dev = math.sqrt(sum(d * d for d in downside) / n)
    if downside_dev == 0:
        return None
    mean_excess = sum(r - target_daily for r in daily_returns) / n
    return (mean_excess / downside_dev) * math.sqrt(TRADING_DAYS_PER_YEAR)


def calc_calmar(annual_return: float, max_drawdown_pct: float) -> Optional[float]:
    if max_drawdown_pct <= 0:
        return None
    return annual_return / (max_drawdown_pct / 100.0)


def calc_annual_return(daily_returns: Sequence[float]) -> Optional[float]:
    """Geometric annualized return from per-day returns."""
    if not daily_returns:
        return None
    growth = 1.0
    for r in daily_returns:
        growth *= 1.0 + r
    if growth <= 0:
        return -1.0
    return growth ** (TRADING_DAYS_PER_YEAR / len(daily_returns)) - 1.0
