import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import date as date_cls, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.calculators.portfolio_calc import (
    DrawdownResult,
    calc_annual_return,
    calc_calmar,
    calc_daily_returns,
    calc_drawdown,
    calc_sharpe,
    calc_sortino,
)
from backend.calculators.return_calc import (
    CashFlowEvent,
    calc_mwr,
    calc_twr,
)
from backend.calculators.risk_calc import (
    DEFAULT_LOSS_LEVELS,
    RoRLevel,
    calc_mae,
    calc_max_dd_duration,
    calc_mfe,
    calc_parametric_var,
    calc_risk_of_ruin,
    calc_tail_ratio,
    calc_var_cvar,
    excursion_pct,
)
from backend.calculators.trade_builder import Trade, build_trades
from backend.calculators.trade_stats import (
    AvgWinLoss,
    BestWorst,
    ConsecutiveStreaks,
    WinRateResult,
    calc_ahpr_ghpr,
    calc_avg_win_loss,
    calc_best_worst,
    calc_consecutive_streaks,
    calc_profit_factor,
    calc_recovery_factor,
    calc_std_deviation,
    calc_win_rate,
    calc_z_score,
)
from backend.models import Deposit, EquitySnapshot, Order, Portfolio
from backend.models.enums import Direction, DepositType
from backend.services.price_service import PriceService


@dataclass
class StatsFilter:
    portfolio_id: str
    sub_account_id: Optional[str] = None
    date_from: Optional[date_cls] = None
    date_to: Optional[date_cls] = None


@dataclass
class SummaryStats:
    win_rate: WinRateResult
    long_win_rate: WinRateResult
    short_win_rate: WinRateResult
    profit_factor: Optional[Decimal]
    avg_win_loss: AvgWinLoss
    best_worst: BestWorst
    streaks: ConsecutiveStreaks
    std_deviation: Optional[Decimal]
    z_score: Optional[float]
    z_score_probability: Optional[float]
    ahpr: Optional[Decimal]
    ghpr: Optional[Decimal]
    recovery_factor: Optional[Decimal]
    total_net_profit: Decimal
    drawdown: DrawdownResult
    sharpe: Optional[float]
    sortino: Optional[float]
    calmar: Optional[float]
    annual_return: Optional[float]
    # Phase 3
    cumulative_twr: Optional[float] = None
    annualized_twr: Optional[float] = None
    mwr: Optional[float] = None
    var_95: Optional[float] = None
    cvar_95: Optional[float] = None
    parametric_var_95: Optional[float] = None
    tail_ratio: Optional[float] = None
    # Peak→recovery duration. Distinct from DrawdownResult.max_dd_duration_days
    # which measures peak→trough.
    max_dd_recovery_days: int = 0


@dataclass
class AssetBreakdown:
    asset: str
    longs_count: int
    longs_pnl: Decimal
    longs_win_rate: Optional[Decimal]
    shorts_count: int
    shorts_pnl: Decimal
    shorts_win_rate: Optional[Decimal]
    total_count: int
    total_pnl: Decimal
    total_win_rate: Optional[Decimal]


@dataclass
class HourlyBucket:
    hour: int  # 0..23
    count: int
    profit: Decimal


@dataclass
class DailyBucket:
    weekday: int  # 0=Mon ... 6=Sun
    name: str
    winners: int
    losers: int
    profit: Decimal


@dataclass
class DurationPoint:
    asset: str
    duration_seconds: int
    pnl_dollar: Decimal
    pnl_percent: Decimal
    direction: Optional[str] = None
    exit_datetime: Optional[str] = None


@dataclass
class DurationStats:
    points: List[DurationPoint]
    avg_seconds: Optional[float]
    median_seconds: Optional[float]
    longest_seconds: Optional[int]
    shortest_seconds: Optional[int]
    avg_winner_seconds: Optional[float]
    avg_loser_seconds: Optional[float]


@dataclass
class ExcursionPoint:
    asset: str
    direction: Optional[str]
    entry_price: Decimal
    exit_price: Decimal
    pnl_pct: Decimal
    mae_pct: Decimal  # ≤ 0 (worst against you)
    mfe_pct: Decimal  # ≥ 0 (best for you)
    exit_datetime: Optional[str] = None


@dataclass
class MaeMfeData:
    points: List[ExcursionPoint]
    avg_mae_pct: Optional[Decimal]
    avg_mfe_pct: Optional[Decimal]
    skipped: int  # trades for which klines could not be fetched


