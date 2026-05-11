"""P&L waterfall: gross → commission → funding → slippage → mgmt/perf fees → net."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class PnLWaterfall:
    gross_trading_pnl: Decimal
    total_commission: Decimal
    total_funding: Decimal
    total_slippage: Decimal
    net_trading_pnl: Decimal

    management_fee: Decimal
    performance_fee: Decimal
    net_portfolio_pnl: Decimal

    commission_drag_bps: Optional[float]
    funding_drag_bps: Optional[float]
    slippage_drag_bps: Optional[float]
    total_cost_ratio: Optional[float]

    winning_trades: int
    losing_trades: int
    total_notional_traded: Decimal


def calc_pnl_waterfall(
    trades: list,
    management_fee_rate: Optional[Decimal],
    performance_fee_rate: Optional[Decimal],
    period_start_nav: Decimal,
    period_end_nav: Decimal,
    high_water_mark: Optional[Decimal],
    period_days: int,
    total_slippage: Decimal = Decimal("0"),
) -> PnLWaterfall:
    gross = sum((t.gross_pnl for t in trades), Decimal("0"))
    commission = sum((t.fee_total for t in trades), Decimal("0"))
    funding = sum((t.funding_pnl for t in trades), Decimal("0"))

    net_trading = gross - commission - funding - total_slippage

    mgmt_fee = Decimal("0")
    if management_fee_rate and management_fee_rate > 0 and period_days > 0:
        avg_nav = (period_start_nav + period_end_nav) / Decimal("2")
        mgmt_fee = avg_nav * management_fee_rate * Decimal(period_days) / Decimal("365")

    perf_fee = Decimal("0")
    if performance_fee_rate and performance_fee_rate > 0:
        hwm = high_water_mark if high_water_mark is not None else period_start_nav
        if period_end_nav > hwm:
            perf_fee = (period_end_nav - hwm) * performance_fee_rate

    net_portfolio = net_trading - mgmt_fee - perf_fee

    total_notional = sum(
        (t.entry_price * t.quantity for t in trades), Decimal("0")
    )

    def _bps(cost: Decimal, notional: Decimal) -> Optional[float]:
        if notional <= 0:
            return None
        return float(cost / notional * Decimal("10000"))

    winners = sum(1 for t in trades if t.pnl_dollar > 0)
    losers = sum(1 for t in trades if t.pnl_dollar < 0)
    total_costs = commission + funding + total_slippage
    cost_ratio = float(total_costs / gross) if gross > 0 else None

    return PnLWaterfall(
        gross_trading_pnl=gross,
        total_commission=commission,
        total_funding=funding,
        total_slippage=total_slippage,
        net_trading_pnl=net_trading,
        management_fee=mgmt_fee,
        performance_fee=perf_fee,
        net_portfolio_pnl=net_portfolio,
        commission_drag_bps=_bps(commission, total_notional),
        funding_drag_bps=_bps(funding, total_notional),
        slippage_drag_bps=_bps(total_slippage, total_notional),
        total_cost_ratio=cost_ratio,
        winning_trades=winners,
        losing_trades=losers,
        total_notional_traded=total_notional,
    )
