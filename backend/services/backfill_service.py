"""Reconstruct historical equity snapshots from the order + deposit log.

For every day from the first event to today, we replay events in chronological
order, then mark-to-market still-open positions with that day's Binance 1d
close price. Each (portfolio_id, date) row is upserted in `equity_snapshots`.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date as date_cls, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Dict, List

from sqlalchemy.orm import Session

from backend.models import (
    Deposit,
    DepositType,
    Direction,
    EquitySnapshot,
    Order,
    OrderStatus,
    Portfolio,
    Side,
)
from backend.services.price_service import PriceService
from backend.util.clock import utc_now


@dataclass
class BackfillResult:
    snapshots_upserted: int
    first_date: str
    last_date: str
    assets_priced: List[str]
    assets_skipped: List[str]


class BackfillService:
    def __init__(self, db: Session, price_service: PriceService) -> None:
        self._db = db
        self._prices = price_service

    async def backfill(self, portfolio_id: str) -> BackfillResult:
        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        sub_ids = [s.id for s in portfolio.sub_accounts]
        all_orders: List[Order] = []
        all_deposits: List[Deposit] = []
        for sub in portfolio.sub_accounts:
            all_orders.extend(sub.orders)
            all_deposits.extend(sub.deposits)

        if not all_orders and not all_deposits:
            raise ValueError("Portfolio has no orders or deposits to backfill from")

        first_event_dt = min(
            min((o.datetime for o in all_orders), default=datetime.max),
            min((d.datetime for d in all_deposits), default=datetime.max),
        )
        first_date = first_event_dt.date()
        today = utc_now().date()

        # Fetch 1d klines once per asset
        base = portfolio.base_currency.value
        assets = sorted({o.asset for o in all_orders})
        price_by_asset_date: Dict[str, Dict[date_cls, Decimal]] = {}
        skipped: List[str] = []
        priced: List[str] = []

        # Pad start by 1 day so we have the previous close if needed.
        kline_start = datetime.combine(first_date, time.min, tzinfo=timezone.utc)
        kline_end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc)

        for asset in assets:
            try:
                klines = await self._prices.get_klines(
                    asset=asset, base=base, interval="1d",
                    start_time=kline_start, end_time=kline_end, limit=1000,
                )
            except Exception:
                skipped.append(asset)
                continue
            if not klines:
                skipped.append(asset)
                continue
            price_by_asset_date[asset] = {
                k.open_time.date(): k.close for k in klines
            }
            priced.append(asset)

        # Sort all events chronologically
        events = sorted(
            [(o.datetime, "order", o) for o in all_orders]
            + [(d.datetime, "deposit", d) for d in all_deposits],
            key=lambda x: x[0],
        )

        # Per-sub-account state we mutate as we walk events
        cash_per_sub: Dict[str, Decimal] = {
            sub.id: Decimal(sub.initial_capital) for sub in portfolio.sub_accounts
        }
        deposited_per_sub: Dict[str, Decimal] = {
            sub.id: Decimal(sub.initial_capital) for sub in portfolio.sub_accounts
        }
        # buy_state[buy_order_id] = [order, remaining_qty]
        buy_state: Dict[str, list] = {}

        snapshots_upserted = 0
        peak_equity = Decimal("0")
        idx = 0
        cur_date = first_date

        # Wipe existing snapshots in the backfill window so a clean replay
        # produces clean rows (no leftover from prior partial backfills).
        (
            self._db.query(EquitySnapshot)
            .filter(EquitySnapshot.portfolio_id == portfolio_id)
            .filter(EquitySnapshot.date >= first_date)
            .filter(EquitySnapshot.date <= today)
            .delete(synchronize_session=False)
        )
        self._db.flush()

        while cur_date <= today:
            # Apply all events whose datetime is <= end-of-this-date
            while idx < len(events) and events[idx][0].date() <= cur_date:
                _, kind, ev = events[idx]
                if kind == "order":
                    self._apply_order(ev, cash_per_sub, buy_state)
                else:
                    self._apply_deposit(ev, cash_per_sub, deposited_per_sub)
                idx += 1

            # Compute today's equity using closing prices
            sub_account_data = []
            total_equity = Decimal("0")
            total_balance = Decimal("0")
            total_deposited = Decimal("0")

            for sub in portfolio.sub_accounts:
                cash = cash_per_sub[sub.id]
                market_value = Decimal("0")

                for buy_id, (buy, remaining) in buy_state.items():
                    if buy.sub_account_id != sub.id or remaining <= 0:
                        continue
                    close = self._lookup_close(price_by_asset_date, buy.asset, cur_date)
                    if close is None:
                        # Without a price we can't mark-to-market; fall back to cost basis.
                        close = Decimal(buy.price)

                    if buy.direction is None:
                        market_value += close * remaining
                    else:
                        share = remaining / Decimal(buy.quantity)
                        margin_remaining = Decimal(buy.margin_used or 0) * share
                        funding_share = Decimal(buy.funding_accumulated or 0) * share
                        if buy.direction == Direction.LONG:
                            raw = (close - Decimal(buy.price)) * remaining
                        else:
                            raw = (Decimal(buy.price) - close) * remaining
                        market_value += margin_remaining + raw - funding_share

                sub_equity = cash + market_value
                sub_account_data.append({
                    "id": sub.id,
                    "name": sub.name,
                    "type": sub.type.value,
                    "equity": str(sub_equity),
                    "cash": str(cash),
                    "market_value": str(market_value),
                    "unrealized_pnl": str(sub_equity - deposited_per_sub[sub.id]),
                })
                total_equity += sub_equity
                total_balance += cash
                total_deposited += deposited_per_sub[sub.id]

            peak_equity = max(peak_equity, total_equity)
            drawdown = (
                ((peak_equity - total_equity) / peak_equity * Decimal("100"))
                if peak_equity > 0 else Decimal("0")
            )

            snap = EquitySnapshot(
                portfolio_id=portfolio_id,
                date=cur_date,
                total_equity=total_equity,
                total_balance=total_balance,
                total_deposited=total_deposited,
                drawdown_pct=drawdown,
                sub_account_data=sub_account_data,
            )
            self._db.add(snap)
            snapshots_upserted += 1

            cur_date += timedelta(days=1)

        self._db.commit()

        return BackfillResult(
            snapshots_upserted=snapshots_upserted,
            first_date=first_date.isoformat(),
            last_date=today.isoformat(),
            assets_priced=priced,
            assets_skipped=skipped,
        )

    @staticmethod
    def _lookup_close(
        prices: Dict[str, Dict[date_cls, Decimal]],
        asset: str,
        d: date_cls,
    ):
        per_asset = prices.get(asset)
        if per_asset is None:
            return None
        # Walk back up to 7 days to handle thin trading / missing klines.
        for delta in range(0, 8):
            close = per_asset.get(d - timedelta(days=delta))
            if close is not None:
                return Decimal(close)
        return None

    @staticmethod
    def _apply_order(
        order: Order,
        cash_per_sub: Dict[str, Decimal],
        buy_state: Dict[str, list],
    ) -> None:
        if order.side == Side.BUY:
            if order.direction is not None:
                cash_per_sub[order.sub_account_id] -= (
                    Decimal(order.margin_used or 0) + Decimal(order.fee)
                )
            else:
                cash_per_sub[order.sub_account_id] -= (
                    Decimal(order.total_value) + Decimal(order.fee)
                )
            buy_state[order.id] = [order, Decimal(order.quantity)]
            return

        # SELL
        linked = buy_state.get(order.linked_buy_order_id) if order.linked_buy_order_id else None
        if linked is None:
            # Orphaned sell — apply spot-style cash flow defensively.
            cash_per_sub[order.sub_account_id] += (
                Decimal(order.total_value) - Decimal(order.fee)
            )
            return
        buy, remaining = linked
        sell_qty = Decimal(order.sell_quantity or order.quantity)

        if buy.direction is not None:
            share = sell_qty / Decimal(buy.quantity)
            margin_share = Decimal(buy.margin_used or 0) * share
            funding_share = Decimal(buy.funding_accumulated or 0) * share
            if buy.direction == Direction.LONG:
                raw = (Decimal(order.price) - Decimal(buy.price)) * sell_qty
            else:
                raw = (Decimal(buy.price) - Decimal(order.price)) * sell_qty
            cash_per_sub[order.sub_account_id] += (
                margin_share + raw - Decimal(order.fee) - funding_share
            )
        else:
            cash_per_sub[order.sub_account_id] += (
                Decimal(order.total_value) - Decimal(order.fee)
            )

        linked[1] = remaining - sell_qty

    @staticmethod
    def _apply_deposit(
        deposit: Deposit,
        cash_per_sub: Dict[str, Decimal],
        deposited_per_sub: Dict[str, Decimal],
    ) -> None:
        amt = Decimal(deposit.amount)
        if deposit.type == DepositType.DEPOSIT:
            cash_per_sub[deposit.sub_account_id] += amt
            deposited_per_sub[deposit.sub_account_id] += amt
        else:
            cash_per_sub[deposit.sub_account_id] -= amt
            deposited_per_sub[deposit.sub_account_id] -= amt