class StatsService:
    def __init__(self, db: Session, price_service: Optional[PriceService] = None) -> None:
        self._db = db
        self._prices = price_service

    def _trades(self, f: StatsFilter) -> List[Trade]:
        portfolio = self._db.get(Portfolio, f.portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {f.portfolio_id} not found")
        sub_ids = [s.id for s in portfolio.sub_accounts]
        sub_by_id = {s.id: s for s in portfolio.sub_accounts}
        if not sub_ids:
            return []
        q = self._db.query(Order).filter(Order.sub_account_id.in_(sub_ids))
        orders = q.order_by(Order.datetime).all()
        trades = build_trades(orders, sub_account_lookup=sub_by_id.get)

        out = []
        for t in trades:
            if f.sub_account_id and t.sub_account_id != f.sub_account_id:
                continue
            if f.date_from and t.exit_datetime.date() < f.date_from:
                continue
            if f.date_to and t.exit_datetime.date() > f.date_to:
                continue
            out.append(t)
        return out

    def _snapshots(self, f: StatsFilter) -> List[EquitySnapshot]:
        q = (
            self._db.query(EquitySnapshot)
            .filter(EquitySnapshot.portfolio_id == f.portfolio_id)
        )
        if f.date_from:
            q = q.filter(EquitySnapshot.date >= f.date_from)
        if f.date_to:
            q = q.filter(EquitySnapshot.date <= f.date_to)
        return q.order_by(EquitySnapshot.date).all()

    def get_summary(self, f: StatsFilter) -> SummaryStats:
        trades = self._trades(f)
        longs = [t for t in trades if t.direction is None or t.direction.value == "LONG"]
        shorts = [t for t in trades if t.direction is not None and t.direction.value == "SHORT"]

        wr = calc_win_rate(trades)
        long_wr = calc_win_rate(longs)
        short_wr = calc_win_rate(shorts)
        pf = calc_profit_factor(trades)
        awl = calc_avg_win_loss(trades)
        bw = calc_best_worst(trades)
        streaks = calc_consecutive_streaks(trades)
        std = calc_std_deviation(trades)
        z, z_prob = calc_z_score(trades)
        ahpr, ghpr = calc_ahpr_ghpr(trades)
        total_net = sum((t.pnl_dollar for t in trades), Decimal("0"))

        # Snapshot-based ratios are only meaningful at the portfolio level.
        cumulative_twr = annualized_twr = mwr_val = None
        var_95 = cvar_95 = parametric_var = tail_r = None
        dd_dur = 0
        if f.sub_account_id is None:
            snaps = self._snapshots(f)
            dd = calc_drawdown(snaps)
            equity_series = [Decimal(s.total_equity) for s in snaps]
            daily_rets = calc_daily_returns(equity_series)
            sharpe = calc_sharpe(daily_rets)
            sortino = calc_sortino(daily_rets)

            # TWR / MWR — replace geometric annual return with cash-flow-adjusted TWR
            equity_ts = [(s.date, Decimal(s.total_equity)) for s in snaps]
            cf_events = self._cash_flow_events(f.portfolio_id)
            twr = calc_twr(equity_ts, cf_events)
            cumulative_twr = twr.cumulative_twr
            annualized_twr = twr.annualized_twr
            mwr_val = calc_mwr(equity_ts, cf_events) if len(snaps) >= 2 else None

            # Prefer TWR for annualized return when available
            ann = annualized_twr if annualized_twr is not None else calc_annual_return(daily_rets)
            calmar = (
                calc_calmar(ann, float(dd.max_dd_pct))
                if ann is not None else None
            )

            # Risk metrics — VaR/CVaR/tail/max-DD-duration
            var_95, cvar_95 = calc_var_cvar(daily_rets, confidence=0.95)
            parametric_var = calc_parametric_var(daily_rets, confidence=0.95)
            tail_r = calc_tail_ratio(daily_rets)
            snap_dates = [s.date for s in snaps]
            dd_dur, _ = calc_max_dd_duration(equity_series, snap_dates)
        else:
            dd = calc_drawdown([])
            sharpe = sortino = calmar = ann = None

        recovery = calc_recovery_factor(total_net, dd.max_dd_dollar)

        return SummaryStats(
            win_rate=wr,
            long_win_rate=long_wr,
            short_win_rate=short_wr,
            profit_factor=pf,
            avg_win_loss=awl,
            best_worst=bw,
            streaks=streaks,
            std_deviation=std,
            z_score=z,
            z_score_probability=z_prob,
            ahpr=ahpr,
            ghpr=ghpr,
            recovery_factor=recovery,
            total_net_profit=total_net,
            drawdown=dd,
            sharpe=sharpe,
            sortino=sortino,
            calmar=calmar,
            annual_return=ann,
            cumulative_twr=cumulative_twr,
            annualized_twr=annualized_twr,
            mwr=mwr_val,
            var_95=var_95,
            cvar_95=cvar_95,
            parametric_var_95=parametric_var,
            tail_ratio=tail_r,
            max_dd_recovery_days=dd_dur,
        )

    def get_asset_correlations(self, f: StatsFilter) -> dict:
        """Pairwise asset correlation based on per-asset daily P&L percent series."""
        from collections import defaultdict
        from typing import Dict

        from backend.calculators.correlation_calc import calc_correlation_matrix

        trades = self._trades(f)
        if not trades:
            return {"labels": [], "matrix": [], "high_correlations": []}

        all_dates = sorted({t.exit_datetime.date() for t in trades})
        date_to_idx = {d: i for i, d in enumerate(all_dates)}
        n_dates = len(all_dates)

        by_asset: Dict[str, List[float]] = {}
        for t in trades:
            by_asset.setdefault(t.asset, [0.0] * n_dates)
            by_asset[t.asset][date_to_idx[t.exit_datetime.date()]] += float(t.pnl_percent)

        # Need ≥ 5 non-zero data points per asset to be meaningful
        filtered = {
            asset: rets for asset, rets in by_asset.items()
            if sum(1 for r in rets if r != 0.0) >= 5
        }
        if not filtered:
            return {"labels": [], "matrix": [], "high_correlations": []}

        result = calc_correlation_matrix(filtered)
        return {
            "labels": result.labels,
            "matrix": result.matrix,
            "high_correlations": [
                {"asset_a": a, "asset_b": b, "correlation": c}
                for a, b, c in result.high_correlations
            ],
        }

    def _cash_flow_events(self, portfolio_id: str) -> List[CashFlowEvent]:
        """Build TWR-style cash flow vector from Deposit rows for the portfolio."""
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            return []
        sub_ids = [s.id for s in portfolio.sub_accounts]
        if not sub_ids:
            return []
        deposits = (
            self._db.query(Deposit)
            .filter(Deposit.sub_account_id.in_(sub_ids))
            .order_by(Deposit.datetime)
            .all()
        )
        return [
            CashFlowEvent(
                date=d.datetime.date(),
                amount=(
                    Decimal(d.amount)
                    if d.type == DepositType.DEPOSIT
                    else -Decimal(d.amount)
                ),
            )
            for d in deposits
        ]

    def get_trades_breakdown(self, f: StatsFilter) -> List[AssetBreakdown]:
        trades = self._trades(f)
        by_asset = defaultdict(list)
        for t in trades:
            by_asset[t.asset].append(t)

        out: List[AssetBreakdown] = []
        for asset in sorted(by_asset):
            rows = by_asset[asset]
            longs = [t for t in rows if t.direction is None or t.direction.value == "LONG"]
            shorts = [t for t in rows if t.direction is not None and t.direction.value == "SHORT"]
            out.append(AssetBreakdown(
                asset=asset,
                longs_count=len(longs),
                longs_pnl=sum((t.pnl_dollar for t in longs), Decimal("0")),
                longs_win_rate=calc_win_rate(longs).win_rate,
                shorts_count=len(shorts),
                shorts_pnl=sum((t.pnl_dollar for t in shorts), Decimal("0")),
                shorts_win_rate=calc_win_rate(shorts).win_rate,
                total_count=len(rows),
                total_pnl=sum((t.pnl_dollar for t in rows), Decimal("0")),
                total_win_rate=calc_win_rate(rows).win_rate,
            ))
        return out

    def get_hourly(self, f: StatsFilter) -> List[HourlyBucket]:
        trades = self._trades(f)
        bucket = {h: [0, Decimal("0")] for h in range(24)}
        for t in trades:
            h = t.exit_datetime.hour
            bucket[h][0] += 1
            bucket[h][1] += t.pnl_dollar
        return [HourlyBucket(hour=h, count=c, profit=p) for h, (c, p) in bucket.items()]

    def get_daily(self, f: StatsFilter) -> List[DailyBucket]:
        trades = self._trades(f)
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        bucket = {i: {"w": 0, "l": 0, "p": Decimal("0")} for i in range(7)}
        for t in trades:
            d = t.exit_datetime.weekday()
            if t.pnl_dollar > 0:
                bucket[d]["w"] += 1
            elif t.pnl_dollar < 0:
                bucket[d]["l"] += 1
            bucket[d]["p"] += t.pnl_dollar
        return [
            DailyBucket(weekday=i, name=names[i], winners=v["w"], losers=v["l"], profit=v["p"])
            for i, v in bucket.items()
        ]

    def get_risk_of_ruin(self, f: StatsFilter) -> List[RoRLevel]:
        trades = self._trades(f)
        wr = calc_win_rate(trades)
        awl = calc_avg_win_loss(trades)
        if wr.win_rate is None or awl.avg_loss_pct is None:
            return calc_risk_of_ruin(win_rate=0.0, avg_loss_pct=0.0)
        win_rate = float(wr.win_rate) / 100.0
        # avg_loss_pct comes back negative; flip to a positive fraction
        avg_loss_frac = abs(float(awl.avg_loss_pct)) / 100.0
        return calc_risk_of_ruin(
            win_rate=win_rate,
            avg_loss_pct=avg_loss_frac,
            loss_levels=DEFAULT_LOSS_LEVELS,
        )

    def get_duration(self, f: StatsFilter) -> DurationStats:
        trades = self._trades(f)
        if not trades:
            return DurationStats(
                points=[], avg_seconds=None, median_seconds=None,
                longest_seconds=None, shortest_seconds=None,
                avg_winner_seconds=None, avg_loser_seconds=None,
            )
        pts: List[DurationPoint] = []
        durs: List[int] = []
        winner_durs: List[int] = []
        loser_durs: List[int] = []
        for t in trades:
            secs = int(t.holding_duration.total_seconds())
            durs.append(secs)
            if t.pnl_dollar > 0:
                winner_durs.append(secs)
            elif t.pnl_dollar < 0:
                loser_durs.append(secs)
            pts.append(DurationPoint(
                asset=t.asset,
                duration_seconds=secs,
                pnl_dollar=t.pnl_dollar,
                pnl_percent=t.pnl_percent,
                direction=t.direction.value if t.direction else None,
                exit_datetime=t.exit_datetime.isoformat(),
            ))
        durs_sorted = sorted(durs)
        n = len(durs_sorted)
        median = durs_sorted[n // 2] if n % 2 == 1 else (durs_sorted[n // 2 - 1] + durs_sorted[n // 2]) / 2.0
        return DurationStats(
            points=pts,
            avg_seconds=sum(durs) / n,
            median_seconds=float(median),
            longest_seconds=max(durs),
            shortest_seconds=min(durs),
            avg_winner_seconds=(sum(winner_durs) / len(winner_durs)) if winner_durs else None,
            avg_loser_seconds=(sum(loser_durs) / len(loser_durs)) if loser_durs else None,
        )

    async def get_mae_mfe(self, f: StatsFilter, base: str = "USDT") -> MaeMfeData:
        if self._prices is None:
            raise RuntimeError("MAE/MFE requires PriceService — inject one")
        trades = self._trades(f)

        # --- Fetch all klines in parallel (capped at 10 concurrent) ---
        sem = asyncio.Semaphore(10)

        async def _fetch_klines(t: Trade):
            async with sem:
                interval = _pick_interval(t.holding_duration)
                return await self._prices.get_klines(
                    asset=t.asset,
                    base=base,
                    interval=interval,
                    start_time=t.entry_datetime,
                    end_time=t.exit_datetime,
                    limit=1000,
                )

        # Fire all fetches concurrently
        tasks = [_fetch_klines(t) for t in trades]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # --- Process results ---
        points: List[ExcursionPoint] = []
        sum_mae = Decimal("0")
        sum_mfe = Decimal("0")
        skipped = 0
        for t, klines_or_err in zip(trades, results):
            if isinstance(klines_or_err, BaseException) or not klines_or_err:
                skipped += 1
                continue
            klines = klines_or_err
            highs = [k.high for k in klines]
            lows = [k.low for k in klines]
            direction = t.direction or Direction.LONG
            if direction == Direction.LONG:
                mae_unit = calc_mae(t.entry_price, lows, direction)
                mfe_unit = calc_mfe(t.entry_price, highs, direction)
            else:
                mae_unit = calc_mae(t.entry_price, highs, direction)
                mfe_unit = calc_mfe(t.entry_price, lows, direction)
            mae_p = excursion_pct(mae_unit, t.entry_price)
            mfe_p = excursion_pct(mfe_unit, t.entry_price)
            points.append(ExcursionPoint(
                asset=t.asset,
                direction=direction.value if t.direction else None,
                entry_price=t.entry_price,
                exit_price=t.exit_price,
                pnl_pct=t.pnl_percent,
                mae_pct=mae_p,
                mfe_pct=mfe_p,
                exit_datetime=t.exit_datetime.isoformat(),
            ))
            sum_mae += mae_p
            sum_mfe += mfe_p
        n = len(points)
        return MaeMfeData(
            points=points,
            avg_mae_pct=(sum_mae / Decimal(n)) if n > 0 else None,
            avg_mfe_pct=(sum_mfe / Decimal(n)) if n > 0 else None,
            skipped=skipped,
        )


def _pick_interval(duration: timedelta) -> str:
    secs = duration.total_seconds()
    if secs <= 6 * 3600:
        return "1m"
    if secs <= 7 * 86400:
        return "1h"
    return "1d"
