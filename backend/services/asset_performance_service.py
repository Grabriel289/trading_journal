"""Asset performance — contribution per asset to portfolio return.

Combines:
- Buy order metadata (count, invested capital)
- Closed-trade realized P&L (sum of Trade.pnl_dollar grouped by asset)
- Open positions mark-to-market unrealized P&L

Uses PortfolioService.get_overview() so it shares the same price-fetch and
graceful-fallback behavior as the dashboard.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List

from sqlalchemy.orm import Session

from backend.calculators.trade_builder import build_trades
from backend.models import Order, Portfolio
from backend.models.enums import Side
from backend.services.portfolio_service import PortfolioService


@dataclass
class AssetPerformanceRow:
    symbol: str
    total_trades: int
    open_trades: int
    closed_trades: int
    total_invested: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    current_value: Decimal
    return_pct: Decimal
    contribution_pct: Decimal


class AssetPerformanceService:
    def __init__(self, db: Session, portfolio_service: PortfolioService) -> None:
        self._db = db
        self._portfolio_service = portfolio_service

    async def get_rows(self, portfolio_id: str) -> List[AssetPerformanceRow]:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        sub_ids = [s.id for s in portfolio.sub_accounts]
        if not sub_ids:
            return []

        sub_by_id = {s.id: s for s in portfolio.sub_accounts}

        # All orders for the portfolio, for both trade-building and per-asset
        # aggregation of buys.
        orders = (
            self._db.query(Order)
            .filter(Order.sub_account_id.in_(sub_ids))
            .order_by(Order.datetime)
            .all()
        )

        # Realized P&L per asset from closed round-trips
        trades = build_trades(orders, sub_account_lookup=sub_by_id.get)
        realized_by_asset: Dict[str, Decimal] = {}
        for t in trades:
            realized_by_asset[t.asset] = (
                realized_by_asset.get(t.asset, Decimal("0")) + t.pnl_dollar
            )

        # Per-asset buy aggregates
        agg: Dict[str, dict] = {}
        for o in orders:
            if o.side != Side.BUY:
                continue
            row = agg.setdefault(o.asset, {
                "total_trades": 0,
                "open_trades": 0,
                "total_invested": Decimal("0"),
            })
            row["total_trades"] += 1
            if Decimal(o.remaining_quantity) > 0:
                row["open_trades"] += 1
            row["total_invested"] += Decimal(o.price) * Decimal(o.quantity)

        # Open positions: current value + unrealized P&L from the live overview.
        # Reuse PortfolioService so price-fetch matches the dashboard.
        overview = await self._portfolio_service.get_overview(portfolio_id)
        unrealized_by_asset: Dict[str, Decimal] = {}
        current_value_by_asset: Dict[str, Decimal] = {}
        for sub in overview.sub_accounts:
            for p in sub.open_positions:
                unrealized_by_asset[p.asset] = (
                    unrealized_by_asset.get(p.asset, Decimal("0"))
                    + Decimal(p.unrealized_pnl)
                )
                current_value_by_asset[p.asset] = (
                    current_value_by_asset.get(p.asset, Decimal("0"))
                    + Decimal(p.market_value)
                )

        total_nav = Decimal(overview.total_equity)

        # Union of assets seen anywhere (buys, closed trades, open positions)
        all_assets = (
            set(agg.keys())
            | set(realized_by_asset.keys())
            | set(unrealized_by_asset.keys())
        )

        rows: List[AssetPerformanceRow] = []
        for sym in all_assets:
            stats = agg.get(sym, {
                "total_trades": 0, "open_trades": 0,
                "total_invested": Decimal("0"),
            })
            invested = stats["total_invested"]
            realized = realized_by_asset.get(sym, Decimal("0"))
            unrealized = unrealized_by_asset.get(sym, Decimal("0"))
            current_value = current_value_by_asset.get(sym, Decimal("0"))
            total_pnl = realized + unrealized

            return_pct = (
                total_pnl / invested * Decimal("100")
                if invested > 0 else Decimal("0")
            )
            contribution_pct = (
                total_pnl / total_nav * Decimal("100")
                if total_nav > 0 else Decimal("0")
            )

            rows.append(AssetPerformanceRow(
                symbol=sym,
                total_trades=stats["total_trades"],
                open_trades=stats["open_trades"],
                closed_trades=stats["total_trades"] - stats["open_trades"],
                total_invested=invested,
                realized_pnl=realized,
                unrealized_pnl=unrealized,
                total_pnl=total_pnl,
                current_value=current_value,
                return_pct=return_pct,
                contribution_pct=contribution_pct,
            ))

        rows.sort(key=lambda r: r.contribution_pct, reverse=True)
        return rows
