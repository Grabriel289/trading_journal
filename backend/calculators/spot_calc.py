from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PnLResult:
    gross_pnl: Decimal
    net_pnl: Decimal
    pnl_pct: Decimal  # net_pnl / cost_basis * 100


def calc_unrealized_pnl(
    entry_price: Decimal, current_price: Decimal, quantity: Decimal
) -> Decimal:
    return (current_price - entry_price) * quantity


def calc_position_value(current_price: Decimal, quantity: Decimal) -> Decimal:
    return current_price * quantity


def calc_spot_pnl(
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: Decimal,
    entry_fee: Decimal = Decimal("0"),
    exit_fee: Decimal = Decimal("0"),
) -> PnLResult:
    gross = (exit_price - entry_price) * quantity
    net = gross - entry_fee - exit_fee
    cost_basis = entry_price * quantity
    pct = (net / cost_basis * Decimal("100")) if cost_basis > 0 else Decimal("0")
    return PnLResult(gross_pnl=gross, net_pnl=net, pnl_pct=pct)
