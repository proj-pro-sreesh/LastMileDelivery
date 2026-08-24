from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AvailabilityStatus
from app.schemas.zones import INDIAN_PINCODE_PATTERN


class AvailabilityUpdateRequest(BaseModel):
    availability_status: AvailabilityStatus


class LocationUpdateRequest(BaseModel):
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)
    pincode: str | None = Field(default=None, pattern=INDIAN_PINCODE_PATTERN)


class ManualAssignRequest(BaseModel):
    agent_id: UUID


class AgentAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    name: str
    email: str
    phone: str | None
    availability_status: AvailabilityStatus
    latitude: Decimal | None
    longitude: Decimal | None
    current_zone_id: UUID | None
    vehicle_type: str | None
    active_orders: int


class AssignmentResultResponse(BaseModel):
    assigned: bool
    message: str | None = None
    order_id: UUID | None = None
    order_status: str | None = None
    assigned_agent_id: UUID | None = None
