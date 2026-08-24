from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderType, PaymentType, ZoneType
from app.schemas.zones import INDIAN_PINCODE_PATTERN, ZoneResponse


class RateCardCreate(BaseModel):
    order_type: OrderType
    from_zone_id: UUID
    to_zone_id: UUID
    rate_per_kg: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    minimum_charge: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class RateCardUpdate(BaseModel):
    order_type: OrderType | None = None
    from_zone_id: UUID | None = None
    to_zone_id: UUID | None = None
    rate_per_kg: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    minimum_charge: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)


class RateCardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_type: OrderType
    from_zone_id: UUID
    to_zone_id: UUID
    rate_per_kg: Decimal
    minimum_charge: Decimal
    created_at: datetime


class CODRateCreate(BaseModel):
    order_type: OrderType
    surcharge: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class CODRateUpdate(BaseModel):
    order_type: OrderType | None = None
    surcharge: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)


class CODRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_type: OrderType
    surcharge: Decimal
    created_at: datetime


class QuoteRequest(BaseModel):
    pickup_pincode: str = Field(pattern=INDIAN_PINCODE_PATTERN)
    drop_pincode: str = Field(pattern=INDIAN_PINCODE_PATTERN)
    length_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    breadth_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    height_cm: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    actual_weight_kg: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    order_type: OrderType
    payment_type: PaymentType


class QuoteResponse(BaseModel):
    pickup_zone: ZoneResponse
    drop_zone: ZoneResponse
    zone_type: ZoneType
    actual_weight: Decimal
    volumetric_weight: Decimal
    chargeable_weight: Decimal
    rate_per_kg: Decimal
    minimum_charge_applied: bool
    base_charge: Decimal
    cod_surcharge: Decimal
    total_charge: Decimal
