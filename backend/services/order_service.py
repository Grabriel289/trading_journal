import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.calculators.futures_calc import calc_liquidation_price, calc_margin_used
from backend.calculators.trade_builder import Trade, build_trades
from backend.models import (
    Direction, ExecutionVenue, MakerTaker, Order, OrderStatus, OrderType,
    Side, SubAccount, SubAccountType,
)
from backend.services.price_service import PriceService
from backend.util.clock import utc_now


logger = logging.getLogger(__name__)

# Two orders considered "likely duplicate" if posted within this window
# with identical (sub_account, asset, side, quantity, price).
DUPLICATE_WINDOW_SECONDS = 60


@dataclass
class BuyOrderInput:
    sub_account_id: str
    asset: str
    quantity: Decimal
    price: Optional[Decimal] = None  # if None, fetch live
    fee: Decimal = Decimal("0")
    note: Optional[str] = None
    when: Optional[datetime] = None
    # Futures-only (required when sub-account.type == FUTURES)
    leverage: Optional[int] = None
    direction: Optional[Direction] = None
    funding_accumulated: Decimal = Decimal("0")
    # Phase 2: enriched metadata
    strategy_id: Optional[str] = None
    order_type: Optional[OrderType] = None
    execution_venue: Optional[ExecutionVenue] = None
    exchange_order_id: Optional[str] = None
    exchange_trade_id: Optional[str] = None
    expected_price: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    maker_taker: Optional[MakerTaker] = None
    tag_ids: List[str] = field(default_factory=list)


@dataclass
class SellOrderInput:
    linked_buy_order_id: str
    sell_quantity: Decimal
    price: Optional[Decimal] = None  # if None, fetch live
    fee: Decimal = Decimal("0")
    note: Optional[str] = None
    when: Optional[datetime] = None
    # Phase 2: enriched metadata
    strategy_id: Optional[str] = None
    order_type: Optional[OrderType] = None
    execution_venue: Optional[ExecutionVenue] = None
    exchange_order_id: Optional[str] = None
    exchange_trade_id: Optional[str] = None
    expected_price: Optional[Decimal] = None
    fee_currency: Optional[str] = None
    maker_taker: Optional[MakerTaker] = None
    tag_ids: List[str] = field(default_factory=list)


def _attach_tags(db: Session, order: Order, tag_ids: List[str]) -> None:
    if not tag_ids:
        return
    from backend.models import Tag
    found = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
    order.tags = list(found)


def _create_confirmation(db: Session, order: Order) -> None:
    """Append an immutable TradeConfirmation snapshot for this order.
    Called inside the same transaction as the order create_buy/create_sell."""
    from backend.models import Strategy, SubAccount, TradeConfirmation
    sub = db.get(SubAccount, order.sub_account_id)
    strat = db.get(Strategy, order.strategy_id) if order.strategy_id else None
    snapshot = {
        c.key: (str(getattr(order, c.key)) if getattr(order, c.key) is not None else None)
        for c in order.__table__.columns
    }
    confirmation = TradeConfirmation(
        order_id=order.id,
        portfolio_id=sub.portfolio_id if sub else "",
        sub_account_id=order.sub_account_id,
        sub_account_name=sub.name if sub else "",
        asset=order.asset,
        side=order.side.value,
        quantity=order.quantity,
        price=order.price,
        total_value=order.total_value,
        fee=order.fee,
        fee_currency=order.fee_currency,
        order_type=order.order_type.value if order.order_type else None,
        execution_venue=order.execution_venue.value if order.execution_venue else None,
        exchange_order_id=order.exchange_order_id,
        strategy_name=strat.name if strat else None,
        leverage=order.leverage,
        direction=order.direction.value if order.direction else None,
        margin_used=order.margin_used,
        linked_buy_order_id=order.linked_buy_order_id,
        raw_snapshot=snapshot,
    )
    db.add(confirmation)


