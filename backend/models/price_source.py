import uuid
from datetime import datetime as DT
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.util.clock import utc_now


class SourceType(str, Enum):
    BINANCE = "BINANCE"
    KUCOIN = "KUCOIN"
    COINGECKO = "COINGECKO"
    MANUAL = "MANUAL"


class PriceSource(Base):
    __tablename__ = "price_sources"
    __table_args__ = (
        UniqueConstraint("asset_id", "source_type", name="uq_source_per_asset"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[SourceType] = mapped_column(SAEnum(SourceType), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)

    asset = relationship("Asset", back_populates="sources")
