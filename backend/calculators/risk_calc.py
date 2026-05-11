import math
from dataclasses import dataclass
from datetime import date as date_cls
from decimal import Decimal
from typing import List, Optional, Sequence, Tuple

import numpy as np

from backend.models.enums import Direction


@dataclass(frozen=True)
class RoRLevel:
    loss_pct: float                     # 0..100
    consecutive_losses: Optional[int]    # None when unbounded / undefined
    probability: Optional[float]         # 0..1, None when undefined


DEFAULT_LOSS_LEVELS = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]


def calc_risk_of_ruin(
    win_rate: float,
    avg_loss_pct: float,
    loss_levels: Sequence[float] = DEFAULT_LOSS_LEVELS,
) -> List[RoRLevel]:
    """Probability of an N-loss streak large enough to lose `loss_level` of capital.

    Each loss removes `avg_loss_pct` (a fraction, 0..1) of remaining capital.
    Geometric drawdown: capital × (1 − avg_loss_pct)^N = capital × (1 − L).
    Probability of N consecutive losing trades = (1 − win_rate)^N.
    """
    out: List[RoRLevel] = []
    has_loss = avg_loss_pct > 0
    loss_prob = max(0.0, min(1.0, 1.0 - win_rate))

    for L in loss_levels:
        L_pct = float(L) * 100.0

        # 100% loss with %-based per-trade loss is geometrically unreachable.
        if L >= 1.0:
            out.append(RoRLevel(loss_pct=L_pct, consecutive_losses=None, probability=None))
            continue
        if not has_loss:
            out.append(RoRLevel(loss_pct=L_pct, consecutive_losses=None, probability=None))
            continue

        consec = math.ceil(math.log(1.0 - L) / math.log(1.0 - avg_loss_pct))
        if consec < 1:
            consec = 1
        prob = loss_prob ** consec
        out.append(RoRLevel(loss_pct=L_pct, consecutive_losses=int(consec), probability=prob))
    return out


def calc_mae(
    entry_price: Decimal,
    price_history: Sequence[Decimal],
    direction: Direction = Direction.LONG,
) -> Decimal:
    """Maximum Adverse Excursion in price terms (per unit). Returns a non-positive number."""
    if not price_history:
        return Decimal("0")
    if direction == Direction.LONG:
        return min(price_history) - entry_price
    return entry_price - max(price_history)


def calc_mfe(
    entry_price: Decimal,
    price_history: Sequence[Decimal],
    direction: Direction = Direction.LONG,
) -> Decimal:
    """Maximum Favorable Excursion in price terms (per unit). Returns a non-negative number."""
    if not price_history:
        return Decimal("0")
    if direction == Direction.LONG:
        return max(price_history) - entry_price
    return entry_price - min(price_history)


def excursion_pct(excursion: Decimal, entry_price: Decimal) -> Decimal:
    if entry_price <= 0:
        return Decimal("0")
    return excursion / entry_price * Decimal("100")


# ── Phase 3 risk metrics ─────────────────────────────────────────────


def calc_var_cvar(
    daily_returns: Sequence[float],
    confidence: float = 0.95,
) -> Tuple[Optional[float], Optional[float]]:
    """Historical VaR & CVaR (Expected Shortfall) as percentages.

    Returns (var_pct, cvar_pct) — both typically negative (losses).
    """
    if len(daily_returns) < 30:
        return (None, None)

    arr = np.asarray(daily_returns, dtype=float)
    percentile = (1.0 - confidence) * 100.0
    var = float(np.percentile(arr, percentile))
    tail = arr[arr <= var]
    cvar = float(np.mean(tail)) if tail.size > 0 else var
    return (var * 100.0, cvar * 100.0)


def calc_parametric_var(
    daily_returns: Sequence[float],
    confidence: float = 0.95,
    holding_period_days: int = 1,
) -> Optional[float]:
    """Parametric (Gaussian) VaR. Useful as a fat-tail check vs historical VaR."""
    if len(daily_returns) < 30:
        return None
    from scipy.stats import norm  # lazy import — scipy is heavy

    arr = np.asarray(daily_returns, dtype=float)
    mu = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))
    z = float(norm.ppf(1.0 - confidence))
    var = -(mu + z * sigma * math.sqrt(holding_period_days))
    return var * 100.0


def calc_tail_ratio(daily_returns: Sequence[float]) -> Optional[float]:
    """|p95| / |p5|. >1 means right tail (gains) dominates left tail."""
    if len(daily_returns) < 20:
        return None
    arr = np.asarray(daily_returns, dtype=float)
    p95 = float(np.percentile(arr, 95))
    p5 = float(np.percentile(arr, 5))
    if abs(p5) < 1e-10:
        return None
    return abs(p95) / abs(p5)


def calc_max_dd_duration(
    equity_series: Sequence[Decimal],
    dates: Sequence[date_cls],
) -> Tuple[int, Optional[Tuple[date_cls, Optional[date_cls]]]]:
    """Longest peak-to-recovery stretch in calendar days.

    Returns (max_duration_days, (peak_date, recovery_date or None)).
    If the portfolio hasn't recovered by the last snapshot, recovery_date is None.
    """
    if len(equity_series) < 2:
        return (0, None)

    peak = Decimal("0")
    peak_idx = 0
    max_duration = 0
    max_peak_idx = 0
    max_trough_idx = 0
    recovered = True

    for i, eq in enumerate(equity_series):
        if eq >= peak:
            if i > peak_idx:
                duration = (dates[i] - dates[peak_idx]).days
                if duration > max_duration:
                    max_duration = duration
                    max_peak_idx = peak_idx
                    max_trough_idx = i
                    recovered = True
            peak = eq
            peak_idx = i

    # Tail check: still in drawdown at end of series.
    current_dd_days = (dates[-1] - dates[peak_idx]).days
    if (
        current_dd_days > max_duration
        and Decimal(equity_series[-1]) < peak
    ):
        max_duration = current_dd_days
        max_peak_idx = peak_idx
        max_trough_idx = len(dates) - 1
        recovered = False

    if max_duration == 0:
        return (0, None)

    peak_date = dates[max_peak_idx]
    recovery = dates[max_trough_idx] if recovered else None
    return (max_duration, (peak_date, recovery))
