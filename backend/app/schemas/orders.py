from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderStatus, OrderType, PaymentType
from app.schemas.zones import INDIAN_PINCODE_PATTERN


class OrderCreateRequest(BaseModel):
    """customer_id is only honored for ADMIN callers (create on behalf)."""

    customer_id: UUID | None = None
    pickup_address: str = Field(min_length=5, max_length=500)
    pickup_pincode: str = Field(pattern=INDIAN_PINCODE_PATTERN)
    drop_address: str = Field(min_length=5, max_length=500)
    drop_pincode: str = Field(pattern=INDIAN_PINCODE_PATTERN)
    length_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    breadth_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    height_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    actual_weight_kg: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    order_type: OrderType
    payment_type: PaymentType
    scheduled_delivery_date: date | None = None


class QuotePreviewResponse(BaseModel):
    customer_id: UUID | None = None
    total_charge: Decimal
    base_charge: Decimal
    cod_surcharge: Decimal


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    assigned_agent_id: UUID | None
    pickup_address: str
    pickup_pincode: str
    drop_address: str
    drop_pincode: str
    length_cm: Decimal
    breadth_cm: Decimal
    height_cm: Decimal
    actual_weight_kg: Decimal
    volumetric_weight_kg: Decimal
    chargeable_weight_kg: Decimal
    order_type: OrderType
    payment_type: PaymentType
    base_charge: Decimal
    cod_surcharge: Decimal
    total_charge: Decimal
    status: OrderStatus
    delivery_attempt: int
    scheduled_delivery_date: date | None
    created_at: datetime
    updated_at: datetime


class TrackingEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    status: OrderStatus
    actor_id: UUID
    remarks: str | None
    created_at: datetime
