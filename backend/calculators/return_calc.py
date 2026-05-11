"""Time-Weighted Return (TWR) and Money-Weighted Return (MWR).

TWR isolates investment performance from cash flow timing — the GIPS-compliant
standard for institutional reporting. MWR (IRR) measures investor experience
including cash flow timing.
"""

from dataclasses import dataclass
from datetime import date as date_cls
from decimal import Decimal
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class SubPeriodReturn:
    start_date: date_cls
    end_date: date_cls
    bmv: Decimal
    emv: Decimal
    cash_flow: Decimal
    sub_return: float


@dataclass(frozen=True)
class TWRResult:
    cumulative_twr: float
    annualized_twr: Optional[float]
    sub_periods: List[SubPeriodReturn]
    total_days: int


@dataclass(frozen=True)
class CashFlowEvent:
    date: date_cls
    amount: Decimal  # positive = deposit, negative = withdrawal


def calc_twr(
    equity_series: Sequence[Tuple[date_cls, Decimal]],
    cash_flows: Sequence[CashFlowEvent],
) -> TWRResult:
    """TWR chains sub-period returns across each cash-flow boundary.

    Sub-period return R_i = (EMV_i - BMV_i - CF_i) / BMV_i
    TWR = ∏(1 + R_i) - 1
    """
    if len(equity_series) < 2:
        return TWRResult(
            cumulative_twr=0.0, annualized_twr=None,
            sub_periods=[], total_days=0,
        )

    eq_by_date = {d: float(e) for d, e in equity_series}
    all_dates = sorted(eq_by_date.keys())

    cf_by_date: dict = {}
    for cf in cash_flows:
        cf_by_date[cf.date] = cf_by_date.get(cf.date, 0.0) + float(cf.amount)

    # Sub-period boundaries: first equity date, every CF date inside the range, last date.
    boundary_set = {all_dates[0], all_dates[-1]}
    for d in cf_by_date.keys():
        if all_dates[0] <= d <= all_dates[-1]:
            boundary_set.add(d)
    boundary_dates = sorted(boundary_set)

    sub_periods: List[SubPeriodReturn] = []
    for i in range(len(boundary_dates) - 1):
        start = boundary_dates[i]
        end = boundary_dates[i + 1]

        bmv = _nearest_equity(eq_by_date, start, all_dates)
        emv = _nearest_equity(eq_by_date, end, all_dates)
        cf = cf_by_date.get(end, 0.0)

        r = (emv - bmv - cf) / bmv if bmv > 0 else 0.0

        sub_periods.append(SubPeriodReturn(
            start_date=start,
            end_date=end,
            bmv=Decimal(str(bmv)),
            emv=Decimal(str(emv)),
            cash_flow=Decimal(str(cf)),
            sub_return=r,
        ))

    growth = 1.0
    for sp in sub_periods:
        growth *= (1.0 + sp.sub_return)
    cumulative = growth - 1.0

    total_days = (all_dates[-1] - all_dates[0]).days
    annualized = None
    if total_days > 365 and growth > 0:
        annualized = growth ** (365.0 / total_days) - 1.0

    return TWRResult(
        cumulative_twr=cumulative,
        annualized_twr=annualized,
        sub_periods=sub_periods,
        total_days=total_days,
    )


def _nearest_equity(eq_by_date: dict, target: date_cls, all_dates: list) -> float:
    if target in eq_by_date:
        return eq_by_date[target]
    for d in reversed(all_dates):
        if d <= target and d in eq_by_date:
            return eq_by_date[d]
    return 0.0


def calc_mwr(
    equity_series: Sequence[Tuple[date_cls, Decimal]],
    cash_flows: Sequence[CashFlowEvent],
) -> Optional[float]:
    """Money-Weighted Return (annualized IRR).

    Solves Σ flow_i × (1+r)^(-day_i) = 0 with Newton-Raphson on the daily rate,
    then annualizes.
    """
    if len(equity_series) < 2:
        return None

    first_date, first_eq = equity_series[0]
    last_date, last_eq = equity_series[-1]
    total_days = (last_date - first_date).days
    if total_days <= 0:
        return None

    flows: List[Tuple[int, float]] = [(0, -float(first_eq))]
    for cf in cash_flows:
        day_offset = (cf.date - first_date).days
        if 0 < day_offset < total_days:
            flows.append((day_offset, -float(cf.amount)))
    flows.append((total_days, float(last_eq)))

    r = 0.0001
    for _ in range(200):
        npv = sum(f * (1 + r) ** (-d) for d, f in flows)
        dnpv = sum(-d * f * (1 + r) ** (-d - 1) for d, f in flows)
        if abs(dnpv) < 1e-14:
            break
        r_new = r - npv / dnpv
        if abs(r_new - r) < 1e-12:
            r = r_new
            break
        r = r_new

    try:
        return (1 + r) ** 365 - 1
    except (OverflowError, ValueError):
        return None
