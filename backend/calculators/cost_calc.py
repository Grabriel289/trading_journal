"""Trade cost attribution — commission + funding + slippage breakdown.

Slippage = (actual_fill - expected_price) × quantity.
For BUY: positive slippage = paid more than expected (bad).
For SELL: positive slippage = received less than expected (bad).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Sequence


@dataclass(frozen=True)
class TradeCostBreakdown:
    entry_commission: Decimal
    exit_commission: Decimal
    total_commission: Decimal
    entry_slippage: Optional[Decimal]
    exit_slippage: Optional[Decimal]
    total_slippage: Optional[Decimal]
    funding_cost: Decimal
    total_cost: Decimal
    cost_as_pct_of_notional: Decimal
    entry_maker_taker: Optional[str]
    exit_maker_taker: Optional[str]


def calc_trade_costs(
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: Decimal,
    entry_fee: Decimal,
    exit_fee: Decimal,
    funding: Decimal = Decimal("0"),
    entry_expected_price: Optional[Decimal] = None,
    exit_expected_price: Optional[Decimal] = None,
    entry_maker_taker: Optional[str] = None,
    exit_maker_taker: Optional[str] = None,
) -> TradeCostBreakdown:
    total_commission = entry_fee + exit_fee

    entry_slip = (
        (entry_price - entry_expected_price) * quantity
        if entry_expected_price is not None else None
    )
    exit_slip = (
        (exit_expected_price - exit_price) * quantity
        if exit_expected_price is not None else None
    )

    total_slip = None
    if entry_slip is not None or exit_slip is not None:
        total_slip = (entry_slip or Decimal("0")) + (exit_slip or Decimal("0"))

    total_cost = total_commission + funding + (total_slip or Decimal("0"))
    notional = entry_price * quantity
    cost_pct = (
        (total_cost / notional * Decimal("100")) if notional > 0
        else Decimal("0")
    )

    return TradeCostBreakdown(
        entry_commission=entry_fee,
        exit_commission=exit_fee,
        total_commission=total_commission,
        entry_slippage=entry_slip,
        exit_slippage=exit_slip,
        total_slippage=total_slip,
        funding_cost=funding,
        total_cost=total_cost,
        cost_as_pct_of_notional=cost_pct,
        entry_maker_taker=entry_maker_taker,
        exit_maker_taker=exit_maker_taker,
    )


@dataclass(frozen=True)
class SlippageGroupBucket:
    group: str
    avg_slippage_bps: float
    trade_count: int


@dataclass(frozen=True)
class SlippageStats:
    total_slippage_cost: Decimal
    avg_slippage_per_trade: Optional[Decimal]
    avg_slippage_bps: Optional[float]
    slippage_by_venue: List[SlippageGroupBucket]
    slippage_by_order_type: List[SlippageGroupBucket]
    worst_slippage_trade: Optional[str]
    trades_with_slippage_data: int
    trades_without_slippage_data: int


def calc_slippage_stats(trades_with_costs: Sequence[dict]) -> SlippageStats:
    """`trades_with_costs`: list of {trade, costs, entry_order, exit_order}.
    `costs.total_slippage` is None when expected_price isn't set on either side.
    """
    has_data = [t for t in trades_with_costs if t["costs"].total_slippage is not None]
    no_data = len(trades_with_costs) - len(has_data)

    if not has_data:
        return SlippageStats(
            total_slippage_cost=Decimal("0"),
            avg_slippage_per_trade=None,
            avg_slippage_bps=None,
            slippage_by_venue=[],
            slippage_by_order_type=[],
            worst_slippage_trade=None,
            trades_with_slippage_data=0,
            trades_without_slippage_data=no_data,
        )

    total = sum((t["costs"].total_slippage for t in has_data), Decimal("0"))
    avg_per_trade = total / Decimal(len(has_data))

    total_notional = sum(
        (t["trade"].entry_price * t["trade"].quantity for t in has_data),
        Decimal("0"),
    )
    avg_bps = (
        float(total / total_notional * Decimal("10000"))
        if total_notional > 0 else None
    )

    def _group_by(attr: str) -> List[SlippageGroupBucket]:
        bucket: Dict[str, List[dict]] = {}
        for t in has_data:
            v = getattr(t["entry_order"], attr, None)
            key = v.value if v is not None else "UNKNOWN"
            bucket.setdefault(key, []).append(t)

        out: List[SlippageGroupBucket] = []
        for k, items in bucket.items():
            v_total = sum(
                (i["costs"].total_slippage for i in items), Decimal("0")
            )
            v_notional = sum(
                (i["trade"].entry_price * i["trade"].quantity for i in items),
                Decimal("0"),
            )
            bps = (
                float(v_total / v_notional * Decimal("10000"))
                if v_notional > 0 else 0.0
            )
            out.append(SlippageGroupBucket(
                group=k, avg_slippage_bps=bps, trade_count=len(items),
            ))
        out.sort(key=lambda x: abs(x.avg_slippage_bps), reverse=True)
        return out

    worst = max(has_data, key=lambda t: abs(t["costs"].total_slippage))

    return SlippageStats(
        total_slippage_cost=total,
        avg_slippage_per_trade=avg_per_trade,
        avg_slippage_bps=avg_bps,
        slippage_by_venue=_group_by("execution_venue"),
        slippage_by_order_type=_group_by("order_type"),
        worst_slippage_trade=worst["trade"].entry_order_id,
        trades_with_slippage_data=len(has_data),
        trades_without_slippage_data=no_data,
    )
