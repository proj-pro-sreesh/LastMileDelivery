from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

INDIAN_PINCODE_PATTERN = r"^[1-9][0-9]{5}$"


class ZoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9\-]+$")


class ZoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9\-]+$")


class ZoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    created_at: datetime


class AreaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    pincode: str = Field(pattern=INDIAN_PINCODE_PATTERN)
    zone_id: UUID


class AreaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    pincode: str | None = Field(default=None, pattern=INDIAN_PINCODE_PATTERN)
    zone_id: UUID | None = None


class AreaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    pincode: str
    zone_id: UUID
    created_at: datetime
