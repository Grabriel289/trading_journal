"""TradeConfirmation — append-only compliance record of every order at creation.

Snapshots the order's key fields at the moment of creation. NEVER updated or
deleted, even if the underlying Order is later edited or soft-deleted. This is
the canonical "what was executed" record for audit / tax / reconciliation.
"""
import uuid
from datetime import datetime as DT
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base
from backend.util.clock import utc_now


class TradeConfirmation(Base):
    __tablename__ = "trade_confirmations"
    __table_args__ = (
        Index("ix_tc_order", "order_id"),
        Index("ix_tc_confirmed", "confirmed_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id"), nullable=False,
    )
    confirmed_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Denormalized snapshot — these fields are FROZEN at the moment of order
    # creation, even if the Order row is later edited or soft-deleted.
    portfolio_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sub_account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sub_account_name: Mapped[str] = mapped_column(String(120), nullable=False)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    fee_currency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    order_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    execution_venue: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    strategy_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    leverage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    margin_used: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    linked_buy_order_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Full structured snapshot for forward compatibility (JSON for portability —
    # JSONB on Postgres, JSON-encoded TEXT on SQLite).
    raw_snapshot: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
