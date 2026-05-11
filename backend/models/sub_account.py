import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.models.enums import SubAccountType
from backend.util.clock import utc_now


class SubAccount(Base):
    __tablename__ = "sub_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portfolio_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[SubAccountType] = mapped_column(SAEnum(SubAccountType), nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    portfolio = relationship("Portfolio", back_populates="sub_accounts")
    orders = relationship("Order", back_populates="sub_account", cascade="all, delete-orphan")
    deposits = relationship("Deposit", back_populates="sub_account", cascade="all, delete-orphan")
