from decimal import Decimal

from backend.calculators.spot_calc import PnLResult
from backend.models.enums import Direction


DEFAULT_MAINTENANCE_MARGIN_RATE = Decimal("0.005")


def calc_margin_used(quantity: Decimal, entry_price: Decimal, leverage: int) -> Decimal:
    if leverage <= 0:
        raise ValueError("Leverage must be positive")
    return (quantity * entry_price) / Decimal(leverage)


def calc_liquidation_price(
    entry_price: Decimal,
    leverage: int,
    direction: Direction,
    maintenance_margin_rate: Decimal = DEFAULT_MAINTENANCE_MARGIN_RATE,
) -> Decimal:
    if leverage <= 0:
        raise ValueError("Leverage must be positive")
    inv_lev = Decimal(1) / Decimal(leverage)
    if direction == Direction.LONG:
        return entry_price * (Decimal(1) - inv_lev + maintenance_margin_rate)
    return entry_price * (Decimal(1) + inv_lev - maintenance_margin_rate)


def calc_futures_raw_pnl(
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: Decimal,
    direction: Direction,
) -> Decimal:
    if direction == Direction.LONG:
        return (exit_price - entry_price) * quantity
    return (entry_price - exit_price) * quantity


def calc_futures_pnl(
    entry_price: Decimal,
    exit_price: Decimal,
    quantity: Decimal,
    direction: Direction,
    margin_used: Decimal,
    funding_accumulated: Decimal = Decimal("0"),
    entry_fee: Decimal = Decimal("0"),
    exit_fee: Decimal = Decimal("0"),
) -> PnLResult:
    raw = calc_futures_raw_pnl(entry_price, exit_price, quantity, direction)
    net = raw - funding_accumulated - entry_fee - exit_fee
    pct = (net / margin_used * Decimal("100")) if margin_used > 0 else Decimal("0")
    return PnLResult(gross_pnl=raw, net_pnl=net, pnl_pct=pct)


def calc_unrealized_futures_pnl(
    entry_price: Decimal,
    current_price: Decimal,
    quantity: Decimal,
    direction: Direction,
    funding_accumulated: Decimal = Decimal("0"),
) -> Decimal:
    raw = calc_futures_raw_pnl(entry_price, current_price, quantity, direction)
    return raw - funding_accumulated
