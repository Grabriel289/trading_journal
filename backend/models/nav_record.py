"""NAVRecord — daily Net Asset Value per unit, for investor reporting.

When the fund accepts subscriptions/redemptions, units_outstanding lets NAV
per unit stay coherent as capital flows in/out. For a single-investor fund
units stays at 1 and nav_per_unit == total_nav.
"""
import uuid
from datetime import date as date_cls, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.util.clock import utc_now


class NAVRecord(Base):
    __tablename__ = "nav_records"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "date", name="uq_nav_portfolio_date"),
        Index("ix_nav_date", "date"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False,
    )
    date: Mapped[date_cls] = mapped_column(Date, nullable=False)
    total_nav: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    units_outstanding: Mapped[Decimal] = mapped_column(
        Numeric(24, 8), nullable=False, default=Decimal("1"),
    )
    nav_per_unit: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    gross_exposure: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    net_exposure: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    portfolio = relationship("Portfolio")
