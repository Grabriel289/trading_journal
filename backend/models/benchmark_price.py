"""BenchmarkPrice — daily close for benchmark assets, populated by a job.

Used for alpha calculation, tracking error, information ratio — anywhere
performance is compared against a benchmark like BTC or ETH.
"""
import uuid
from datetime import date as date_cls, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base
from backend.util.clock import utc_now


class BenchmarkPrice(Base):
    __tablename__ = "benchmark_prices"
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_benchmark_symbol_date"),
        Index("ix_benchmark_symbol", "symbol"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[date_cls] = mapped_column(Date, nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