class OrderService:
    def __init__(self, db: Session, price_service: PriceService) -> None:
        self._db = db
        self._prices = price_service

    async def create_buy(self, data: BuyOrderInput) -> Order:
        from backend.services.asset_service import AssetService

        sub = self._db.get(SubAccount, data.sub_account_id)
        if sub is None:
            raise ValueError(f"SubAccount {data.sub_account_id} not found")

        # Auto-register asset on first reference (with default Binance/Kucoin/Coingecko sources).
        AssetService(self._db).ensure_asset(data.asset)

        base = sub.portfolio.base_currency.value
        price = data.price if data.price is not None else await self._prices.get_price(
            data.asset, base
        )
        quantity = Decimal(data.quantity)
        total_value = price * quantity

        # Duplicate guard: same (sub, asset, side, qty, price) within the window
        # → probably a double-click or replayed request. Reject with a clear msg
        # so the user can explicitly resubmit with a different timestamp if intentional.
        when = data.when or utc_now()
        cutoff = when - timedelta(seconds=DUPLICATE_WINDOW_SECONDS)
        dup = (
            self._db.query(Order)
            .filter(
                Order.sub_account_id == sub.id,
                Order.asset == data.asset.upper(),
                Order.side == Side.BUY,
                Order.quantity == quantity,
                Order.price == price,
                Order.datetime >= cutoff,
                Order.datetime <= when,
            )
            .first()
        )
        if dup is not None:
            raise ValueError(
                f"Possible duplicate of order {dup.id[:8]}… "
                f"(same asset/qty/price within {DUPLICATE_WINDOW_SECONDS}s). "
                f"Set an explicit `when` if intentional."
            )

        leverage: Optional[int] = None
        direction: Optional[Direction] = None
        margin_used: Optional[Decimal] = None
        liquidation_price: Optional[Decimal] = None
        funding_accumulated: Optional[Decimal] = None

        if sub.type == SubAccountType.FUTURES:
            if data.leverage is None or data.leverage <= 0:
                raise ValueError("Futures order requires leverage >= 1")
            if data.direction is None:
                raise ValueError("Futures order requires direction (LONG or SHORT)")
            leverage = int(data.leverage)
            direction = data.direction
            margin_used = calc_margin_used(quantity, price, leverage)
            liquidation_price = calc_liquidation_price(price, leverage, direction)
            funding_accumulated = Decimal(data.funding_accumulated)

        # Compute slippage if user reported their expected price
        slippage = (price - Decimal(data.expected_price)) if data.expected_price else None

        order = Order(
            sub_account_id=sub.id,
            datetime=when,
            asset=data.asset.upper(),
            side=Side.BUY,
            quantity=quantity,
            price=price,
            total_value=total_value,
            fee=Decimal(data.fee),
            note=data.note,
            leverage=leverage,
            direction=direction,
            margin_used=margin_used,
            liquidation_price=liquidation_price,
            funding_accumulated=funding_accumulated,
            status=OrderStatus.OPEN,
            remaining_quantity=quantity,
            # Phase 2 metadata
            strategy_id=data.strategy_id,
            order_type=data.order_type,
            execution_venue=data.execution_venue,
            exchange_order_id=data.exchange_order_id,
            exchange_trade_id=data.exchange_trade_id,
            expected_price=Decimal(data.expected_price) if data.expected_price else None,
            slippage=slippage,
            fee_currency=data.fee_currency,
            maker_taker=data.maker_taker,
        )
        self._db.add(order)
        self._db.flush()  # populate order.id before snapshotting
        _attach_tags(self._db, order, data.tag_ids)
        _create_confirmation(self._db, order)
        self._db.commit()
        self._db.refresh(order)
        logger.info(
            "order.create_buy",
            extra={
                "order_id": order.id,
                "sub_account_id": sub.id,
                "asset": order.asset,
                "quantity": str(order.quantity),
                "price": str(order.price),
                "leverage": order.leverage,
                "direction": order.direction.value if order.direction else None,
            },
        )
        return order

    def update_funding(self, order_id: str, funding_accumulated: Decimal) -> Order:
        order = self._db.get(Order, order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")
        if order.direction is None:
            raise ValueError("Funding can only be set on futures orders")
        order.funding_accumulated = Decimal(funding_accumulated)
        self._db.commit()
        self._db.refresh(order)
        return order

    def update_order(
        self,
        order_id: str,
        *,
        when: Optional[datetime] = None,
        price: Optional[Decimal] = None,
        fee: Optional[Decimal] = None,
        note: Optional[str] = None,
    ) -> Order:
        """Edit only fields that don't disturb lot accounting (datetime / price / fee / note).

        Quantity and side aren't editable — change them by deleting and re-creating.
        Editing price on a futures BUY recomputes margin_used + liquidation_price.
        """
        from backend.calculators.futures_calc import calc_liquidation_price, calc_margin_used

        order = self._db.get(Order, order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")

        if when is not None:
            order.datetime = when
        if price is not None:
            if price <= 0:
                raise ValueError("price must be positive")
            order.price = Decimal(price)
            order.total_value = Decimal(order.quantity) * Decimal(price)
            if order.side == Side.BUY and order.direction is not None and order.leverage:
                order.margin_used = calc_margin_used(
                    Decimal(order.quantity), Decimal(price), order.leverage
                )
                order.liquidation_price = calc_liquidation_price(
                    Decimal(price), order.leverage, order.direction
                )
        if fee is not None:
            if fee < 0:
                raise ValueError("fee cannot be negative")
            order.fee = Decimal(fee)
        if note is not None:
            order.note = note or None

        self._db.commit()
        self._db.refresh(order)
        return order

    def delete_order(self, order_id: str) -> None:
        """Delete an order with status recalc on the linked buy.

        - Deleting a SELL: returns its quantity to the linked BUY's remaining and
          re-opens the buy's status accordingly.
        - Deleting a BUY: refused if any sells are linked to it. Delete those first.
        """
        order = self._db.get(Order, order_id)
        if order is None:
            raise ValueError(f"Order {order_id} not found")

        if order.side == Side.BUY:
            linked_count = (
                self._db.query(Order)
                .filter(Order.linked_buy_order_id == order.id)
                .count()
            )
            if linked_count > 0:
                raise ValueError(
                    f"Buy order has {linked_count} linked sell(s) — delete the sells first"
                )
            self._db.delete(order)
            self._db.commit()
            return

        # SELL — restore the linked buy's remaining + status.
        if order.linked_buy_order_id:
            buy = self._db.get(Order, order.linked_buy_order_id)
            if buy is not None:
                returned = Decimal(order.sell_quantity or order.quantity)
                new_remaining = Decimal(buy.remaining_quantity) + returned
                buy.remaining_quantity = new_remaining
                if new_remaining >= Decimal(buy.quantity):
                    buy.remaining_quantity = Decimal(buy.quantity)
                    buy.status = OrderStatus.OPEN
                else:
                    buy.status = OrderStatus.PARTIALLY_CLOSED

        self._db.delete(order)
        self._db.commit()
        logger.info(
            "order.delete",
            extra={
                "order_id": order_id,
                "side": order.side.value,
                "asset": order.asset,
                "quantity": str(order.quantity),
            },
        )

    async def create_sell(self, data: SellOrderInput) -> Order:
        buy = self._db.get(Order, data.linked_buy_order_id)
        if buy is None:
            raise ValueError(f"Buy order {data.linked_buy_order_id} not found")
        if buy.side != Side.BUY:
            raise ValueError("Linked order must be a BUY order")
        if buy.status == OrderStatus.CLOSED:
            raise ValueError("Linked buy order is already fully closed")

        sell_qty = Decimal(data.sell_quantity)
        if sell_qty <= 0:
            raise ValueError("Sell quantity must be positive")
        remaining = Decimal(buy.remaining_quantity)
        if sell_qty > remaining:
            raise ValueError(
                f"Sell quantity {sell_qty} exceeds remaining {remaining} on buy order"
            )

        sub = buy.sub_account
        base = sub.portfolio.base_currency.value
        price = data.price if data.price is not None else await self._prices.get_price(
            buy.asset, base
        )
        total_value = price * sell_qty

        slippage = (price - Decimal(data.expected_price)) if data.expected_price else None

        sell = Order(
            sub_account_id=sub.id,
            datetime=data.when or utc_now(),
            asset=buy.asset,
            side=Side.SELL,
            quantity=sell_qty,
            price=price,
            total_value=total_value,
            fee=Decimal(data.fee),
            note=data.note,
            linked_buy_order_id=buy.id,
            sell_quantity=sell_qty,
            status=OrderStatus.CLOSED,
            remaining_quantity=Decimal("0"),
            # Phase 2 metadata (sell inherits buy's strategy if user didn't override)
            strategy_id=data.strategy_id or buy.strategy_id,
            order_type=data.order_type,
            execution_venue=data.execution_venue,
            exchange_order_id=data.exchange_order_id,
            exchange_trade_id=data.exchange_trade_id,
            expected_price=Decimal(data.expected_price) if data.expected_price else None,
            slippage=slippage,
            fee_currency=data.fee_currency,
            maker_taker=data.maker_taker,
        )

        new_remaining = remaining - sell_qty
        buy.remaining_quantity = new_remaining
        buy.status = OrderStatus.CLOSED if new_remaining == 0 else OrderStatus.PARTIALLY_CLOSED

        self._db.add(sell)
        self._db.flush()
        _attach_tags(self._db, sell, data.tag_ids)
        _create_confirmation(self._db, sell)
        self._db.commit()
        self._db.refresh(sell)
        self._db.refresh(buy)
        logger.info(
            "order.create_sell",
            extra={
                "order_id": sell.id,
                "linked_buy_id": buy.id,
                "asset": sell.asset,
                "sell_quantity": str(sell_qty),
                "price": str(price),
                "buy_status_after": buy.status.value,
                "buy_remaining_after": str(buy.remaining_quantity),
            },
        )
        return sell

    def get_open_buys(
        self, sub_account_id: str, asset: Optional[str] = None
    ) -> List[Order]:
        q = (
            self._db.query(Order)
            .filter(Order.sub_account_id == sub_account_id)
            .filter(Order.side == Side.BUY)
            .filter(Order.status != OrderStatus.CLOSED)
            .filter(Order.remaining_quantity > 0)
        )
        if asset:
            q = q.filter(Order.asset == asset.upper())
        return list(q.order_by(Order.datetime).all())

    def list_orders(
        self,
        sub_account_id: Optional[str] = None,
        asset: Optional[str] = None,
        side: Optional[Side] = None,
    ) -> List[Order]:
        q = self._db.query(Order)
        if sub_account_id:
            q = q.filter(Order.sub_account_id == sub_account_id)
        if asset:
            q = q.filter(Order.asset == asset.upper())
        if side:
            q = q.filter(Order.side == side)
        return list(q.order_by(Order.datetime.desc()).all())

    def list_trades_for_portfolio(self, portfolio_id: str) -> List[Trade]:
        from backend.models import Portfolio

        portfolio = self._db.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        sub_ids = [s.id for s in portfolio.sub_accounts]
        sub_by_id = {s.id: s for s in portfolio.sub_accounts}
        if not sub_ids:
            return []

        orders = (
            self._db.query(Order)
            .filter(Order.sub_account_id.in_(sub_ids))
            .order_by(Order.datetime)
            .all()
        )
        return build_trades(orders, sub_account_lookup=sub_by_id.get)
