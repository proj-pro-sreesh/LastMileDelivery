import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import OrderStatus


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    pickup_address: Mapped[str] = mapped_column(String(500), nullable=False)
    pickup_pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    pickup_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    pickup_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    pickup_zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False
    )

    drop_address: Mapped[str] = mapped_column(String(500), nullable=False)
    drop_pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    drop_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    drop_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    drop_zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zones.id", ondelete="RESTRICT"), nullable=False
    )

    length_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    breadth_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    actual_weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    volumetric_weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    chargeable_weight_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order_type: Mapped[str] = mapped_column(String(10), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(10), nullable=False)

    base_charge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cod_surcharge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_charge: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, create_constraint=True, name="ck_orders_status", length=20),
        default=OrderStatus.PENDING,
        server_default=OrderStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    delivery_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    scheduled_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
