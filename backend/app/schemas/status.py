from datetime import date

from pydantic import BaseModel, Field

from app.models.enums import OrderStatus


class AgentStatusUpdateRequest(BaseModel):
    status: OrderStatus
    remarks: str | None = Field(default=None, max_length=500)


class AdminStatusOverrideRequest(BaseModel):
    status: OrderStatus
    remarks: str = Field(min_length=3, max_length=500)


class RescheduleRequest(BaseModel):
    scheduled_delivery_date: date | None = None
    remarks: str | None = Field(default=None, max_length=500)
