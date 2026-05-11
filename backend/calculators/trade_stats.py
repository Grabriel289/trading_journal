import math
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Sequence

from backend.calculators.trade_builder import Trade


@dataclass(frozen=True)
class WinRateResult:
    total: int
    winners: int
    losers: int
    breakeven: int
    win_rate: Optional[Decimal]  # %, None if no trades


@dataclass(frozen=True)
class AvgWinLoss:
    avg_win_dollar: Optional[Decimal]
    avg_loss_dollar: Optional[Decimal]
    avg_win_pct: Optional[Decimal]
    avg_loss_pct: Optional[Decimal]
    expectancy_dollar: Optional[Decimal]


@dataclass(frozen=True)
class BestWorst:
    best_dollar: Optional[Decimal]
    worst_dollar: Optional[Decimal]
    best_at: Optional[str]  # ISO datetime
    worst_at: Optional[str]


@dataclass(frozen=True)
class ConsecutiveStreaks:
    max_consecutive_wins: int
    max_consecutive_losses: int


def _winners(trades: Sequence[Trade]) -> List[Trade]:
    return [t for t in trades if t.pnl_dollar > 0]


def _losers(trades: Sequence[Trade]) -> List[Trade]:
    return [t for t in trades if t.pnl_dollar < 0]


def calc_win_rate(trades: Sequence[Trade]) -> WinRateResult:
    n = len(trades)
    if n == 0:
        return WinRateResult(0, 0, 0, 0, None)
    w = sum(1 for t in trades if t.pnl_dollar > 0)
    l = sum(1 for t in trades if t.pnl_dollar < 0)
    be = n - w - l
    return WinRateResult(
        total=n,
        winners=w,
        losers=l,
        breakeven=be,
        win_rate=(Decimal(w) / Decimal(n) * Decimal("100")),
    )


def calc_profit_factor(trades: Sequence[Trade]) -> Optional[Decimal]:
    gain = sum((t.pnl_dollar for t in trades if t.pnl_dollar > 0), Decimal("0"))
    loss = sum((-t.pnl_dollar for t in trades if t.pnl_dollar < 0), Decimal("0"))
    if loss == 0:
        return None  # undefined when no losses
    return gain / loss


def calc_avg_win_loss(trades: Sequence[Trade]) -> AvgWinLoss:
    winners = _winners(trades)
    losers = _losers(trades)
    n = len(trades)
    avg_w = (sum(t.pnl_dollar for t in winners) / Decimal(len(winners))) if winners else None
    avg_l = (sum(t.pnl_dollar for t in losers) / Decimal(len(losers))) if losers else None
    avg_wp = (sum(t.pnl_percent for t in winners) / Decimal(len(winners))) if winners else None
    avg_lp = (sum(t.pnl_percent for t in losers) / Decimal(len(losers))) if losers else None
    expectancy = (
        (sum(t.pnl_dollar for t in trades) / Decimal(n)) if n > 0 else None
    )
    return AvgWinLoss(
        avg_win_dollar=avg_w,
        avg_loss_dollar=avg_l,
        avg_win_pct=avg_wp,
        avg_loss_pct=avg_lp,
        expectancy_dollar=expectancy,
    )


def calc_best_worst(trades: Sequence[Trade]) -> BestWorst:
    if not trades:
        return BestWorst(None, None, None, None)
    best = max(trades, key=lambda t: t.pnl_dollar)
    worst = min(trades, key=lambda t: t.pnl_dollar)
    return BestWorst(
        best_dollar=best.pnl_dollar,
        worst_dollar=worst.pnl_dollar,
        best_at=best.exit_datetime.isoformat(),
        worst_at=worst.exit_datetime.isoformat(),
    )


def calc_std_deviation(trades: Sequence[Trade]) -> Optional[Decimal]:
    n = len(trades)
    if n < 2:
        return None
    mean = sum(t.pnl_dollar for t in trades) / Decimal(n)
    var = sum((t.pnl_dollar - mean) ** 2 for t in trades) / Decimal(n - 1)
    # Decimal lacks sqrt; switch to float for sqrt then back.
    return Decimal(str(math.sqrt(float(var))))


def _ordered_outcomes(trades: Sequence[Trade]) -> List[int]:
    """1 for win, -1 for loss, 0 for breakeven, in chronological order."""
    chrono = sorted(trades, key=lambda t: t.exit_datetime)
    out = []
    for t in chrono:
        if t.pnl_dollar > 0:
            out.append(1)
        elif t.pnl_dollar < 0:
            out.append(-1)
        else:
            out.append(0)
    return out


def calc_consecutive_streaks(trades: Sequence[Trade]) -> ConsecutiveStreaks:
    outs = _ordered_outcomes(trades)
    max_w = max_l = cur_w = cur_l = 0
    for o in outs:
        if o > 0:
            cur_w += 1; cur_l = 0
            if cur_w > max_w: max_w = cur_w
        elif o < 0:
            cur_l += 1; cur_w = 0
            if cur_l > max_l: max_l = cur_l
        else:
            cur_w = cur_l = 0
    return ConsecutiveStreaks(max_consecutive_wins=max_w, max_consecutive_losses=max_l)


def calc_z_score(trades: Sequence[Trade]) -> tuple[Optional[float], Optional[float]]:
    """Wald-Wolfowitz runs test on win/loss sequence.

    Returns (z, two-sided probability that the streak pattern is non-random).
    Breakeven trades are excluded.
    """
    seq = [o for o in _ordered_outcomes(trades) if o != 0]
    n = len(seq)
    if n < 2:
        return (None, None)
    w = sum(1 for x in seq if x > 0)
    l = n - w
    if w == 0 or l == 0:
        return (None, None)
    runs = 1
    for i in range(1, n):
        if seq[i] != seq[i - 1]:
            runs += 1
    x = 2.0 * w * l
    denom_sq = (x * (x - n)) / (n - 1)
    if denom_sq <= 0:
        return (None, None)
    z = (n * (runs - 0.5) - x) / math.sqrt(denom_sq)
    prob = math.erf(abs(z) / math.sqrt(2.0))  # 2*Φ(|z|) - 1
    return (z, prob)


def calc_ahpr_ghpr(trades: Sequence[Trade]) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Per-trade hold period returns. HPR_i = 1 + pct_i/100."""
    if not trades:
        return (None, None)
    hprs = [Decimal("1") + (t.pnl_percent / Decimal("100")) for t in trades]
    n = len(hprs)
    ahpr = sum(hprs, Decimal("0")) / Decimal(n)
    # Geometric mean — guard against any non-positive HPR (would indicate -100% loss).
    if any(h <= 0 for h in hprs):
        return (ahpr, None)
    log_sum = sum(math.log(float(h)) for h in hprs)
    ghpr = Decimal(str(math.exp(log_sum / n)))
    return (ahpr, ghpr)


def calc_recovery_factor(
    total_net_profit: Decimal, max_drawdown_dollar: Decimal
) -> Optional[Decimal]:
    if max_drawdown_dollar <= 0:
        return None
    return total_net_profit / max_drawdown_dollar
