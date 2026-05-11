import uuid
from datetime import datetime as DT
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.models.enums import DepositType
from backend.util.clock import utc_now


class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sub_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sub_accounts.id", ondelete="CASCADE"), nullable=False
    )
    datetime: Mapped[DT] = mapped_column(DateTime, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    type: Mapped[DepositType] = mapped_column(SAEnum(DepositType), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)

    sub_account = relationship("SubAccount", back_populates="deposits")
