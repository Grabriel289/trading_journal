"""Per-coin trading skill stats — distinct from contribution-to-portfolio.

Per asset: closed trade count, wins, win rate, total/avg P&L, avg hold
duration, best/worst single trade.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.calculators.trade_builder import build_trades
from backend.models import Order, Portfolio


@dataclass
class PerCoinRow:
    symbol: str
    trades: int
    wins: int
    win_rate: Decimal
    total_pnl: Decimal
    avg_pnl: Decimal
    avg_hold_seconds: float
    best_pnl: Decimal
    worst_pnl: Decimal


class PerCoinService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_rows(self, portfolio_id: str) -> List[PerCoinRow]:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        sub_ids = [s.id for s in portfolio.sub_accounts]
        if not sub_ids:
            return []

        sub_by_id = {s.id: s for s in portfolio.sub_accounts}
        orders = (
            self._db.query(Order)
            .filter(Order.sub_account_id.in_(sub_ids))
            .order_by(Order.datetime)
            .all()
        )
        trades = build_trades(orders, sub_account_lookup=sub_by_id.get)

        by_asset: Dict[str, list] = {}
        for t in trades:
            by_asset.setdefault(t.asset, []).append(t)

        rows: List[PerCoinRow] = []
        for symbol, ts in by_asset.items():
            n = len(ts)
            wins = sum(1 for t in ts if t.pnl_dollar > 0)
            total = sum((t.pnl_dollar for t in ts), Decimal("0"))
            durations = [t.holding_duration.total_seconds() for t in ts]
            best = max(t.pnl_dollar for t in ts)
            worst = min(t.pnl_dollar for t in ts)

            rows.append(PerCoinRow(
                symbol=symbol,
                trades=n,
                wins=wins,
                win_rate=(
                    Decimal(wins) / Decimal(n) * Decimal("100")
                    if n > 0 else Decimal("0")
                ),
                total_pnl=total,
                avg_pnl=total / Decimal(n) if n > 0 else Decimal("0"),
                avg_hold_seconds=sum(durations) / len(durations) if durations else 0.0,
                best_pnl=best,
                worst_pnl=worst,
            ))

        rows.sort(key=lambda r: r.total_pnl, reverse=True)
        return rows
