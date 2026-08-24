from app.core.database import Base
from app.models.area import Area
from app.models.cod_rate import CODRate
from app.models.enums import OrderType, PaymentType, ZoneType
from app.models.rate_card import RateCard
from app.models.user import User, UserRole
from app.models.zone import Zone

__all__ = [
    "Base",
    "User",
    "UserRole",
    "Zone",
    "Area",
    "RateCard",
    "CODRate",
    "OrderType",
    "PaymentType",
    "ZoneType",
]

# Model modules above are imported so Alembic autogenerate sees every table.
