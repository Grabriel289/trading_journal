import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, Enum as SAEnum, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.models.enums import BaseCurrency
from backend.util.clock import utc_now


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[BaseCurrency] = mapped_column(
        SAEnum(BaseCurrency), nullable=False, default=BaseCurrency.USDT
    )

    # Phase 2 Step 6: institutional metadata
    inception_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    benchmark: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    high_water_mark: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    management_fee_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 4), nullable=True,
        comment="Annual management fee, decimal (0.02 = 2%)",
    )
    performance_fee_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 4), nullable=True,
        comment="Performance fee above HWM, decimal (0.20 = 20%)",
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    sub_accounts = relationship(
        "SubAccount", back_populates="portfolio", cascade="all, delete-orphan"
    )
