import uuid
from datetime import datetime as DT
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.models.enums import (
    Direction, ExecutionVenue, MakerTaker, OrderStatus, OrderType, Side,
)
from backend.util.clock import utc_now


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sub_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sub_accounts.id", ondelete="CASCADE"), nullable=False
    )
    datetime: Mapped[DT] = mapped_column(DateTime, nullable=False)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[Side] = mapped_column(SAEnum(Side), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False, default=Decimal("0"))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    leverage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    direction: Mapped[Optional[Direction]] = mapped_column(SAEnum(Direction), nullable=True)
    margin_used: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    liquidation_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    funding_accumulated: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)

    linked_buy_order_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("orders.id"), nullable=True
    )
    sell_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(28, 10), nullable=True)

    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus), nullable=False, default=OrderStatus.OPEN
    )
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)

    # ── Phase 2 Step 1: strategy attribution ──
    strategy_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("strategies.id"), nullable=True, default=None,
    )

    # ── Phase 2 Step 2: execution metadata ──
    order_type: Mapped[Optional[OrderType]] = mapped_column(
        SAEnum(OrderType), nullable=True, default=None,
    )
    execution_venue: Mapped[Optional[ExecutionVenue]] = mapped_column(
        SAEnum(ExecutionVenue), nullable=True, default=None,
    )
    exchange_order_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default=None, index=True,
    )
    exchange_trade_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, default=None,
    )
    expected_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(24, 8), nullable=True, default=None,
    )
    slippage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(24, 8), nullable=True, default=None,
    )
    fee_currency: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default=None,
    )
    maker_taker: Mapped[Optional[MakerTaker]] = mapped_column(
        SAEnum(MakerTaker), nullable=True, default=None,
    )

    # ── Phase 2 Step 2: soft-delete (audit trail bones — full audit log is later) ──
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[DT]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[Optional[DT]] = mapped_column(
        DateTime, nullable=True, onupdate=utc_now,
    )

    sub_account = relationship("SubAccount", back_populates="orders")
    strategy = relationship("Strategy", back_populates="orders")
    funding_payments = relationship(
        "FundingPayment", back_populates="order", cascade="all, delete-orphan",
    )
    tags = relationship("Tag", secondary="order_tags", back_populates="orders")
