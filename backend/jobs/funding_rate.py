"""Funding-rate sync job.

For every open futures BUY:
  1. Pulls Binance funding events since the latest stored payment (or order
     datetime if no payments yet).
  2. Inserts one `FundingPayment` row per new event with the dollar amount
     `quantity × markPrice × fundingRate × directionSign`.
  3. Updates the denormalized cache `Order.funding_accumulated` to the
     sum of all payment_amounts on that order.

LONG positions with positive funding rates pay (positive amount); SHORTs receive.
"""
import logging
from decimal import Decimal

from sqlalchemy import func

from backend.db.database import SessionLocal
from backend.exchange.base import BaseExchange
from backend.models import (
    Direction, FundingPayment, Order, OrderStatus, Portfolio, Side,
)


logger = logging.getLogger(__name__)


async def run_funding_sync_job(exchange: BaseExchange) -> int:
    """Returns the number of OPEN futures orders touched (updated or unchanged)."""
    db = SessionLocal()
    touched = 0
    new_payments = 0
    try:
        portfolios = db.query(Portfolio).all()
        for portfolio in portfolios:
            base = portfolio.base_currency.value
            for sub in portfolio.sub_accounts:
                rows = (
                    db.query(Order)
                    .filter(Order.sub_account_id == sub.id)
                    .filter(Order.side == Side.BUY)
                    .filter(Order.direction.isnot(None))
                    .filter(Order.status != OrderStatus.CLOSED)
                    .all()
                )
                for o in rows:
                    touched += 1
                    last = (
                        db.query(FundingPayment)
                        .filter(FundingPayment.order_id == o.id)
                        .order_by(FundingPayment.funding_time.desc())
                        .first()
                    )
                    start_time = last.funding_time if last else o.datetime

                    try:
                        events = await exchange.get_funding_history(
                            asset=o.asset, base=base, start_time=start_time,
                        )
                    except Exception as exc:
                        logger.warning("funding fetch failed for %s: %s", o.id, exc)
                        continue

                    sign = Decimal("1") if o.direction == Direction.LONG else Decimal("-1")
                    qty = Decimal(o.quantity)
                    for ev in events:
                        # Skip duplicates by exact funding_time match
                        exists = (
                            db.query(FundingPayment)
                            .filter(
                                FundingPayment.order_id == o.id,
                                FundingPayment.funding_time == ev.funding_time,
                            )
                            .first()
                        )
                        if exists is not None:
                            continue
                        amount = sign * qty * ev.mark_price * ev.funding_rate
                        db.add(FundingPayment(
                            order_id=o.id,
                            funding_time=ev.funding_time.replace(tzinfo=None),
                            funding_rate=ev.funding_rate,
                            mark_price=ev.mark_price,
                            position_size=qty,
                            payment_amount=amount,
                        ))
                        new_payments += 1

                    # Recompute the denormalized cache from the rows we just persisted
                    db.flush()
                    total = (
                        db.query(func.coalesce(func.sum(FundingPayment.payment_amount), 0))
                        .filter(FundingPayment.order_id == o.id)
                        .scalar()
                    )
                    o.funding_accumulated = Decimal(total)
        db.commit()
        logger.info(
            "Funding sync job — %d open futures orders touched, %d new payment rows",
            touched, new_payments,
        )
        return touched
    finally:
        db.close()
