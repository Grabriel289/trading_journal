"""Strategy table — named buckets for per-strategy P&L attribution.

Examples: "BTC Momentum", "ETH Mean Reversion", "Altcoin Breakout",
"DCA Core", "Hedging", "Arbitrage". Orders may reference one strategy
or none. Disabling a strategy doesn't break historical orders.
"""
import uuid
from datetime import datetime as DT
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.util.clock import utc_now


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(
        String(7), nullable=True,
        comment="Optional hex color for UI (e.g. '#25d9a7')",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)

    orders = relationship("Order", back_populates="strategy")
