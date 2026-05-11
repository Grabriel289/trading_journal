"""FundingPayment — one row per 8h funding event for an open futures position.

Replaces the denormalized `Order.funding_accumulated` cache with an auditable
time-series. The cache stays in sync as the sum of payment_amount for the
order — useful for fast reads.
"""
import uuid
from datetime import datetime as DT
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.util.clock import utc_now


class FundingPayment(Base):
    __tablename__ = "funding_payments"
    __table_args__ = (
        Index("ix_funding_order_time", "order_id", "funding_time"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    funding_time: Mapped[DT] = mapped_column(DateTime, nullable=False)
    funding_rate: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    mark_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    position_size: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    payment_amount: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False,
        comment="position_size × mark_price × funding_rate × direction_sign — positive = paid",
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)

    order = relationship("Order", back_populates="funding_payments")
