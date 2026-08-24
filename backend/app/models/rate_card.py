import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import OrderType


class RateCard(Base):
    __tablename__ = "rate_cards"
    __table_args__ = (
        UniqueConstraint("order_type", "from_zone_id", "to_zone_id", name="uq_rate_cards_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_type: Mapped[OrderType] = mapped_column(
        String(10), nullable=False
    )  # plain string + validation at edge; avoids PG enum migration pain
    from_zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False
    )
    to_zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False
    )
    rate_per_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    minimum_charge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
