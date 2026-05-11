import uuid
from datetime import datetime as DT
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.models.enums import Chain, Sector
from backend.util.clock import utc_now


class AssetType(str, Enum):
    CRYPTO = "CRYPTO"
    TOKEN = "TOKEN"
    FUND = "FUND"
    OTHER = "OTHER"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType), nullable=False, default=AssetType.CRYPTO
    )
    coingecko_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Phase 2 Step 8: classification for exposure analysis
    sector: Mapped[Optional[Sector]] = mapped_column(SAEnum(Sector), nullable=True)
    chain: Mapped[Optional[Chain]] = mapped_column(SAEnum(Chain), nullable=True)
    market_cap_tier: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True,
        comment="MEGA / LARGE / MID / SMALL / MICRO",
    )

    created_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)

    sources = relationship(
        "PriceSource", back_populates="asset", cascade="all, delete-orphan", order_by="PriceSource.priority"
    )
    manual_prices = relationship(
        "ManualPriceEntry", back_populates="asset", cascade="all, delete-orphan",
        order_by="desc(ManualPriceEntry.created_at)"
    )
