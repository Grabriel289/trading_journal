"""Funding analytics — converts FundingPayment time-series into actionable metrics.

Daily aggregation, per-position aggregation, annualized funding cost as % of notional.
"""

from dataclasses import dataclass
from datetime import date as date_cls
from decimal import Decimal
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class FundingDailySummary:
    date: date_cls
    total_paid: Decimal       # net (positive = paid out, negative = received)
    payment_count: int
    positions_affected: int


@dataclass(frozen=True)
class FundingByPosition:
    order_id: str
    asset: str
    direction: str            # LONG / SHORT
    total_funding: Decimal
    annualized_rate: Optional[float]  # % of notional, annualized
    payment_count: int
    avg_payment: Decimal
    max_single_payment: Decimal
    holding_days: int


@dataclass(frozen=True)
class FundingAnalytics:
    daily: List[FundingDailySummary]
    by_position: List[FundingByPosition]
    total_paid: Decimal
    total_received: Decimal
    net_funding: Decimal
    avg_daily_cost: Optional[Decimal]


def calc_funding_analytics(
    payments: Sequence,           # FundingPayment ORM rows
    orders_by_id: Dict[str, object],
) -> FundingAnalytics:
    """Aggregate FundingPayment rows into daily + per-position summaries."""
    daily_map: Dict[date_cls, dict] = {}
    for fp in payments:
        d = fp.funding_time.date()
        if d not in daily_map:
            daily_map[d] = {"total": Decimal("0"), "count": 0, "orders": set()}
        daily_map[d]["total"] += Decimal(fp.payment_amount)
        daily_map[d]["count"] += 1
        daily_map[d]["orders"].add(fp.order_id)

    daily = sorted([
        FundingDailySummary(
            date=d,
            total_paid=v["total"],
            payment_count=v["count"],
            positions_affected=len(v["orders"]),
        )
        for d, v in daily_map.items()
    ], key=lambda x: x.date)

    pos_map: Dict[str, list] = {}
    for fp in payments:
        pos_map.setdefault(fp.order_id, []).append(fp)

    by_position: List[FundingByPosition] = []
    total_paid = Decimal("0")
    total_received = Decimal("0")

    for order_id, fps in pos_map.items():
        order = orders_by_id.get(order_id)
        amounts = [Decimal(fp.payment_amount) for fp in fps]
        total = sum(amounts, Decimal("0"))

        if total > 0:
            total_paid += total
        else:
            total_received += abs(total)

        annualized = None
        holding_days = 0
        if order is not None and fps:
            dates = [fp.funding_time for fp in fps]
            holding_days = max(1, (max(dates).date() - min(dates).date()).days)
            notional = Decimal(order.quantity) * Decimal(order.price)
            if notional > 0 and holding_days > 0:
                annualized = float(
                    abs(total) / notional * Decimal(365) / Decimal(holding_days) * Decimal(100)
                )

        asset = order.asset if order is not None else "UNKNOWN"
        direction = (
            order.direction.value
            if order is not None and order.direction is not None
            else "UNKNOWN"
        )

        by_position.append(FundingByPosition(
            order_id=order_id,
            asset=asset,
            direction=direction,
            total_funding=total,
            annualized_rate=annualized,
            payment_count=len(fps),
            avg_payment=total / Decimal(len(fps)) if fps else Decimal("0"),
            max_single_payment=max((abs(a) for a in amounts), default=Decimal("0")),
            holding_days=holding_days,
        ))

    by_position.sort(key=lambda x: abs(x.total_funding), reverse=True)

    net = total_paid - total_received
    n_days = len(daily)
    avg_daily = net / Decimal(n_days) if n_days > 0 else None

    return FundingAnalytics(
        daily=daily,
        by_position=by_position,
        total_paid=total_paid,
        total_received=total_received,
        net_funding=net,
        avg_daily_cost=avg_daily,
    )
