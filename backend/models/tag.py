"""Tag — flexible labels on orders. Many-to-many via `order_tags`.

Examples: "breakout", "mean-reversion", "news-driven", "high-conviction",
"Q1-thesis", "hedge", "bull-market". Free-form — the user decides the
taxonomy.
"""
import uuid
from datetime import datetime as DT

from sqlalchemy import Column, DateTime, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base
from backend.util.clock import utc_now


# Many-to-many junction
order_tags = Table(
    "order_tags",
    Base.metadata,
    Column("order_id", String(36),
           ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id",   String(36),
           ForeignKey("tags.id",   ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6B7280")
    created_at: Mapped[DT] = mapped_column(DateTime, default=utc_now, nullable=False)

    orders = relationship("Order", secondary=order_tags, back_populates="tags")
