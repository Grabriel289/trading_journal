from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, List, Optional

from backend.calculators.futures_calc import (
    calc_futures_pnl,
    calc_futures_raw_pnl,
)
from backend.calculators.spot_calc import calc_spot_pnl
from backend.models.enums import Direction, Side, SubAccountType


@dataclass(frozen=True)
class Trade:
    """Round-trip trade computed from a matched (buy, sell) pair."""

    entry_order_id: str
    exit_order_id: str
    sub_account_id: str
    sub_account_type: SubAccountType
    asset: str

    entry_datetime: datetime
    exit_datetime: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal

    pnl_dollar: Decimal     # NET P&L (after fees and funding)
    pnl_percent: Decimal
    fee_total: Decimal      # COMMISSION only (entry_fee_share + exit_fee). Funding split out.
    funding_pnl: Decimal    # Funding paid / received (positive = paid by trader)
    gross_pnl: Decimal      # Raw price-move PnL before any deductions
    holding_duration: timedelta

    leverage: Optional[int] = None
    direction: Optional[Direction] = None
    strategy_id: Optional[str] = None


def build_trades(orders: Iterable, sub_account_lookup) -> List[Trade]:
    """Pure function: given orders (buys + sells with lot linkage), return round-trip Trades.

    `orders`: any iterable yielding ORM Order rows (or duck-typed equivalents).
    `sub_account_lookup`: callable(sub_account_id) -> (type, ...). Only `.type` is read.
    """
    by_id = {o.id: o for o in orders}
    trades: List[Trade] = []

    for o in by_id.values():
        if o.side != Side.SELL or not o.linked_buy_order_id:
            continue
        buy = by_id.get(o.linked_buy_order_id)
        if buy is None:
            continue

        sell_qty = Decimal(o.sell_quantity if o.sell_quantity is not None else o.quantity)
        buy_qty = Decimal(buy.quantity)
        share = sell_qty / buy_qty if buy_qty > 0 else Decimal("0")
        buy_fee_share = Decimal(buy.fee) * share
        sell_fee = Decimal(o.fee)

        sub = sub_account_lookup(o.sub_account_id)
        sub_type = sub.type if sub is not None else SubAccountType.SPOT

        if buy.direction is not None:  # futures round-trip
            # Prefer the FundingPayment time-series (Phase 2+) over the cached
            # lump-sum on the order — the cache can lag a recent funding event.
            ts = getattr(buy, "funding_payments", None)
            if ts:
                total_funding = sum(
                    (Decimal(fp.payment_amount) for fp in ts), Decimal("0")
                )
                funding_share = total_funding * share
            else:
                funding_share = Decimal(buy.funding_accumulated or Decimal("0")) * share
            margin_share = Decimal(buy.margin_used or Decimal("0")) * share
            pnl = calc_futures_pnl(
                entry_price=Decimal(buy.price),
                exit_price=Decimal(o.price),
                quantity=sell_qty,
                direction=buy.direction,
                margin_used=margin_share,
                funding_accumulated=funding_share,
                entry_fee=buy_fee_share,
                exit_fee=sell_fee,
            )
            gross = calc_futures_raw_pnl(
                entry_price=Decimal(buy.price),
                exit_price=Decimal(o.price),
                quantity=sell_qty,
                direction=buy.direction,
            )
            # Commission only — funding split out into funding_pnl
            fee_total = buy_fee_share + sell_fee
            funding_pnl = funding_share
            leverage = buy.leverage
            direction = buy.direction
        else:  # spot round-trip
            pnl = calc_spot_pnl(
                entry_price=Decimal(buy.price),
                exit_price=Decimal(o.price),
                quantity=sell_qty,
                entry_fee=buy_fee_share,
                exit_fee=sell_fee,
            )
            gross = pnl.gross_pnl
            fee_total = buy_fee_share + sell_fee
            funding_pnl = Decimal("0")
            leverage = None
            direction = None

        # Phase 2: strategy attribution — prefer the buy's strategy (the
        # opening intent); if absent, fall back to the sell's
        strategy_id = buy.strategy_id or o.strategy_id

        trades.append(
            Trade(
                entry_order_id=buy.id,
                exit_order_id=o.id,
                sub_account_id=o.sub_account_id,
                sub_account_type=sub_type,
                asset=o.asset,
                entry_datetime=buy.datetime,
                exit_datetime=o.datetime,
                entry_price=Decimal(buy.price),
                exit_price=Decimal(o.price),
                quantity=sell_qty,
                pnl_dollar=pnl.net_pnl,
                pnl_percent=pnl.pnl_pct,
                fee_total=fee_total,
                funding_pnl=funding_pnl,
                gross_pnl=gross,
                holding_duration=o.datetime - buy.datetime,
                leverage=leverage,
                direction=direction,
                strategy_id=strategy_id,
            )
        )

    trades.sort(key=lambda t: t.exit_datetime, reverse=True)
    return trades
