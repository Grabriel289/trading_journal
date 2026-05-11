import uuid
from datetime import datetime as DT
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.util.clock import utc_now


class ManualPriceEntry(Base):
    __tablename__ = "manual_price_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    set_by: Mapped[str] = mapped_column(String(80), nullable=False, default="user")
    created_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)

    asset = relationship("Asset", back_populates="manual_prices")
