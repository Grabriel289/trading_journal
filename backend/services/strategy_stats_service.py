"""Per-strategy performance attribution.

Reuses trade_stats calculators, grouping trades by `strategy_id`.
"""

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.calculators.trade_builder import Trade, build_trades
from backend.calculators.trade_stats import (
    calc_avg_win_loss,
    calc_best_worst,
    calc_consecutive_streaks,
    calc_profit_factor,
    calc_std_deviation,
    calc_win_rate,
)
from backend.models import Order, Portfolio, Strategy
from backend.services.stats_service import StatsFilter


@dataclass
class StrategyPerformance:
    strategy_id: Optional[str]
    strategy_name: str
    trade_count: int
    winners: int
    losers: int
    win_rate: Optional[Decimal]
    total_pnl: Decimal
    gross_pnl: Decimal
    total_commission: Decimal
    total_funding: Decimal
    avg_pnl_per_trade: Decimal
    profit_factor: Optional[Decimal]
    best_trade: Optional[Decimal]
    worst_trade: Optional[Decimal]
    avg_holding_seconds: Optional[float]
    std_deviation: Optional[Decimal]
    max_consecutive_wins: int
    max_consecutive_losses: int
    sharpe_estimate: Optional[float]


@dataclass
class StrategyAttribution:
    strategies: List[StrategyPerformance]
    total_pnl: Decimal
    untagged_pnl: Decimal
    strategy_count: int


class StrategyStatsService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_attribution(self, f: StatsFilter) -> StrategyAttribution:
        portfolio = self._db.get(Portfolio, f.portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {f.portfolio_id} not found")

        sub_ids = [s.id for s in portfolio.sub_accounts]
        sub_by_id = {s.id: s for s in portfolio.sub_accounts}
        if not sub_ids:
            return StrategyAttribution(
                strategies=[], total_pnl=Decimal("0"),
                untagged_pnl=Decimal("0"), strategy_count=0,
            )

        orders = (
            self._db.query(Order)
            .filter(Order.sub_account_id.in_(sub_ids))
            .order_by(Order.datetime)
            .all()
        )
        all_trades = build_trades(orders, sub_account_lookup=sub_by_id.get)

        trades = []
        for t in all_trades:
            if f.date_from and t.exit_datetime.date() < f.date_from:
                continue
            if f.date_to and t.exit_datetime.date() > f.date_to:
                continue
            trades.append(t)

        by_strategy: Dict[Optional[str], List[Trade]] = {}
        for t in trades:
            by_strategy.setdefault(t.strategy_id, []).append(t)

        strategy_names: Dict[str, str] = {}
        strategy_ids = [sid for sid in by_strategy if sid is not None]
        if strategy_ids:
            strats = (
                self._db.query(Strategy)
                .filter(Strategy.id.in_(strategy_ids))
                .all()
            )
            strategy_names = {s.id: s.name for s in strats}

        results: List[StrategyPerformance] = []
        for strat_id, strat_trades in by_strategy.items():
            wr = calc_win_rate(strat_trades)
            pf = calc_profit_factor(strat_trades)
            calc_avg_win_loss(strat_trades)  # touched but values not surfaced here
            bw = calc_best_worst(strat_trades)
            streaks = calc_consecutive_streaks(strat_trades)
            std = calc_std_deviation(strat_trades)

            total_pnl = sum((t.pnl_dollar for t in strat_trades), Decimal("0"))
            gross_pnl = sum((t.gross_pnl for t in strat_trades), Decimal("0"))
            total_comm = sum((t.fee_total for t in strat_trades), Decimal("0"))
            total_fund = sum((t.funding_pnl for t in strat_trades), Decimal("0"))
            n = len(strat_trades)

            sharpe_est = None
            if std is not None and std > 0 and n > 1:
                mean_pnl = total_pnl / Decimal(n)
                sharpe_est = float(mean_pnl / std) * math.sqrt(n)

            durations = [t.holding_duration.total_seconds() for t in strat_trades]
            avg_dur = sum(durations) / len(durations) if durations else None

            results.append(StrategyPerformance(
                strategy_id=strat_id,
                strategy_name=strategy_names.get(strat_id, "Untagged") if strat_id else "Untagged",
                trade_count=n,
                winners=wr.winners,
                losers=wr.losers,
                win_rate=wr.win_rate,
                total_pnl=total_pnl,
                gross_pnl=gross_pnl,
                total_commission=total_comm,
                total_funding=total_fund,
                avg_pnl_per_trade=total_pnl / Decimal(n) if n > 0 else Decimal("0"),
                profit_factor=pf,
                best_trade=bw.best_dollar,
                worst_trade=bw.worst_dollar,
                avg_holding_seconds=avg_dur,
                std_deviation=std,
                max_consecutive_wins=streaks.max_consecutive_wins,
                max_consecutive_losses=streaks.max_consecutive_losses,
                sharpe_estimate=sharpe_est,
            ))

        results.sort(key=lambda x: x.total_pnl, reverse=True)

        total = sum((r.total_pnl for r in results), Decimal("0"))
        untagged = next(
            (r.total_pnl for r in results if r.strategy_id is None),
            Decimal("0"),
        )

        return StrategyAttribution(
            strategies=results,
            total_pnl=total,
            untagged_pnl=untagged,
            strategy_count=len([r for r in results if r.strategy_id is not None]),
        )
