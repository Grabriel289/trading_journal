import uuid
from datetime import date, datetime as DT
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.util.clock import utc_now


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "date", name="uq_snapshot_portfolio_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)

    total_equity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    total_balance: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    total_deposited: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    drawdown_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)

    sub_account_data = mapped_column(JSON, nullable=False)

    created_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)

    portfolio = relationship("Portfolio")
